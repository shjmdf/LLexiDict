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

CONCURRENCY = 128
SOURCE_FILE = "jp-clean.txt"
DB_NAME = "japanese_dictionary.db"
SYSTEM_MESSAGE_CONTENT = (
    "You are a Japanese dictionary generator. Your response MUST be ONLY the requested JSON object. "
    "DO NOT include any explanatory text, preambles, comments, or chain-of-thought before or after the JSON block. "
    "Start immediately with '{' and end with '}'."
)
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
      
      "readings": {{//must be generated
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

      "search_keywords": [//must be generated
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
                            {"role": "user", "content": get_japanese_prompt(word)}
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
    
    print("日语词典构建完成！")

if __name__ == "__main__":
    asyncio.run(main())