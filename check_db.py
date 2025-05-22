import sqlite3
import os

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def check_tables():
    """
    Проверяет таблицы в базе данных.
    """
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Таблицы в базе данных:")
        for table in tables:
            print(f"  {table[0]}")
        
        print("\n--- ТАБЛИЦА chunks ---")
        check_chunks_table(conn)
        
        print("\n--- ТАБЛИЦА vector_map ---")
        check_vector_map_table(conn)
        
    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {str(e)}")
    
    finally:
        if conn:
            conn.close()

def check_chunks_table(conn):
    """
    Проверяет таблицу chunks в базе данных.
    """
    try:
        cursor = conn.cursor()
        
        # Проверяем существование таблицы chunks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
        if not cursor.fetchone():
            print("Таблица 'chunks' не существует в базе данных.")
            return
        
        # Проверяем количество записей
        cursor.execute("SELECT COUNT(*) FROM chunks")
        count = cursor.fetchone()[0]
        print(f"Количество записей в таблице 'chunks': {count}")
        
        # Получаем структуру таблицы
        cursor.execute("PRAGMA table_info(chunks)")
        columns = cursor.fetchall()
        print("\nСтруктура таблицы 'chunks':")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Получаем названия столбцов
        cursor.execute("SELECT * FROM chunks LIMIT 1")
        col_names = [description[0] for description in cursor.description]
        print("\nНазвания столбцов:")
        print(col_names)
        
        # Получаем пример данных
        if count > 0:
            cursor.execute("SELECT * FROM chunks LIMIT 2")
            rows = cursor.fetchall()
            print("\nПример данных (до 2 записей):")
            for row in rows:
                print(f"  Строка: {row}")
                
        # Проверяем SQL-запрос, который используется в vector_search.py
        try:
            cursor.execute("SELECT id, content FROM chunks LIMIT 1")
            print("\nЗапрос 'SELECT id, content FROM chunks' выполнен успешно")
            col_names = [description[0] for description in cursor.description]
            print(f"Названия столбцов: {col_names}")
        except sqlite3.Error as e:
            print(f"\nОшибка при выполнении запроса 'SELECT id, content FROM chunks': {str(e)}")
            
            # Проверяем, есть ли похожие столбцы
            cursor.execute("PRAGMA table_info(chunks)")
            columns = cursor.fetchall()
            id_columns = [col[1] for col in columns if 'id' in col[1].lower()]
            content_columns = [col[1] for col in columns if 'content' in col[1].lower() or 'text' in col[1].lower()]
            
            print(f"Столбцы с 'id' в названии: {id_columns}")
            print(f"Столбцы с 'content' или 'text' в названии: {content_columns}")
        
    except sqlite3.Error as e:
        print(f"Ошибка при работе с таблицей chunks: {str(e)}")

def check_vector_map_table(conn):
    """
    Проверяет таблицу vector_map в базе данных.
    """
    try:
        cursor = conn.cursor()
        
        # Проверяем существование таблицы vector_map
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vector_map'")
        if not cursor.fetchone():
            print("Таблица 'vector_map' не существует в базе данных.")
            return
        
        # Проверяем количество записей
        cursor.execute("SELECT COUNT(*) FROM vector_map")
        count = cursor.fetchone()[0]
        print(f"Количество записей в таблице 'vector_map': {count}")
        
        # Получаем структуру таблицы
        cursor.execute("PRAGMA table_info(vector_map)")
        columns = cursor.fetchall()
        print("\nСтруктура таблицы 'vector_map':")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Получаем пример данных
        if count > 0:
            cursor.execute("SELECT * FROM vector_map LIMIT 2")
            rows = cursor.fetchall()
            print("\nПример данных (до 2 записей):")
            for row in rows:
                print(f"  Строка: {row}")
        
    except sqlite3.Error as e:
        print(f"Ошибка при работе с таблицей vector_map: {str(e)}")

if __name__ == "__main__":
    check_tables() 