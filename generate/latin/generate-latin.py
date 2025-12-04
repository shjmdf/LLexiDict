import os
import json
import asyncio
import sqlite3
import time
from openai import AsyncOpenAI
import random
import re
import csv

# ================= 配置 =================
API_KEY = "" 
BASE_URL = ""
MODEL_NAME = ""

CONCURRENCY = 128
TIMEOUT = 300

SOURCE_FILE = "latin_data_cleaned.csv"
DB_NAME = "latin_dictionary.db"
SYSTEM_MESSAGE_CONTENT = "You are an expert Latin lexicographer. Your sole output MUST be a strict JSON object that adheres to the requested schema. Do not include any external commentary, explanation, or markdown formatting."

EXPECTED_FIELDS = [
    'lemma_clean',
    'lemma_macron',
    'full_headword_source',
    'pos',
    'semantic_group',
    'rank',
    'definition_source'
]

# ================= 数据库 =================
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
                print(f"[{time.strftime('%H:%M:%S')}] DB Wrote Batch: {len(batch_to_write)} entries.")
                
            except Exception as e:
                print(f"⚠️ DB Error: {e}")
                batch_buffer = batch_to_write + batch_buffer
        
        queue.task_done()

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

# ================= Latin Prompt =================
def get_latin_prompt(metadata):
    word_macron = metadata['lemma_macron']
    word_clean = metadata['lemma_clean']
    
    primary_definition = metadata.get('definition_source', '') 
    frequency_rank = metadata.get('frequency_rank', 'N/A')
    
    pos_type = metadata['pos'].lower()
    is_verb = 'verb' in pos_type or 'v.' in pos_type
    
    return f"""
    ### SYSTEM ROLE
    You are a strict, academic Latin Lexicography Database Expert. Your goal is to generate high-precision, structured data for a Latin dictionary application.
    
    ### INPUT DATA (THE SOURCE OF TRUTH)
    * **Target Word**: "{word_macron}" (Clean: "{word_clean}")
    * **Part of Speech**: "{metadata['pos']}"
    * **Primary Definition Anchor**: "{primary_definition}" 
      (⚠️ CRITICAL: Generated definitions MUST align with this anchor. Do not invent unrelated meanings.)
    * **Metadata**: Rank: {frequency_rank}, Semantic Group: {metadata.get('semantic_group', 'General')}
    
    ### STRICT OUTPUT REQUIREMENTS
    1. **Format**: Return ONLY valid JSON. No Markdown block symbols.
    2. **Language**: 
       - Definitions: Simplified Chinese (简体中文).
       - Linguistic Terms: English (e.g., "Accusative", "Subjunctive").
       - Examples: Latin + Chinese(Simplified Chinese).

    ### CONTENT GENERATION RULES
    1. **Principal Parts**: Extract cleanly from source.
    2. **Macrons**: 
       - `word`, `morphology`, `paradigm`, and `examples` MUST have macrons (e.g., 'amō').
       - `search_keywords` and `lemma_clean` MUST NOT have macrons (e.g., 'amo').
    3. **Inflection Paradigm (CRITICAL)**:
       - **IF VERB**: Generate `conjugation` (Pres/Perf/Fut Active Indicative).
       - **IF NOUN/ADJ**: Generate `declension` (Nom/Gen/Dat/Acc/Abl/Voc for Sg/Pl).
       - **IF PREP/ADV**: Set this field to `null`.
    4. **Cultural Context**: Provide subtle meanings and historical insights.

    ### JSON TEMPLATE (FILL THIS EXACT STRUCTURE)
    {{
      "word": "{word_macron}",
      "lemma_clean": "{word_clean}",
      "part_of_speech": "{metadata['pos']}",
      
      "morphology_meta": {{
         "full_headword_source": "{metadata['full_headword_source']}",
         "principal_parts_clean": ["PART_1", "PART_2", "PART_3", "PART_4"],
         "grammatical_info": "STRING (e.g., 'F. 1st Declension' or '3rd Conjugation, Transitive')"
      }},

      // 🔥 SMART PARADIGM: Adapts structure based on POS
      "inflection_paradigm": {{
          // OPTION A: If Verb
          "type": "conjugation",
          "present_active": {{ "1sg": "...", "2sg": "...", "3sg": "...", "1pl": "...", "2pl": "...", "3pl": "..." }},
          "perfect_active": {{ "1sg": "...", "3sg": "...", "3pl": "..." }}, // Keep it concise
          "future_active": {{ "1sg": "...", "3sg": "...", "3pl": "..." }}
          
          // OPTION B: If Noun/Adjective
          // "type": "declension",
          // "singular": {{ "nom": "...", "gen": "...", "dat": "...", "acc": "...", "abl": "..." }},
          // "plural": {{ "nom": "...", "gen": "...", "dat": "...", "acc": "...", "abl": "..." }}
          
          // OPTION C: If Immutable
          // null
      }},
      
      "usage_meta": {{
         "frequency_rank": "{frequency_rank}", 
         "semantic_group": "{metadata.get('semantic_group', 'General')}",
         "usage_commentary": "STRING (Chinese analysis)"
      }},

      "cultural_context": {{
         "en": "STRING or null",
         "cn": "STRING (Chinese) or null"
      }},

      "romance_descendants": {{
         "it": "STRING or null", 
         "es": "STRING or null", 
         "fr": "STRING or null", 
         "pt": "STRING or null"
      }},

      "search_keywords": [
         "{word_clean}", 
         "GENERATED_INFLECTIONS_NO_MACRONS"
      ],

      "etymology_depth": {{
         "root_language": "STRING (e.g., PIE)",
         "root_form": "STRING",
         "cognates_english": "STRING"
      }},
      
      "senses": [
         {{
             "pos_specific": "STRING (e.g., V. tr.)",
             "definition_cn": "STRING",
             "governing_rules": "STRING (Grammar case requirements)",
             "core_concept": {{ "en": "STRING", "cn": "STRING" }},
             "antonyms": ["LATIN_WORD (English Def)"],
             "synonym_discrimination": "STRING",
             "examples": [
                 {{ "lat": "Authentic sentence with macrons", "cn": "Translation in Simplified Chinese" }}
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
async def worker(sem, client, queue, metadata):
    word = metadata['lemma_macron'] 
    async with sem:
        last_error = None
        
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": SYSTEM_MESSAGE_CONTENT},
                            {"role": "user", "content": get_latin_prompt(metadata)}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1
                    ),
                    timeout=TIMEOUT
                )
                
                raw_content = response.choices[0].message.content

                data, data_str = robust_json_parser(raw_content)
                
                # 提取关键词列表 for DB indexing
                keywords = data.get("search_keywords", [])
                
                # 确保主词条也在关键词列表中
                lemma_clean = metadata['lemma_clean']
                if lemma_clean not in keywords:
                    keywords.append(lemma_clean)
                    
                keywords_str = " ".join([str(x) for x in keywords]).lower()
                
                await queue.put((word, keywords_str, data_str))
                print(f"✅ {word} ({metadata['pos']}) | 任务耗时: {response.usage.total_tokens} tokens")
                return
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                wait_time = (2 ** attempt) + random.uniform(0, 1)

                if "429" in error_str:
                    print(f"⏳ 限流等待: {word}. 等待 {wait_time:.1f}s")
                    await asyncio.sleep(wait_time) 
                elif "timeout" in error_str.lower():
                    print(f"⏳ 超时错误: {word}. 尝试重试...")
                    await asyncio.sleep(wait_time)
                elif "JSONDecodeError" in error_str or "JSON_BLOCK_NOT_FOUND" in error_str or "JSON_PARSE_FAIL" in error_str:
                    print(f"⚠️ JSON 严重错误: {word} | {e}. 等待 1s")
                    await asyncio.sleep(1)
                else:
                    print(f"❌ Worker 错误: {word} | {e}. 等待 {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
        
        print(f"❌ {word} 失败 | 最终原因: {last_error}")
        
# ================= 主程序 =================
async def main():
    conn = sqlite3.connect(DB_NAME)
    try:
        existing = set(row[0] for row in conn.execute("SELECT word FROM dictionary"))
    except sqlite3.OperationalError:
        existing = set()
    conn.close()
    print(f"库中已有 {len(existing)} 个词。")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, SOURCE_FILE)
    if not os.path.exists(file_path):
        print(f"❌ 找不到 {SOURCE_FILE}！请确保文件存在。")
        return

    tasks_metadata = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing_fields = [field for field in EXPECTED_FIELDS if field not in header]
            if missing_fields:
                print(f"⚠️ CSV 列缺失: {missing_fields}。现有列: {header}")

            for row in reader:
                if not row:
                    continue

                lemma_clean = (row.get('lemma_clean') or '').strip()
                lemma_macron = (row.get('lemma_macron') or '').strip()
                full_headword = (row.get('full_headword_source') or '').strip()
                pos = (row.get('pos') or '').strip()
                semantic_group = (row.get('semantic_group') or '').strip()
                frequency_rank = (row.get('rank') or row.get('frequency_rank') or '').strip()
                definition_source = (row.get('definition_source') or '').strip()

                if not lemma_clean and not lemma_macron:
                    print(f"跳过缺少核心词形的行: {row}")
                    continue

                # 如果缺少带长音符的版本，退回到无长音形式
                if not lemma_macron:
                    lemma_macron = lemma_clean
                if not lemma_clean:
                    lemma_clean = lemma_macron

                if not full_headword:
                    full_headword = lemma_macron

                transformed_metadata = {
                    'lemma_macron': lemma_macron,
                    'lemma_clean': lemma_clean,
                    'full_headword_source': full_headword,
                    'pos': pos,
                    'semantic_group': semantic_group,
                    'frequency_rank': frequency_rank,
                    'definition_source': definition_source
                }

                if transformed_metadata['lemma_macron'] not in existing:
                    tasks_metadata.append(transformed_metadata)

    except Exception as e:
        print(f"❌ 读取 CSV 文件时发生错误: {e}")
        return

    if not tasks_metadata:
        print("数据库已是最新，无需操作！")
        return
        
    print(f"剩余任务: {len(tasks_metadata)} 个。使用模型: {MODEL_NAME} | 并发: {CONCURRENCY}")

    queue = asyncio.Queue()
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)
    db_task = asyncio.create_task(db_writer(queue))

    print(f"正在创建 {len(tasks_metadata)} 个 API 任务...")
    workers = [
        asyncio.create_task(worker(sem, client, queue, metadata))
        for metadata in tasks_metadata
    ]

    print(f"🏃 开始处理... (并发上限 {CONCURRENCY})")
    await asyncio.gather(*workers)
    
    print("\n✅ 所有 API worker 均已完成。")

    print("⏳ 正在等待数据库队列清空...")
    await queue.join()

    print("⚠ 发送关闭信号到数据库写入线程...")
    await queue.put(None)
    await db_task
    
    print("拉丁词典构建完成！")

if __name__ == "__main__":
    asyncio.run(main())