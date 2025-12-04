import os
import json
import asyncio
import sqlite3
from openai import AsyncOpenAI

# ================= 配置 =================
API_KEY = "" 
BASE_URL = ""
MODEL_NAME = ""


CONCURRENCY = 64

SOURCE_FILE = "count_1w_20k_english_clean.txt"
DB_NAME = "english_dictionary.db"

# ================= 数据库 =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary (
            word TEXT PRIMARY KEY,
            data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def word_exists(word):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM dictionary WHERE word = ?", (word,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_word(word, data_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO dictionary (word, data) VALUES (?, ?)", (word, data_str))
    conn.commit()
    conn.close()

# ================= 英语 Prompt =================
def get_english_prompt(word):
    return f"""
    Role: Expert Lexicographer & Linguist. Target: English word "{word}".
    Task: Create a deep, insightful entry for an advanced learner (C1/C2 level).
    
    CRITICAL INSTRUCTIONS FOR DEPTH:
    1. **Collocations**: Do NOT just give 2. Provide **4-6 high-frequency items** per sense. For verbs, include **prepositions** (e.g., 'rely ON') and **idioms**. For adjectives, include **adverbs** (e.g., 'significantly shorter').
    2. **Core Image**: Abstract the meaning. Don't just repeat the definition. Find the **underlying logical concept** that connects the literal and metaphorical uses.
    3. **Synonym Discrimination**: Don't just say "X is different from Y". Explain the **Nuance**, **Register** (formal/casual), or **Connotation** (positive/negative). Why would a native speaker choose THIS word?
    4. **Senses**: Cover distinct meanings. If a word has a specific "contextual meaning" (e.g. 'run' for software), include it.

    Output Format: STRICT JSON (No Markdown).
    
    JSON Structure Requirement:
    {{
      "word": "{word}",
      "ipa": "IPA pronunciation (US/UK)",
      "etymology": "Brief origin + The root logic (e.g., Latin 'portare' -> to carry -> portable)",
      "senses": [  // List the top 3-5 distinct senses.
        {{
          "pos": "Part of Speech",
          "definition_cn": "Chinese Definition (Precise & Contextual), not a direct translation.",
          "core_image": "The 'Soul' of the definition (e.g. 'Violent separation' for 'break'), be insightful and accurate, detailed and explicit.",
          "collocations": [
            "set collocations or combinations 1 (e.g., 'run a risk')",
            "Verb + Preposition (e.g., 'run into')",
            "Adverb + Verb / Adj + Noun",
            "Idiomatic expression",
            "Other common idioms or expressions"
          ],
          "synonym_discrimination": "Compare with [Synonym]. Explain the unique 'flavor' or specific usage scenario of '{word}'.",
          "examples": [
            {{ "en": "A sentence showing typical usage.", "cn": "Natural Chinese translation." }}
          ]
        }}
      ]
    }}
    """

# ================= 异步 Worker =================
async def process_word(sem, client, word):
    async with sem:
        if word_exists(word):
            print(f"⚠[已存在] {word}")
            return

        print(f"[生成中] {word} ...")
        
        try:
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a dictionary generator. Output valid JSON only."},
                    {"role": "user", "content": get_english_prompt(word)}
                ],
                response_format={"type": "json_object"}, # 强制 JSON
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            
            json.loads(content) 
            
            save_word(word, content)
            print(f"✅ [成功] {word}")
            
        except Exception as e:
            print(f"❌ [失败] {word}: {e}")

# ================= 主程序 =================
async def main():
    init_db()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, SOURCE_FILE)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        words = [line.strip() for line in f if line.strip()]

    print(f"任务开始：共 {len(words)} 个单词。")
    print(f"数据库：{DB_NAME}")
    print("--------------------------------")

    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    tasks = []
    for word in words:
        tasks.append(process_word(sem, client, word))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())