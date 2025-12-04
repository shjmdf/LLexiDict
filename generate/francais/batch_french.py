import os
import json
import asyncio
import sqlite3
import time
from openai import AsyncOpenAI
import random
# ================= 配置 =================

API_KEY = "" 
BASE_URL = ""
MODEL_NAME = ""
CONCURRENCY = 24

SOURCE_FILE = "list_french.txt"
DB_NAME = "french_dictionary.db"

# ================= 数据库 =================
async def db_writer(queue):
    print("💾 数据库写入线程启动...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary (
            word TEXT PRIMARY KEY,
            keywords TEXT,  -- 搜索索引 (包含原形 + 变位)
            data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    batch_buffer = []
    last_commit = time.time()

    while True:
        item = await queue.get()
        if item is None: break
        
        word, keywords, data_str = item
        batch_buffer.append((word, keywords, data_str))

        if len(batch_buffer) >= 50 or (time.time() - last_commit > 2 and batch_buffer):
            try:
                cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch_buffer)
                conn.commit()
                batch_buffer = []
                last_commit = time.time()
            except Exception as e:
                print(f"⚠️ DB Error: {e}")

        queue.task_done()

    if batch_buffer:
        cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch_buffer)
        conn.commit()
    
    conn.close()
    print("🖊 数据库写入完成。")

# ================= 法语 Prompt =================
def get_french_prompt(word):
    return f"""
    Role: Expert French-Chinese Lexicographer. 
    Target Word: "{word}" (French).
    Task: Create a deep, insightful dictionary entry for advanced Chinese learners of French (C1/C2 level).
    
    🔥🔥 STRATEGY: SPLIT INFLECTIONS & CONTEXTUAL DEPTH 🔥🔥
    0. Strictly use traditional French spelling (l'orthographe traditionnelle) with circumflex accents (e.g., traîner, croître) unless the headword itself is specific to the 1990 reform.

    1. **Morphology Split**: A French word can be a Verb form, an Adjective, or both (e.g. 'refusé'). 
       - You must populate `verb_conjugations` AND `adjective_inflections` independently based on what the word *can functioning as*.
    
    2. **Contextual Meaning**: Do not just give a translation. For each sense, explain the **Context/Vibe** (e.g., "Used for physical pain, not mental sadness").
    
    3. **Synonym Discrimination**: Don't just say "X is different from Y". Explain the **Nuance**, **Register**, or **Connotation**. Why would a native speaker choose THIS word?
    
    4. **Core Image**: Abstract the meaning. Don't just repeat the definition. Find the **underlying logical concept** that connects the literal and metaphorical uses.

    5. **Language Rules**: 
       - Definitions MUST be **Simplified Chinese**.
       - Collocations MUST be **French**.
       - Analysis MUST be **English** (for logical precision).

    Output STRICT JSON (No Markdown):
    {{
      "word": "{word}",
      "ipa": "IPA pronunciation",
      "pos": "List ALL potential roles: v. / adj. / n.m. / n.f. / adv. / participe passé",
      "gender": "m. / f. / m. et f. / N/A",
      "related_lemma": "Root word (e.g. 'refuser' for 'refusé'). Null if it is the root.",
      
      "morphology": {{
         "group": "e.g. 1er groupe / 3e groupe (irrégulier)",
         "auxiliary": "avoir / être / les deux"
      }},

      // 变位与变格物理隔离
      "inflections_detail": {{
         // IF the word can function as an Adjective/Noun/Participle:
         // List Gender/Number variations (e.g. 'refusée', 'refusés', 'belles')
         "adjective_inflections": [
            "form1", "form2", "..."
         ],
         // IF the word can function as a Verb (or is a verb form):
         // List key Tense/Person variations (e.g. 'refusons', 'refusait')
         // If input is already conjugated (e.g. 'fus'), list its siblings or root forms.
         "verb_conjugations": [
            "form1", "form2", "..."
         ]
      }},

      // 扁平列表
      "search_keywords": ["list", "of", "all", "forms", "above", "for", "indexing"],

      "etymology": "Brief origin + logic (English)",
      "false_friend_alert": "Alert if it looks like English but differs (e.g. 'Coin' = Corner, not Money). Null if safe.",

      "senses": [ // List the top 3-5 distinct senses.
        {{
          "pos": "Specific POS for this sense (e.g. 'n.m.' or 'v.t.')",
          
          "definition_cn": "Chinese Definition (Precise and accurate), not a direct translation. In Simplified Chinese.",
          
          // 语境与核心意象
          "context_usage": "Explain WHEN to use this specific sense. (e.g. 'Formal contexts only' or 'Implies negative consequence'). Be more specific.",
          "core_image": {{
             "en": "The 'Soul' of the definition, be insightful and accurate, detailed and explicit.",
             "fr": "L'âme de la définition, soit perspicace et précise, détaillée et explicite."
          }},
          
          "register": "Courant / Soutenu / Familier / Argot",
          
          // 强制介词搭配
          "collocations": [
             "Verbe + Préposition (CRITICAL: e.g. 'jouer à' vs 'jouer de')",
             "Expression figée",
             "Common usage phrase"
          ],
          
          "synonym_discrimination": "Why choose this word over a synonym? (e.g. 'Grand vs Gros')",
          
          "examples": [
            {{ "fr": "Authentic sentence", "cn": "Natural translation in Simplified Chinese" }}
          ]
        }}
      ]
    }}
    """
# ================= API Worker =================
async def worker(sem, client, queue, word):
    await asyncio.sleep(random.uniform(0, 7))
    async with sem:
        last_error = None
        
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "You are a French dictionary generator. Output JSON only."},
                            {"role": "user", "content": get_french_prompt(word)}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    ),
                    timeout=200
                )
                
                content = response.choices[0].message.content
                
                data = json.loads(content)
                
                inflections = data.get("inflections", [])
                if word not in inflections:
                    inflections.append(word)
                keywords_str = " ".join([str(x) for x in inflections]).lower()
                
                await queue.put((word, keywords_str, content))
                print(f"✅ {word}")
                return
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                if "429" in error_str:
                    print(f"⏳ 限流等待: {word}")
                    await asyncio.sleep(5)
                elif "JSONDecodeError" in error_str:
                    print(f"⚠️ JSON 解析失败: {word}")
                    pass
                else:
                    pass
        
        print(f"💀 {word} 失败 | 原因: {last_error}")
        
# ================= 主程序 =================
async def main():
    conn = sqlite3.connect(DB_NAME)
    try:
        existing = set(row[0] for row in conn.execute("SELECT word FROM dictionary"))
    except:
        existing = set()
    conn.close()
    print(f"库中已有 {len(existing)} 个词。")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, SOURCE_FILE)
    if not os.path.exists(file_path):
        print(f"找不到 {SOURCE_FILE}，请先运行清洗脚本！")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        all_words = [line.strip() for line in f if line.strip()]

    tasks_to_run = [w for w in all_words if w not in existing]
    print(f"剩余任务: {len(tasks_to_run)} 个。使用模型: {MODEL_NAME}")

    queue = asyncio.Queue()
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)
    db_task = asyncio.create_task(db_writer(queue))

    chunk_size = 500
    for i in range(0, len(tasks_to_run), chunk_size):
        chunk = tasks_to_run[i:i+chunk_size]
        print(f"批次 {i} - {i+chunk_size} ...")
        workers = [asyncio.create_task(worker(sem, client, queue, word)) for word in chunk]
        await asyncio.gather(*workers)

    await queue.put(None)
    await db_task
    print("法语词典构建完成！")

if __name__ == "__main__":
    asyncio.run(main())