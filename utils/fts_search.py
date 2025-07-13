"""
Модуль для полнотекстового поиска с использованием FTS5.
"""
import sqlite3
import logging
from typing import List, Dict, Any
import os
from config import DEFAULT_TOP_K

# Настраиваем логгер для модуля FTS поиска
fts_logger = logging.getLogger('fts_search')

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def fts_search(query: str, limit: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    """
    Выполняет полнотекстовый поиск по FTS5 индексу.
    
    Args:
        query: Поисковый запрос
        limit: Максимальное количество результатов
        
    Returns:
        Список словарей с информацией о найденных чанках
    """
    results = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование FTS таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
        if not cursor.fetchone():
            fts_logger.error("FTS таблица 'chunks_fts' не найдена. Запустите: python build_fts_index.py")
            return results
        
        # Подготавливаем запрос для FTS поиска
        escaped_query = query.replace('"', '""')
        
        # SQL запрос для FTS поиска
        sql = """
        SELECT 
            chunks.chunk_id,
            chunks.document_id,
            chunks.doc_type_short,
            chunks.chunk_text,
            chunks.id,
            bm25(chunks_fts) AS rank,
            snippet(chunks_fts, 0, '<b>', '</b>', '...', 10) AS snippet
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """
        
        cursor.execute(sql, (escaped_query, limit))
        rows = cursor.fetchall()
        
        # Получаем названия столбцов
        column_names = [description[0] for description in cursor.description]
        
        # Преобразуем результаты в список словарей
        for row in rows:
            result = {}
            for i, value in enumerate(row):
                result[column_names[i]] = value
            
            # Добавляем поля для совместимости с векторным поиском
            result['id'] = result['chunk_id']
            result['content'] = result['chunk_text']
            result['text'] = result['chunk_text']
            result['doc_id'] = result['document_id']
            result['document_title'] = result['document_id']
            result['similarity'] = abs(result['rank'])
            result['search_type'] = 'fts'
            
            results.append(result)
        
        fts_logger.info(f"FTS поиск по запросу '{query}' нашел {len(results)} результатов")
        
    except sqlite3.Error as e:
        fts_logger.error(f"Ошибка SQLite при FTS поиске: {str(e)}")
    except Exception as e:
        fts_logger.error(f"Неожиданная ошибка при FTS поиске: {str(e)}", exc_info=True)
    finally:
        if conn:
            conn.close()
    
    return results

def merge_results(vec_results: List[Dict[str, Any]], fts_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет результаты векторного и FTS поиска, убирая дубли.
    
    Args:
        vec_results: Результаты векторного поиска
        fts_results: Результаты FTS поиска
        
    Returns:
        Объединенный список результатов без дублей
    """
    seen_ids = set()
    merged_results = []
    
    # Сначала добавляем результаты векторного поиска (приоритет)
    for result in vec_results:
        chunk_id = result.get('chunk_id', result.get('id'))
        if chunk_id and chunk_id not in seen_ids:
            result['search_type'] = 'vector'
            merged_results.append(result)
            seen_ids.add(chunk_id)
    
    # Затем добавляем результаты FTS поиска (дополнительные)
    for result in fts_results:
        chunk_id = result.get('chunk_id', result.get('id'))
        if chunk_id and chunk_id not in seen_ids:
            merged_results.append(result)
            seen_ids.add(chunk_id)
    
    fts_logger.info(f"Объединено {len(merged_results)} уникальных результатов (векторный: {len(vec_results)}, FTS: {len(fts_results)})")
    
    return merged_results

if __name__ == "__main__":
    # Тестирование
    test_queries = ["диагностика", "анализ", "лечение"]
    
    print("🔍 ТЕСТИРОВАНИЕ FTS ПОИСКА")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i}. Запрос: '{query}'")
        print("-" * 40)
        
        results = fts_search(query, limit=3)
        
        if results:
            for j, result in enumerate(results, 1):
                doc_id = result.get('document_id', 'N/A')
                doc_type = result.get('doc_type_short', 'N/A')
                rank = result.get('rank', 0)
                snippet = result.get('snippet', '')
                
                print(f"   {j}. Документ: {doc_id} ({doc_type})")
                print(f"      Релевантность: {rank:.3f}")
                print(f"      Отрывок: {snippet}")
                print()
        else:
            print("   ❌ Результаты не найдены")
            print() 