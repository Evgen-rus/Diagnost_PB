"""
Модуль для гибридного поиска, объединяющего векторный и FTS поиск.

Предоставляет функции для получения контекста из обеих систем поиска
и их объединения в единый результат.
"""
import sqlite3
import logging
from typing import List, Dict, Any, Optional
import os
from config import DEFAULT_TOP_K, MAX_CONTEXT_TOKENS

# Импортируем функции из существующих модулей
from utils.vector_search import search_relevant_chunks, get_chunks_by_ids
from utils.fts_search import fts_search, merge_results

# Настраиваем логгер для модуля гибридного поиска
hybrid_logger = logging.getLogger('hybrid_search')

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def get_hybrid_context(query: str, vector_store, conn: sqlite3.Connection, top_k: int = DEFAULT_TOP_K, max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """
    Получает контекст, объединяя результаты векторного и FTS поиска.
    
    Args:
        query: Поисковый запрос
        vector_store: Экземпляр FAISSVectorStore для векторного поиска
        conn: Соединение с базой данных SQLite
        top_k: Количество результатов для каждого типа поиска
        max_tokens: Максимальное количество токенов для контекста
        
    Returns:
        Строка с контекстом, сформированная из найденных чанков
    """
    hybrid_logger.info(f"Начинаем гибридный поиск по запросу: '{query}'")
    
    # Результаты поиска
    vec_results = []
    fts_results = []
    
    # 1. Выполняем векторный поиск (если vector_store доступен)
    if vector_store:
        try:
            vec_results = search_relevant_chunks(query, vector_store, conn, top_k)
            hybrid_logger.info(f"Векторный поиск нашел {len(vec_results)} результатов")
        except Exception as e:
            hybrid_logger.error(f"Ошибка векторного поиска: {str(e)}")
    else:
        hybrid_logger.warning("Векторное хранилище недоступно, используется только FTS поиск")
    
    # 2. Выполняем FTS поиск
    try:
        fts_results = fts_search(query, limit=top_k)
        hybrid_logger.info(f"FTS поиск нашел {len(fts_results)} результатов")
    except Exception as e:
        hybrid_logger.error(f"Ошибка FTS поиска: {str(e)}")
    
    # 3. Объединяем результаты
    merged_results = merge_results(vec_results, fts_results)
    hybrid_logger.info(f"Объединено {len(merged_results)} уникальных результатов")
    
    # 4. Формируем контекст
    if not merged_results:
        hybrid_logger.warning("Гибридный поиск не нашел результатов")
        return ""
    
    context_parts = []
    
    for chunk in merged_results:
        # Добавляем информацию о документе и типе поиска
        search_type = chunk.get('search_type', 'unknown')
        search_type_label = '🔍 Векторный' if search_type == 'vector' else '📝 Текстовый'
        
        document_info = f"{search_type_label} поиск - Документ: {chunk.get('doc_id', chunk.get('document_title', chunk.get('document_id', 'Неизвестный документ')))}"
        
        # Добавляем содержимое чанка
        content = chunk.get('chunk_text', chunk.get('text', chunk.get('content', '')))
        
        # Добавляем информацию о релевантности
        similarity = chunk.get('similarity', 0)
        similarity_info = f"Релевантность: {similarity:.3f}"
        
        # Формируем полное описание чанка
        chunk_text = f"{document_info} ({similarity_info})\n\n{content}\n\n"
        context_parts.append(chunk_text)
    
    # Объединяем части контекста
    context = "--- КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ (ГИБРИДНЫЙ ПОИСК) ---\n\n" + "\n".join(context_parts)
    
    # Ограничиваем контекст по длине (примерно)
    if len(context) > max_tokens * 4:  # Примерное соотношение токенов к символам
        context = context[:max_tokens * 4] + "...\n\n--- КОНЕЦ КОНТЕКСТА ---"
    else:
        context += "\n\n--- КОНЕЦ КОНТЕКСТА ---"
    
    hybrid_logger.info(f"Сформирован контекст длиной {len(context)} символов")
    
    return context

def hybrid_search(query: str, vector_store, conn: sqlite3.Connection, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    """
    Выполняет гибридный поиск, возвращая объединенные результаты.
    
    Args:
        query: Поисковый запрос
        vector_store: Экземпляр FAISSVectorStore для векторного поиска
        conn: Соединение с базой данных SQLite
        top_k: Количество результатов для каждого типа поиска
        
    Returns:
        Список словарей с информацией о найденных чанках
    """
    hybrid_logger.info(f"Выполняем гибридный поиск по запросу: '{query}'")
    
    # Результаты поиска
    vec_results = []
    fts_results = []
    
    # 1. Выполняем векторный поиск
    if vector_store:
        try:
            vec_results = search_relevant_chunks(query, vector_store, conn, top_k)
            hybrid_logger.info(f"Векторный поиск: {len(vec_results)} результатов")
        except Exception as e:
            hybrid_logger.error(f"Ошибка векторного поиска: {str(e)}")
    
    # 2. Выполняем FTS поиск
    try:
        fts_results = fts_search(query, limit=top_k)
        hybrid_logger.info(f"FTS поиск: {len(fts_results)} результатов")
    except Exception as e:
        hybrid_logger.error(f"Ошибка FTS поиска: {str(e)}")
    
    # 3. Объединяем результаты
    merged_results = merge_results(vec_results, fts_results)
    hybrid_logger.info(f"Итого уникальных результатов: {len(merged_results)}")
    
    return merged_results

def get_search_statistics(query: str, vector_store, conn: sqlite3.Connection, top_k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
    """
    Возвращает статистику по результатам гибридного поиска.
    
    Args:
        query: Поисковый запрос
        vector_store: Экземпляр FAISSVectorStore для векторного поиска
        conn: Соединение с базой данных SQLite
        top_k: Количество результатов для каждого типа поиска
        
    Returns:
        Словарь со статистикой поиска
    """
    stats = {
        'query': query,
        'vector_results': 0,
        'fts_results': 0,
        'merged_results': 0,
        'overlap_count': 0,
        'vector_available': vector_store is not None,
        'fts_available': False
    }
    
    try:
        # Проверяем доступность FTS
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
        stats['fts_available'] = cursor.fetchone() is not None
        
        # Выполняем поиск
        vec_results = []
        fts_results = []
        
        if vector_store:
            try:
                vec_results = search_relevant_chunks(query, vector_store, conn, top_k)
                stats['vector_results'] = len(vec_results)
            except Exception as e:
                hybrid_logger.error(f"Ошибка векторного поиска в статистике: {str(e)}")
        
        if stats['fts_available']:
            try:
                fts_results = fts_search(query, limit=top_k)
                stats['fts_results'] = len(fts_results)
            except Exception as e:
                hybrid_logger.error(f"Ошибка FTS поиска в статистике: {str(e)}")
        
        # Анализируем пересечения
        if vec_results and fts_results:
            vec_ids = set(r.get('chunk_id', r.get('id')) for r in vec_results)
            fts_ids = set(r.get('chunk_id', r.get('id')) for r in fts_results)
            stats['overlap_count'] = len(vec_ids & fts_ids)
        
        # Объединяем результаты
        merged_results = merge_results(vec_results, fts_results)
        stats['merged_results'] = len(merged_results)
        
    except Exception as e:
        hybrid_logger.error(f"Ошибка при получении статистики: {str(e)}")
    
    return stats

if __name__ == "__main__":
    # Тестирование гибридного поиска
    import sqlite3
    from utils.vector_search import FAISSVectorStore
    from config import EMBEDDING_DIMENSION
    
    print("🔄 ТЕСТИРОВАНИЕ ГИБРИДНОГО ПОИСКА")
    print("=" * 60)
    
    # Подключаемся к базе данных
    db_path = os.path.join(os.getcwd(), 'knowledge_base_v2.db')
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена")
        exit()
    
    conn = sqlite3.connect(db_path)
    
    # Инициализируем векторное хранилище
    vector_store = None
    try:
        vector_store = FAISSVectorStore(embedding_dimension=EMBEDDING_DIMENSION)
        if vector_store.load_index():
            print("✅ Векторное хранилище загружено")
        else:
            print("⚠️ Векторное хранилище недоступно")
            vector_store = None
    except Exception as e:
        print(f"⚠️ Ошибка векторного хранилища: {e}")
        vector_store = None
    
    # Тестовые запросы
    test_queries = ["диагностика", "анализ крови", "лечение пациентов"]
    
    for query in test_queries:
        print(f"\n🔍 Запрос: '{query}'")
        print("-" * 50)
        
        # Получаем статистику
        stats = get_search_statistics(query, vector_store, conn)
        print(f"📊 Векторный: {stats['vector_results']}, FTS: {stats['fts_results']}, Итого: {stats['merged_results']}")
        
        # Выполняем гибридный поиск
        results = hybrid_search(query, vector_store, conn, top_k=3)
        
        for i, result in enumerate(results[:3], 1):
            search_type = result.get('search_type', 'unknown')
            doc_id = result.get('document_id', 'N/A')
            similarity = result.get('similarity', 0)
            
            print(f"   {i}. [{search_type.upper()}] {doc_id} (релевантность: {similarity:.3f})")
    
    conn.close()
    print("\n✅ Тестирование завершено") 