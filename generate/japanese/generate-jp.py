import os
import json
import asyncio
import re
import sqlite3
import time
from openai import AsyncOpenAI

# ================= 配置 =================
API_KEY = ""
BASE_URL = ""
MODEL_NAME = ""
CONCURRENCY = 128

SOURCE_FILE = "jp-clean.txt"
DB_NAME = "japanese_dictionary.db"
SYSTEM_MESSAGE_CONTENT = (
    "You are a Japanese dictionary generator. Your response MUST be ONLY the requested JSON object. "
    "DO NOT include any explanatory text, preambles, comments, or chain-of-thought before or after the JSON block. "
    "Start immediately with '{' and end with '}'."
)
# ================= 消费者 (写入线程) =================
async def db_writer(queue):
    print("数据库写入线程启动...")
    conn = sqlite3.connect(DB_NAME)
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

    batch_buffer = []
    last_commit = time.time()

    while True:
        item = await queue.get()
        if item is None: break
        
        word, keywords, data_str = item
        batch_buffer.append((word, keywords, data_str))

        if len(batch_buffer) >= 50 or (time.time() - last_commit > 3 and batch_buffer):
            try:
                cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch_buffer)
                conn.commit()
                batch_buffer = []
                last_commit = time.time()
            except Exception as e:
                print(f"DB Error: {e}")

        queue.task_done()

    if batch_buffer:
        cursor.executemany("INSERT OR REPLACE INTO dictionary (word, keywords, data) VALUES (?, ?, ?)", batch_buffer)
        conn.commit()
    
    conn.close()
    print("数据库写入完成。")

# ================= 日语 Prompt =================
def get_japanese_prompt(word):
    return f"""
    Role: Meticulous and Verifying Japanese-Chinese Lexicographer.
    Target Word: "{word}" (Japanese).
    Target Audience: Advanced Learners (N1/N2) aiming for native-like nuance.

    **Core Principles: ACCURACY > COMPLETENESS. VERIFICATION is MANDATORY.**

    **🔥🔥 CRITICAL VERIFICATION STEPS (Must perform before generating): 🔥🔥**

    1.  **AMBIGUITY CHECK:**
        * Does "{word}" have multiple, distinct meanings or parts of speech? (e.g., `そういう` as a pre-noun adjective vs. `そう言う` as a verb phrase).
        * **Action:** You MUST select the **single most common/primary meaning** associated with the `word` spelling.
        * **Constraint:** All subsequent fields (`pos`, `grammar_meta`, `inflections_detail`, `senses`, `examples`) MUST align 100% with this SINGLE chosen meaning. **Do not mix meanings.**

    2.  **DATA CONSISTENCY CHECK:**
        * `pitch_accent` ([num]) MUST exactly match the `pitch_visual` (L/H graph).
        * `inflections_detail` (活用形) MUST logically match the `pos` (词性) and `grammar_meta` (语法). (e.g., If `pos` is 'n.', `inflections_detail.forms` MUST be an empty array `[]`).
        * All `examples` MUST use the word in the exact `pos` and `sense` defined above.

    3.  **PRECISION CHECK:**
        * `ruby` (振假名): Must be 100% accurate, mapping the `kana` reading precisely to the `jp` kanji. **Pay extreme attention to おくりがな (okurigana)** (e.g., `お掛けして` -> `お掛(か)けして`).
        * `pitch_accent`: Source from standard lexicographical data (e.g., NHK). **If the pitch accent is unknown or widely disputed, use `"[?] Unknown"` instead of guessing.**

    ---
    Output STRICT JSON (No Markdown):
    {{
      "word": "Standard Written Form (e.g. 食べる, コンピュータ, 薔薇)",
      
      "readings": {{
          "kana": "Full Hiragana (e.g. たべる, こんぴゅーた)",
          "katakana": "Full Katakana (e.g. タベル, コンピュータ) - CRITICAL for search",
          "romaji": "Hepburn",
          "pitch_accent": "[num] Type (e.g. [2] Nakadaka) or [?] Unknown",
          "pitch_visual": "Text graph (e.g. LHHLL) or 'N/A'"
      }},

      "pos": "v. (Godan/Ichidan) / adj-i / adj-na / n. / exp. / rentaishi", // **Added 'rentaishi'**
      
      "grammar_meta": {{
          "verb_group": "Godan / Ichidan / Suru / N/A",
          "transitivity": "Transitive (他) / Intransitive (自) / N/A",
          "paired_verb": "Counterpart (e.g. 'kieru' -> 'kesu') or null"
      }},

      "inflections_detail": {{
          "forms": [
             // "Te-form", "Nai-form", "Ta-form", etc.
             // **If 'pos' is not a verb/adjective, this MUST be []**
          ]
      }},

      "search_keywords": [
          "Must include: Kanji form",
          "Must include: Kana reading (Hiragana)",
          "Must include: Katakana reading (e.g. タベル)", 
          "Must include: Romaji",
          "Must include: All generated conjugated forms (if any)"
      ],

      "script_nuance": "Analysis: Is Kanji standard? Is it often written in Katakana for emphasis, slang, or biological naming? (e.g. 'Often written as ネコ in scientific contexts')",
      
      "cultural_decoding": {{
          "register": "Teineigo / Kudaketa / Sonkeigo / Kenjougo / Neutral",
          "air_reading": "Hidden nuance / Implication",
          "caution": "Taboo / Usage warning / Common Pitfall (e.g. 'Do not confuse with X')"
      }},

      "senses": [
        {{
          "definitions": {{//be specific and concise, accurate and contextual
              "cn": "Natural Simplified Chinese, with cultural context and explicit usage",
              "jp": "Kokugo Jiten definition, with cultural context and explicit usage",
              "en": "Logical English definition, precise and contextual"
          }},
          "core_image": "Mental picture / Underlying concept",
          "collocations": [
              "Particle Usage (~ni vs ~wo)",
              "Set Phrase / Yojijukugo"
          ],
          "synonym_discrimination": "Compare with similar Kanji/Words",
          "examples": [
            {{
               "jp": "Natural sentence with Kanji",
               "kana": "Full Hiragana reading",
               "ruby": "Kanji(Kana) format (MUST BE 100% ACCURATE)",
               "cn": "Translation"
            }}
          ]
        }}
      ]
    }}
    Final Output Constraint: Your entire response must consist of the complete, valid JSON object, starting with '{{' and ending with '}}'. Nothing else.
    """

# ================= API Worker =================
async def worker(sem, client, queue, word):
    async with sem:
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[{"role": "system", "content": "You are a Japanese dictionary generator. Your response MUST be ONLY the requested JSON object. DO NOT include any explanatory text, preambles, comments, or chain-of-thought before or after the JSON block. Start immediately with '{' and end with '}'."}, 
                        {"role": "user", "content": get_japanese_prompt(word)}],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    ),
                    timeout=120
                )
                
                raw_content = response.choices[0].message.content
                
                match = re.search(r'\{.*\}', raw_content.strip(), re.DOTALL)
                
                if not match:
                    raise ValueError("JSON_BLOCK_NOT_FOUND: 无法在原始输出中隔离完整的 {} 结构。")

                content_json_only = match.group(0)
                
                # 正则表达式替换尾部多余符号
                content_json_clean = re.sub(r',\s*([\]\}])', r'\1', content_json_only)

                data = json.loads(content_json_clean)
                
                keywords_list = data.get("search_keywords", [])
                if word not in keywords_list:
                    keywords_list.append(word)
                keywords_str = " ".join([str(x) for x in keywords_list]).lower()
                
                await queue.put((word, keywords_str, content_json_clean))
                print(f"✅ {word}")
                return
                
            except json.JSONDecodeError as e:
                # JSON 内部有更复杂的错误（如缺少引号或冒号）
                print(f"❌ JSON PARSE FAIL (Internal): {word} | Error: {e.msg}")
                await asyncio.sleep(1) 
                continue
            except ValueError as e:
                print(f"❌ JSON BLOCK FAIL: {word} | Error: {e}")  
                await asyncio.sleep(1)
                continue
            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    print(f"⏳ 限流: {word}")
                    await asyncio.sleep(5)
                    continue
                else:
                    print(f"❌ {word}: {e}")
                    await asyncio.sleep(1)
                    continue
        print(f"💀 {word} 失败")

# ================= 主程序 =================
async def main():
    # 检查进度
    conn = sqlite3.connect(DB_NAME)
    try:
        existing = set(row[0] for row in conn.execute("SELECT word FROM dictionary"))
    except:
        existing = set()
    conn.close()
    print(f"📂 库中已有 {len(existing)} 个词。")

    # 读取列表
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, SOURCE_FILE)
    if not os.path.exists(file_path):
        print(f"❌ 找不到 {SOURCE_FILE}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        all_words = [line.strip() for line in f if line.strip()]

    # 过滤任务
    tasks_to_run = [w for w in all_words if w not in existing]
    print(f"🐍 剩余任务: {len(tasks_to_run)} 个。使用模型: {MODEL_NAME}")

    # 启动
    queue = asyncio.Queue()
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)
    db_task = asyncio.create_task(db_writer(queue))

    # batch-style processing
    chunk_size = 500
    for i in range(0, len(tasks_to_run), chunk_size):
        chunk = tasks_to_run[i:i+chunk_size]
        print(f"批次 {i} - {i+chunk_size} ...")
        workers = [asyncio.create_task(worker(sem, client, queue, word)) for word in chunk]
        await asyncio.gather(*workers)

    await queue.put(None)
    await db_task
    print("✅ 日语词典构建完成！")

if __name__ == "__main__":
    asyncio.run(main())