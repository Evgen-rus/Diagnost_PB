#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки работы векторного поиска

Позволяет протестировать поиск по базе знаний без запуска бота
"""

import os
import sqlite3
import sys
from dotenv import load_dotenv
from utils.vector_search import FAISSVectorStore, get_context_for_query, search_relevant_chunks
from config import EMBEDDING_DIMENSION

# Загрузка переменных окружения
load_dotenv()

def test_vector_search():
    """
    Тестирует векторный поиск по базе знаний
    """
    print("🔍 ТЕСТ ВЕКТОРНОГО ПОИСКА")
    print("=" * 60)
    
    # Проверяем API ключ
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ API ключ OpenAI не найден!")
        print("💡 Добавьте OPENAI_API_KEY в файл .env")
        return
    
    # Путь к базе данных
    db_path = os.path.join(os.getcwd(), 'knowledge_base_v2.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("💡 Запустите: python load_excel_to_vectordb.py")
        return
    
    # Проверяем FAISS индекс
    try:
        vector_store = FAISSVectorStore(embedding_dimension=EMBEDDING_DIMENSION)
        if not vector_store.load_index():
            print("❌ FAISS индекс не найден!")
            print("💡 Запустите: python build_faiss_index.py")
            return
        print("✅ Векторный индекс загружен")
    except Exception as e:
        print(f"❌ Ошибка загрузки индекса: {e}")
        return
    
    # Подключаемся к базе данных
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем количество чанков
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        print(f"📊 Найдено {chunk_count} чанков в базе данных")
        
        if chunk_count == 0:
            print("❌ База данных пуста!")
            return
        
    except Exception as e:
        print(f"❌ Ошибка подключения к базе: {e}")
        return
    
    # Тестовые запросы
    test_queries = [
        "Что такое диагностика?",
        "Как проводить анализ?",
        "Методы исследования",
        "Клинические рекомендации",
        "Лечение пациентов"
    ]
    
    print("\n🎯 РЕЗУЛЬТАТЫ ПОИСКА:")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Запрос: '{query}'")
        print("-" * 40)
        
        try:
            # Поиск релевантных чанков
            relevant_chunks = search_relevant_chunks(query, vector_store, conn)
            
            if not relevant_chunks:
                print("❌ Не найдено релевантных результатов")
                continue
            
            # Показываем результаты
            for j, chunk in enumerate(relevant_chunks, 1):
                # Улучшенный расчет релевантности: используем обратную функцию
                # чем меньше расстояние - тем выше релевантность (0.0-1.0)
                distance = chunk.get('distance', float('inf'))
                if distance == 0:
                    relevance = 1.0
                else:
                    relevance = round(1.0 / (1.0 + distance), 4)
                
                doc_id = chunk.get('document_id', 'N/A')
                doc_type = chunk.get('doc_type_short', 'N/A')
                text_preview = chunk.get('text', chunk.get('content', ''))[:100] + "..."
                
                print(f"   {j}. Релевантность: {relevance:.3f} (расстояние: {distance:.3f})")
                print(f"      Документ: {doc_id} ({doc_type})")
                print(f"      Текст: {text_preview}")
                print()
                
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
    
    # Интерактивный поиск
    print("\n🎮 ИНТЕРАКТИВНЫЙ ПОИСК")
    print("=" * 60)
    print("Введите ваш запрос (или 'quit' для выхода):")
    
    while True:
        try:
            user_query = input("\n🔍 Запрос: ").strip()
            
            if user_query.lower() in ['quit', 'exit', 'выход']:
                break
            
            if not user_query:
                continue
            
            # Получаем контекст
            context = get_context_for_query(user_query, vector_store, conn)
            
            if context:
                print(f"\n📄 Найденный контекст ({len(context)} символов):")
                print("-" * 40)
                print(context[:500] + "..." if len(context) > 500 else context)
            else:
                print("❌ Контекст не найден")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Закрываем соединение
    conn.close()
    print("\n👋 Тест завершен!")

def show_database_stats():
    """
    Показывает статистику базы данных
    """
    print("\n📊 СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    db_path = os.path.join(os.getcwd(), 'knowledge_base_v2.db')
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT document_id) FROM chunks")
        unique_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT doc_type_short) FROM chunks WHERE doc_type_short != ''")
        unique_types = cursor.fetchone()[0]
        
        print(f"📄 Всего чанков: {total_chunks}")
        print(f"📚 Уникальных документов: {unique_docs}")
        print(f"🏷️  Типов документов: {unique_types}")
        
        # Топ типов документов
        cursor.execute("""
            SELECT doc_type_short, COUNT(*) as count 
            FROM chunks 
            WHERE doc_type_short != '' 
            GROUP BY doc_type_short 
            ORDER BY count DESC 
            LIMIT 5
        """)
        
        print("\n🏆 Топ-5 типов документов:")
        for doc_type, count in cursor.fetchall():
            print(f"  • {doc_type}: {count} чанков")
        
        # Статистика по длине текста
        cursor.execute("SELECT AVG(LENGTH(chunk_text)), MIN(LENGTH(chunk_text)), MAX(LENGTH(chunk_text)) FROM chunks")
        avg_len, min_len, max_len = cursor.fetchone()
        
        print(f"\n📏 Длина текстов:")
        print(f"  • Средняя: {avg_len:.0f} символов")
        print(f"  • Минимальная: {min_len} символов")
        print(f"  • Максимальная: {max_len} символов")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        show_database_stats()
    else:
        test_vector_search() 