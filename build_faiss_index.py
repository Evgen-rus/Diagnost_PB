"""
Скрипт для построения индекса FAISS на основе чанков из базы данных.

Этот скрипт выполняет следующие действия:
1. Подключается к базе данных SQLite
2. Извлекает чанки документов
3. Создает векторные представления с помощью OpenAI API
4. Строит индекс FAISS с использованием косинусного сходства
5. Сохраняет индекс в файл

Использование:
    python build_faiss_index.py

Примечание:
    Требуется наличие API ключа OpenAI в переменной окружения OPENAI_API_KEY
    или в файле .env в корневой директории проекта.
    
    Индекс использует косинусное сходство (IndexFlatIP) для лучшего 
    семантического поиска с эмбеддингами OpenAI.
"""
import os
import sqlite3
import logging
from dotenv import load_dotenv
import time

from utils.vector_search import FAISSVectorStore, batch_get_embeddings

# Загружаем переменные окружения
load_dotenv()

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('build_faiss_index')

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def main():
    """
    Основная функция для построения индекса FAISS с косинусным сходством.
    """
    # Проверяем наличие API ключа OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("API ключ OpenAI не найден. Установите переменную окружения OPENAI_API_KEY или добавьте ее в файл .env")
        return
    
    # Подключаемся к базе данных
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы chunks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
        if not cursor.fetchone():
            # Таблица chunks уже должна существовать в базе данных
            logger.error("Таблица 'chunks' не найдена в базе данных")
            return
        
        # Проверяем количество записей в таблице chunks
        cursor.execute("SELECT COUNT(*) FROM chunks")
        count = cursor.fetchone()[0]
        if count == 0:
            logger.error("В таблице 'chunks' нет записей для индексации")
            return
        
        logger.info(f"Найдено {count} записей в таблице 'chunks'")
        
        # Создаем экземпляр FAISSVectorStore
        vector_store = FAISSVectorStore(embedding_dimension=1536)
        
        # Замеряем время выполнения
        start_time = time.time()
        
        # Строим индекс
        logger.info("Начинаем построение индекса FAISS с косинусным сходством...")
        logger.info("Используется IndexFlatIP для семантического поиска с эмбеддингами OpenAI")
        vector_store.build_index(conn, lambda texts: batch_get_embeddings(texts), batch_size=20)
        
        # Выводим информацию о времени выполнения
        elapsed_time = time.time() - start_time
        logger.info(f"Построение индекса с косинусным сходством завершено за {elapsed_time:.2f} секунд")
        logger.info("Индекс оптимизирован для поиска по смыслу, а не по длине текста")
        
    except Exception as e:
        logger.error(f"Ошибка при построении индекса: {str(e)}", exc_info=True)
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 