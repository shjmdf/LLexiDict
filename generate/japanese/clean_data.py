import csv
import os

INPUT_FILE = "jpdb_v2.2_freq_list_2024-10-13.csv"
OUTPUT_FILE = "jpdb-clean.txt"

def clean_jlpt_csv(total):
    print(f"🇯🇵 正在解析 CSV 文件: {INPUT_FILE} ...")
    
    unique_words = []
    seen = set()
    try:
        num=0

        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
        

            for row in reader:
                if num>=total:
                    break
                num+=1
                if not row: continue
                
                word = row[0].strip()
                
                # 过滤逻辑：
                # 1. 跳过空字符串
                # 2. 去重 (seen set)
                # 3. 过滤掉非日语字符 (可选，防止混入英文表头)
                if word and word not in seen:
                    # 简单的日语字符检查（包含假名或汉字）
                    # if any('\u3040' <= c <= '\u9faf' for c in word): 
                    unique_words.append(word)
                    seen.add(word)

    except FileNotFoundError:
        print(f"找不到文件: {INPUT_FILE}")
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_words))

    print(f"清洗完成！")
    print(f"已提取 {len(unique_words)} 个词条至: {OUTPUT_FILE}")
    print(f"预览前 5 个: {unique_words[:5]}")

if __name__ == "__main__":
    clean_jlpt_csv(15000)