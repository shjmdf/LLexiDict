import pandas as pd
import unicodedata
import os

def strip_macrons(text):
    """移除拉丁语长音符号 (ā -> a)"""
    if not isinstance(text, str):
        return str(text)
    # 1. NFD 分解
    normalized = unicodedata.normalize('NFD', text)
    # 2. 过滤长音符 (Mn)
    shaved = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return unicodedata.normalize('NFC', shaved)

def load_latin_data(file_path):
    print(f"🏛️ 正在读取 DCC 拉丁语数据: {file_path} ...")
    
    if not os.path.exists(file_path):
        print(f"❌ 错误: 找不到文件 {file_path}")
        return []

    df = pd.read_csv(file_path, encoding='utf-8') 
    df.fillna('', inplace=True)
    
    tasks = []
    for _, row in df.iterrows():
        if not row['Headword']: continue

        raw_headword = str(row['Headword']).strip() # 例如: "abeō -īre -iī -itum"
        
        lemma_macron = raw_headword.split(' ')[0].replace(',', '').strip()

        lemma_clean = strip_macrons(lemma_macron)
        
        # 3. 打包元数据
        metadata = {
            "lemma_clean": lemma_clean,              # 主键 (放在前面方便看)
            "lemma_macron": lemma_macron,            # 显示用
            "full_headword_source": raw_headword,    # 完整原字符串 (给 LLM 参考变位)
            
            "pos": row.get('Part of Speech', ''),
            "semantic_group": row.get('Semantic Group', ''),
            "rank": row.get('Frequency Rank', 0),
            "definition_source": row.get('Definition', '')
        }
        
        tasks.append(metadata)
        
    print(f"✅ 已加载 {len(tasks)} 个拉丁语词条任务。")
    return tasks

def save_to_csv(task_list, output_file):
    if not task_list:
        print("⚠️ 没有数据可保存。")
        return

    df = pd.DataFrame(task_list)
    
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"📁 清洗后的数据已保存到: {output_file}")
    print(f"   预览:\n{df.head(3)}")

if __name__ == "__main__":
    INPUT_FILE = "dcc-latin-core-list.csv" 
    OUTPUT_FILE = "latin_data_cleaned.csv"
    
    tasks = load_latin_data(INPUT_FILE)
    save_to_csv(tasks, OUTPUT_FILE)