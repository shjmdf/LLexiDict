def clean_corpus(input_file, output_file,limit=None):
    print(f"🧹 正在清洗 {input_file} ...")
    
    count = 0
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8') as f_out:
        
        for line in f_in:
            if limit and count >= limit:
                break
            text = line.strip()
            
            if not text:
                continue
            
            if text.startswith("#!"):
                continue
            
            # 统一转小写
            text = text.lower()
            
            f_out.write(text + '\n')
            count += 1
            
    print(f"✨ 清洗完成！保留了 {count} 个单词，已保存为 {output_file}")

if __name__ == "__main__":
    clean_corpus("wiki-100k.txt", "wiki-100k-clean.txt",limit=55000)