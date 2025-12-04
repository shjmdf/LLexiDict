import os

def clean_english_freq(input_file, output_file, limit=40000):
    print(f"🧹 正在清洗 {input_file} ...")
    
    count = 0
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            if count >= limit:
                break
            
            parts = line.strip().split()
            
            if parts:
                word = parts[0]
                # filter
                if word.isalpha():
                    if len(word) > 1 or word.lower() in ['a', 'i']:
                        f_out.write(word + '\n')
                        count += 1
            
    print(f"✅ 完成！提取了前 {count} 个高频词，存为 {output_file}")

if __name__ == "__main__":
    clean_english_freq("count_1w.txt", "count_1w_20k_english_clean.txt", limit=20000)