import csv
import os

# ================= 配置 =================
INPUT_FILE = "Lexique383.tsv"
OUTPUT_FILE = "list_french.txt"
LIMIT = 30000  # first 30k

def clean_lexique():    
    # { "lemma": total_frequency }
    lemma_stats = {}

    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:

                lemma = row['lemme']
                ortho = row['ortho']
                

                try:
                    freq = float(row['freqfilms2'])
                except ValueError:
                    freq = 0.0
                

                if not lemma.replace('-', '').replace(' ', '').isalpha():
                    continue
                
                if lemma in lemma_stats:
                    lemma_stats[lemma] += freq
                else:
                    lemma_stats[lemma] = freq

    except FileNotFoundError:
        print(f"❌ 错误：找不到 {INPUT_FILE}。请确认文件名是否正确。")
        return

    sorted_lemmas = sorted(lemma_stats.items(), key=lambda x: x[1], reverse=True)

    count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for lemma, freq in sorted_lemmas:
            if count >= LIMIT:
                break
            
            if (len(lemma) > 1 or lemma in ['a', 'y', 'à', 'ô']) and freq > 0.01:
                f.write(lemma + '\n')
                count += 1

    print(f"已生成 {OUTPUT_FILE}，包含 {count} 个核心法语原形。")
    print(f"频率最高的 5 个词: {[w[0] for w in sorted_lemmas[:5]]}")

if __name__ == "__main__":
    clean_lexique()