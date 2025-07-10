#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки данных из database_v1.xlsx в векторную базу данных

Описание: Читает Excel файл с чанками документов и загружает их в SQLite базу
для последующего создания FAISS индекса
"""

import pandas as pd
import sqlite3
import os
import logging
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к базе данных
DB_PATH = os.path.join(os.getcwd(), 'knowledge_base_v2.db')

def create_chunks_table(conn):
    """
    Создает таблицу chunks в базе данных если она не существует
    
    Параметры:
    conn: соединение с базой данных SQLite
    """
    cursor = conn.cursor()
    
    # Создаем таблицу chunks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT UNIQUE NOT NULL,
            document_id INTEGER,
            doc_type_short TEXT,
            doc_type_full TEXT,
            doc_number TEXT,
            file_name TEXT,
            chunk_index INTEGER,
            chunk_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks(chunk_index)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON chunks(doc_type_short)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_file_name ON chunks(file_name)')
    
    conn.commit()
    logger.info("Таблица chunks создана или уже существует")

def load_excel_to_database(excel_file: str, db_path: str):
    """
    Загружает данные из Excel файла в базу данных SQLite
    
    Параметры:
    excel_file (str): Путь к Excel файлу
    db_path (str): Путь к базе данных SQLite
    """
    logger.info(f"Начинаем загрузку данных из {excel_file}")
    
    # Проверяем существование Excel файла
    if not Path(excel_file).exists():
        logger.error(f"Файл {excel_file} не найден!")
        return False
    
    try:
        # Читаем Excel файл
        logger.info("Чтение Excel файла...")
        df = pd.read_excel(excel_file, engine='openpyxl')
        logger.info(f"Прочитано {len(df)} строк из Excel файла")
        
        # Проверяем наличие необходимых столбцов
        required_columns = ['document_id', 'chunk_index', 'chunk_text']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Отсутствуют необходимые столбцы: {missing_columns}")
            return False
        
        # Удаляем строки с пустым chunk_text
        initial_count = len(df)
        df = df.dropna(subset=['chunk_text'])
        df = df[df['chunk_text'].str.strip() != '']
        logger.info(f"После очистки пустых текстов: {len(df)} строк (удалено {initial_count - len(df)})")
        
        # Создаем уникальный chunk_id для каждой записи
        df['chunk_id'] = df['document_id'].astype(str) + '_' + df['chunk_index'].astype(str)
        
        # Подключаемся к базе данных
        logger.info(f"Подключение к базе данных: {db_path}")
        conn = sqlite3.connect(db_path)
        
        # Создаем таблицу
        create_chunks_table(conn)
        
        # Очищаем существующие данные
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunks")
        conn.commit()
        logger.info("Очистили существующие данные в таблице chunks")
        
        # Загружаем данные
        logger.info("Загрузка данных в базу...")
        
        # Подготавливаем данные для вставки
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                row['chunk_id'],
                int(row['document_id']),
                row.get('doc_type_short', ''),
                row.get('doc_type_full', ''),
                row.get('doc_number', ''),
                row.get('file_name', ''),
                int(row['chunk_index']),
                str(row['chunk_text']).strip()
            ))
        
        # Вставляем данные пакетами
        cursor.executemany('''
            INSERT OR REPLACE INTO chunks 
            (chunk_id, document_id, doc_type_short, doc_type_full, doc_number, file_name, chunk_index, chunk_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM chunks")
        inserted_count = cursor.fetchone()[0]
        
        logger.info(f"Успешно загружено {inserted_count} записей в таблицу chunks")
        
        # Показываем статистику
        cursor.execute("SELECT COUNT(DISTINCT document_id) FROM chunks")
        unique_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT doc_type_short) FROM chunks WHERE doc_type_short != ''")
        unique_types = cursor.fetchone()[0]
        
        logger.info(f"Статистика:")
        logger.info(f"  - Уникальных документов: {unique_docs}")
        logger.info(f"  - Типов документов: {unique_types}")
        logger.info(f"  - Всего чанков: {inserted_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {str(e)}", exc_info=True)
        return False

def main():
    """
    Основная функция
    """
    excel_file = "database_v1.xlsx"
    
    print("🗃️  ЗАГРУЗКА ДАННЫХ В ВЕКТОРНУЮ БАЗУ")
    print("=" * 60)
    print(f"📄 Excel файл: {excel_file}")
    print(f"🗄️  База данных: {DB_PATH}")
    print("=" * 60)
    
    # Проверяем существование файла
    if not Path(excel_file).exists():
        print(f"❌ Файл {excel_file} не найден!")
        print("💡 Убедитесь, что файл находится в текущей директории")
        return
    
    # Загружаем данные
    success = load_excel_to_database(excel_file, DB_PATH)
    
    if success:
        print("\n✅ ДАННЫЕ УСПЕШНО ЗАГРУЖЕНЫ!")
        print("📋 Следующие шаги:")
        print("  1. Запустите: python build_faiss_index.py")
        print("  2. Включите векторный поиск в bot.py")
        print(f"📁 База данных: {DB_PATH}")
    else:
        print("\n❌ ОШИБКА ПРИ ЗАГРУЗКЕ ДАННЫХ!")
        print("📋 Проверьте логи для получения подробностей")

if __name__ == "__main__":
    main() 