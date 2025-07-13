#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки работы гибридного поиска
"""

import os
import sqlite3
from utils.hybrid_search import hybrid_search, get_search_statistics
from utils.vector_search import FAISSVectorStore
from config import EMBEDDING_DIMENSION, HYBRID_SEARCH_ENABLED, DEFAULT_TOP_K

def test_hybrid_search():
    """Тестирует гибридный поиск по базе знаний"""
    print("🔄 ТЕСТ ГИБРИДНОГО ПОИСКА")
    print("=" * 60)
    
    # Проверяем включен ли гибридный поиск
    if not HYBRID_SEARCH_ENABLED:
        print("❌ Гибридный поиск отключен в конфигурации")
        return
    
    # Путь к базе данных
    db_path = os.path.join(os.getcwd(), 'knowledge_base_v2.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    # Подключаемся к базе данных
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
    
    # Проверяем FTS индекс
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
        if cursor.fetchone():
            print("✅ FTS индекс доступен")
        else:
            print("⚠️ FTS индекс недоступен")
            print("💡 Запустите: python build_fts_index.py")
    except Exception as e:
        print(f"⚠️ Ошибка FTS: {e}")
    
    # Тестовые запросы
    test_queries = [
        "дефекты сварных швов",
        "ультразвуковой контроль",
        "рентгенографический контроль"
    ]
    
    print("\n🎯 РЕЗУЛЬТАТЫ ГИБРИДНОГО ПОИСКА:")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Запрос: '{query}'")
        print("-" * 50)
        
        try:
            # Получаем статистику поиска
            stats = get_search_statistics(query, vector_store, conn, DEFAULT_TOP_K)
            print(f"📊 Статистика: Векторный={stats['vector_results']}, FTS={stats['fts_results']}, Итого={stats['merged_results']}")
            
            # Выполняем гибридный поиск
            results = hybrid_search(query, vector_store, conn, DEFAULT_TOP_K)
            
            if not results:
                print("❌ Не найдено результатов")
                continue
            
            # Показываем результаты
            for j, result in enumerate(results, 1):
                search_type = result.get('search_type', 'unknown')
                doc_id = result.get('document_id', 'N/A')
                doc_type = result.get('doc_type_short', 'N/A')
                similarity = result.get('similarity', 0)
                
                type_label = '🔍 ВЕКТОРНЫЙ' if search_type == 'vector' else '📝 FTS'
                
                print(f"   {j}. [{type_label}] {doc_id} ({doc_type})")
                print(f"      Релевантность: {similarity:.3f}")
                print()
                
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
    
    conn.close()
    print("\n👋 Тест гибридного поиска завершен!")

if __name__ == "__main__":
    test_hybrid_search() 