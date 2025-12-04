import sqlite3

DB_NAME = "english_dictionary.db"

def rollback_last_entries(count=60):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print(f"准备删除最近写入的 {count} 条数据...")
    
    try:
        cursor.execute("SELECT COUNT(*) FROM dictionary")
        total_before = cursor.fetchone()[0]
        print(f"当前总数: {total_before}")

        sql = f"""
        DELETE FROM dictionary 
        WHERE word IN (
            SELECT word FROM dictionary 
            ORDER BY created_at DESC 
            LIMIT {count}
        )
        """
        cursor.execute(sql)
        deleted_count = cursor.rowcount
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM dictionary")
        total_after = cursor.fetchone()[0]
        
        print(f"✅ 成功删除: {deleted_count} 条")
        print(f"剩余总数: {total_after}")
        
    except Exception as e:
        print(f"❌ 删除失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    rollback_last_entries(200)