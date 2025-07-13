#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки работы FTS поиска
"""

import os
import sqlite3
import sys
from utils.fts_search import fts_search
from config import FTS_ENABLED, FTS_DEFAULT_LIMIT

def test_fts_search():
    """Тестирует FTS поиск по базе знаний"""
    print("📝 ТЕСТ FTS ПОИСКА")
    print("=" * 60)
    
    # Проверяем включен ли FTS
    if not FTS_ENABLED:
        print("❌ FTS поиск отключен в конфигурации")
        return
    
    # Путь к базе данных
    db_path = os.path.join(os.getcwd(), 'knowledge_base_v2.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("💡 Запустите: python load_excel_to_vectordb.py")
        return
    
    # Проверяем FTS индекс
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем существование FTS таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
        if not cursor.fetchone():
            print("❌ FTS таблица не найдена!")
            print("💡 Запустите: python build_fts_index.py")
            conn.close()
            return
        
        # Проверяем количество записей в FTS
        cursor.execute("SELECT COUNT(*) FROM chunks_fts")
        fts_count = cursor.fetchone()[0]
        print(f"✅ FTS индекс содержит {fts_count} записей")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка проверки FTS индекса: {e}")
        return
    
    # Тестовые запросы
    test_queries = [
        "дефекты сварных швов",
        "ультразвуковой контроль", 
        "рентгенографический контроль",
        "магнитопорошковый контроль"
    ]
    
    print("\n🎯 РЕЗУЛЬТАТЫ FTS ПОИСКА:")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Запрос: '{query}'")
        print("-" * 40)
        
        try:
            # Поиск по FTS
            results = fts_search(query, limit=FTS_DEFAULT_LIMIT)
            
            if not results:
                print("❌ Не найдено результатов")
                continue
            
            # Показываем результаты
            for j, result in enumerate(results, 1):
                doc_id = result.get('document_id', 'N/A')
                doc_type = result.get('doc_type_short', 'N/A')
                rank = result.get('rank', 0)
                snippet = result.get('snippet', '')
                
                print(f"   {j}. Документ: {doc_id} ({doc_type})")
                print(f"      Релевантность: {rank:.3f}")
                print(f"      Отрывок: {snippet}")
                print()
                
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
    
    print("\n👋 Тест FTS поиска завершен!")

if __name__ == "__main__":
    test_fts_search() 