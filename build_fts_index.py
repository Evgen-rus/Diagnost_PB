"""
Скрипт для построения FTS5 индекса на основе чанков из базы данных.

Этот скрипт выполняет следующие действия:
1. Подключается к существующей базе данных knowledge_base_v2.db
2. Создает FTS5 виртуальную таблицу для полнотекстового поиска
3. Заполняет FTS индекс из существующих данных таблицы chunks
4. Оптимизирует индекс для быстрого поиска

Использование:
    python build_fts_index.py

Примечание:
    FTS5 индекс создается независимо от FAISS индекса и не влияет на
    существующую векторную систему поиска. Используется токенизатор
    unicode61 для поддержки русского языка.
"""
import os
import sqlite3
import logging
import time
from pathlib import Path

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('build_fts_index')

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def create_fts_index():
    """
    Создает FTS5 индекс из существующей таблицы chunks.
    
    Функция создает виртуальную таблицу FTS5, связанную с существующей
    таблицей chunks, заполняет её данными и оптимизирует для поиска.
    """
    logger.info("Начинаем создание FTS5 индекса...")
    
    # Проверяем существование базы данных
    if not Path(DB_PATH).exists():
        logger.error(f"База данных не найдена: {DB_PATH}")
        logger.error("Сначала запустите: python load_excel_to_vectordb.py")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы chunks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
        if not cursor.fetchone():
            logger.error("Таблица 'chunks' не найдена в базе данных")
            return False
        
        # Проверяем количество записей в таблице chunks
        cursor.execute("SELECT COUNT(*) FROM chunks")
        count = cursor.fetchone()[0]
        if count == 0:
            logger.error("В таблице 'chunks' нет записей для индексации")
            return False
        
        logger.info(f"Найдено {count} записей в таблице 'chunks'")
        
        # Удаляем существующий FTS индекс если он есть
        cursor.execute("DROP TABLE IF EXISTS chunks_fts")
        logger.info("Очищен существующий FTS индекс")
        
        # Создаем FTS5 виртуальную таблицу
        cursor.execute('''
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_text,
                content='chunks',
                content_rowid='id',
                tokenize="unicode61 remove_diacritics 2"
            );
        ''')
        logger.info("Создана FTS5 виртуальная таблица")
        
        # Заполняем FTS индекс из существующих данных
        logger.info("Заполняем FTS индекс данными из таблицы chunks...")
        cursor.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');")
        logger.info("FTS индекс заполнен данными")
        
        # Оптимизируем индекс для быстрого поиска
        logger.info("Оптимизируем FTS индекс...")
        cursor.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize');")
        logger.info("FTS индекс оптимизирован")
        
        # Сохраняем изменения
        conn.commit()
        
        # Проверяем созданный индекс
        cursor.execute("SELECT COUNT(*) FROM chunks_fts")
        fts_count = cursor.fetchone()[0]
        logger.info(f"FTS индекс содержит {fts_count} записей")
        
        if fts_count != count:
            logger.warning(f"Несоответствие количества записей: chunks={count}, fts={fts_count}")
        
        logger.info("✅ FTS5 индекс успешно создан и готов к использованию")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Ошибка SQLite при создании FTS индекса: {str(e)}")
        return False
    
    except Exception as e:
        logger.error(f"Неожиданная ошибка при создании FTS индекса: {str(e)}", exc_info=True)
        return False
    
    finally:
        if conn:
            conn.close()

def test_fts_search():
    """
    Тестирует созданный FTS индекс с простым запросом.
    """
    logger.info("Тестируем FTS индекс...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Тестовый запрос
        test_query = "диагностика"
        
        sql = """
        SELECT 
            chunks.chunk_id,
            chunks.document_id,
            chunks.doc_type_short,
            snippet(chunks_fts, 0, '<b>', '</b>', '...', 10) AS snippet,
            bm25(chunks_fts) AS rank
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT 3
        """
        
        cursor.execute(sql, (test_query,))
        results = cursor.fetchall()
        
        logger.info(f"Тестовый запрос '{test_query}' вернул {len(results)} результатов:")
        for i, (chunk_id, doc_id, doc_type, snippet, rank) in enumerate(results, 1):
            logger.info(f"  {i}. {chunk_id} ({doc_type}) - Релевантность: {rank:.3f}")
            logger.info(f"     Отрывок: {snippet}")
        
        conn.close()
        
        if results:
            logger.info("✅ FTS индекс работает корректно")
        else:
            logger.warning("⚠️ FTS индекс не вернул результатов для тестового запроса")
            
    except Exception as e:
        logger.error(f"Ошибка при тестировании FTS индекса: {str(e)}")

def main():
    """
    Основная функция для создания FTS5 индекса.
    """
    print("🔍 СОЗДАНИЕ FTS5 ИНДЕКСА")
    print("=" * 60)
    print(f"📄 База данных: {DB_PATH}")
    print("🔤 Токенизатор: unicode61 (поддержка русского языка)")
    print("=" * 60)
    
    # Замеряем время выполнения
    start_time = time.time()
    
    # Создаем FTS индекс
    success = create_fts_index()
    
    if success:
        # Тестируем созданный индекс
        test_fts_search()
        
        # Выводим информацию о времени выполнения
        elapsed_time = time.time() - start_time
        print(f"\n✅ FTS5 индекс создан за {elapsed_time:.2f} секунд")
        print("📋 Следующие шаги:")
        print("  1. Запустите: python -m utils.fts_search (после создания модуля)")
        print("  2. Интегрируйте гибридный поиск в бота")
        print("  3. Протестируйте качество поиска")
        
    else:
        print("\n❌ ОШИБКА ПРИ СОЗДАНИИ FTS ИНДЕКСА!")
        print("📋 Проверьте логи для получения подробностей")

if __name__ == "__main__":
    main() 