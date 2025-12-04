import os
import json
import asyncio
import sqlite3
import time
from openai import AsyncOpenAI
import random
import re

# ================= 配置 =================
API_KEY = "" 
BASE_URL = ""
MODEL_NAME = ""

CONCURRENCY = 64

SOURCE_FILE = "list_french.txt"
DB_NAME = "french_dictionary.db"
SYSTEM_MESSAGE_CONTENT = "You are a French dictionary generator. Output JSON only."

# ================= 数据库new =================
async def db_writer(queue):
    def blocking_db_init():
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dictionary (
                word TEXT PRIMARY KEY,
                keywords TEXT,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        return conn, cursor

    conn, cursor = await asyncio.to_thread(blocking_db_init)

    batch_buffer = []
    last_commit = time.time()

    while True:
        item = await queue.get()
        if item is None: break
        
        word, keywords, data_str = item
        batch_buffer.append((word, keywords, data_str))

        current_time = time.time()
        if len(batch_buffer) >= 50 or (current_time - last_commit > 2 and batch_buffer):
            try:
                batch_to_write = batch_buffer.copy()
                batch_buffer = []

                def blocking_db_write(batch):
                    cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch)
                    conn.commit()
                
                await asyncio.to_thread(blocking_db_write, batch_to_write)
                last_commit = current_time
                
            except Exception as e:
                print(f"⚠️ DB Error: {e}")
                batch_buffer = batch_to_write + batch_buffer
        
        queue.task_done()

    # 处理循环退出后剩余的任何项目
    if batch_buffer:
        try:
            def blocking_db_final_write(batch):
                cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch)
                conn.commit()
            await asyncio.to_thread(blocking_db_final_write, batch_buffer)
        except Exception as e:
            print(f"⚠️ Final DB Error: {e}")
    
    await asyncio.to_thread(conn.close)
    print("数据库写入完成。")

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

# ================= JSON 解析=================
def robust_json_parser(raw_content):
    try:
        data = json.loads(raw_content)
        return data, raw_content
    except json.JSONDecodeError as e:
        print(f"⚠️ 直接解析失败: {e.msg}。回退到正则提取...")
        match = re.search(r'\{.*\}', raw_content.strip(), re.DOTALL)
        
        if not match:
            raise ValueError("JSON_BLOCK_NOT_FOUND: 无法在原始输出中隔离完整的 {} 结构。")

        content_json_only = match.group(0)
        
        # 3. 清理尾随逗号
        content_json_clean = re.sub(r',\s*([\]\}])', r'\1', content_json_only)

        try:
            data = json.loads(content_json_clean)
            return data, content_json_clean
        except json.JSONDecodeError as final_e:
            raise ValueError(f"JSON_PARSE_FAIL (Internal): 无法解析清理后的 JSON。Error: {final_e.msg}")


# ================= API Worker =================
async def worker(sem, client, queue, word):
    async with sem:
        last_error = None
        
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": SYSTEM_MESSAGE_CONTENT},
                            {"role": "user", "content": get_french_prompt(word)}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    ),
                    timeout=200
                )
                
                raw_content = response.choices[0].message.content

                data, data_str = robust_json_parser(raw_content)
                
                inflections = data.get("inflections", [])
                if word not in inflections:
                    inflections.append(word)
                keywords_str = " ".join([str(x) for x in inflections]).lower()
                
                await queue.put((word, keywords_str, data_str))
                print(f"✅ {word}")
                return
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                if "429" in error_str:
                    print(f"⏳ 限流等待: {word}")
                    await asyncio.sleep(5 + random.uniform(0, 5)) # 增加抖动
                elif "JSONDecodeError" in error_str or "JSON_BLOCK_NOT_FOUND" in error_str or "JSON_PARSE_FAIL" in error_str:
                    print(f"⚠️ JSON 严重错误: {word} | {e}")
                    await asyncio.sleep(1)
                else:
                    print(f"❌ Worker 错误: {word} | {e}")
                    await asyncio.sleep(1 + random.uniform(0, 2))
        
        print(f"❌ {word} 失败 | 最终原因: {last_error}")
        
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
        print(f"❌ 找不到 {SOURCE_FILE}！")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        all_words = [line.strip() for line in f if line.strip()]

    tasks_to_run = [w for w in all_words if w not in existing]
    if not tasks_to_run:
        print("数据库已是最新，无需操作！")
        return
        
    print(f"剩余任务: {len(tasks_to_run)} 个。使用模型: {MODEL_NAME} | 并发: {CONCURRENCY}")

    queue = asyncio.Queue()
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)
    db_task = asyncio.create_task(db_writer(queue))

    print(f"正在创建 {len(tasks_to_run)} 个 API 任务...")
    workers = [
        asyncio.create_task(worker(sem, client, queue, word)) 
        for word in tasks_to_run
    ]

    print(f"🏃 开始处理... (并发上限 {CONCURRENCY})")
    await asyncio.gather(*workers)
    
    print("\n✅ 所有 API worker 均已完成。")

    print("⏳ 正在等待数据库队列清空...")
    await queue.join()

    print("⚠发送关闭信号到数据库写入线程...")
    await queue.put(None)
    await db_task
    
    print("法语词典构建完成！")

if __name__ == "__main__":
    asyncio.run(main())