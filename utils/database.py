"""
Модуль для работы с базой данных SQLite.

Предоставляет функции для сохранения и извлечения логов диалогов пользователей.
"""
import sqlite3
import datetime
import json
from typing import List, Dict, Any, Optional, Tuple
import os
import logging

# Настраиваем логгер для модуля базы данных
db_logger = logging.getLogger('database')

# Путь к файлу базы данных
DB_PATH = os.path.join(os.getcwd(), 'data', 'bot_dialogs.db')

def init_database():
    """
    Инициализирует базу данных, создавая необходимые таблицы, если они отсутствуют.
    
    Создает таблицы для хранения:
    - message_logs: логи сообщений пользователей и ответов бота
    - user_sessions: сессии пользователей
    - test_results: результаты тестирования нейроконсультанта
    """
    # Создаем директорию для БД, если она отсутствует
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Создаем таблицу для логов сообщений
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL,
            message_type TEXT NOT NULL,  -- 'user' или 'bot'
            message_text TEXT NOT NULL,
            topics TEXT,  -- JSON строка с темами
            session_id TEXT  -- Идентификатор сессии
        )
        ''')
        
        # Создаем таблицу для хранения сессий пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id INTEGER PRIMARY KEY,
            last_activity DATETIME NOT NULL,
            knowledge_level TEXT,  -- JSON строка с уровнями знаний
            current_topic TEXT,
            session_data TEXT  -- JSON строка с данными сессии
        )
        ''')
        
        # Создаем таблицу для результатов тестирования
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            tester_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            score INTEGER,  -- Оценка от -2 до +2
            tokens INTEGER,  -- Количество токенов
            comment TEXT,  -- Комментарий тестировщика
            generation_time REAL,  -- Время генерации в секундах
            cost REAL,  -- Стоимость генерации
            chunks TEXT  -- JSON строка с использованными чанками
        )
        ''')
        
        conn.commit()
        db_logger.info("База данных инициализирована успешно")
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        
    finally:
        if conn:
            conn.close()

def log_message(user_id: int, message_type: str, message_text: str, 
                topics: Optional[Dict] = None, session_id: Optional[str] = None):
    """
    Сохраняет сообщение в базу данных.
    
    Args:
        user_id: ID пользователя
        message_type: Тип сообщения ('user' или 'bot')
        message_text: Текст сообщения
        topics: Словарь с информацией о темах (опционально)
        session_id: ID сессии (опционально)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Сериализуем topics в JSON, если они предоставлены
        topics_json = json.dumps(topics) if topics else None
        
        # Текущая дата и время
        timestamp = datetime.datetime.now().isoformat()
        
        # Вставляем запись в базу данных
        cursor.execute(
            '''
            INSERT INTO message_logs (user_id, timestamp, message_type, message_text, topics, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (user_id, timestamp, message_type, message_text, topics_json, session_id)
        )
        
        conn.commit()
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при логировании сообщения: {str(e)}")
        
    finally:
        if conn:
            conn.close()

def update_user_session(user_id: int, knowledge_level: Optional[Dict] = None, 
                       current_topic: Optional[str] = None, session_data: Optional[Dict] = None):
    """
    Обновляет информацию о сессии пользователя.
    
    Args:
        user_id: ID пользователя
        knowledge_level: Уровень знаний пользователя (опционально)
        current_topic: Текущая тема (опционально)
        session_data: Дополнительные данные сессии (опционально)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Текущая дата и время
        timestamp = datetime.datetime.now().isoformat()
        
        # Сериализуем данные в JSON
        knowledge_level_json = json.dumps(knowledge_level) if knowledge_level else None
        session_data_json = json.dumps(session_data) if session_data else None
        
        # Проверяем, существует ли запись для данного пользователя
        cursor.execute("SELECT user_id FROM user_sessions WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем существующую запись
            cursor.execute(
                '''
                UPDATE user_sessions SET 
                last_activity = ?,
                knowledge_level = COALESCE(?, knowledge_level),
                current_topic = COALESCE(?, current_topic),
                session_data = COALESCE(?, session_data)
                WHERE user_id = ?
                ''',
                (timestamp, knowledge_level_json, current_topic, session_data_json, user_id)
            )
        else:
            # Создаем новую запись
            cursor.execute(
                '''
                INSERT INTO user_sessions (user_id, last_activity, knowledge_level, current_topic, session_data)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (user_id, timestamp, knowledge_level_json, current_topic, session_data_json)
            )
        
        conn.commit()
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при обновлении сессии пользователя: {str(e)}")
        
    finally:
        if conn:
            conn.close()

def get_inactive_users(timeout_minutes: int = 30) -> List[int]:
    """
    Возвращает список ID пользователей, неактивных в течение указанного времени.
    
    Args:
        timeout_minutes: Количество минут неактивности (по умолчанию 30)
        
    Returns:
        Список ID неактивных пользователей
    """
    inactive_users = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Вычисляем время отсечки
        cutoff_time = (datetime.datetime.now() - datetime.timedelta(minutes=timeout_minutes)).isoformat()
        
        # Находим пользователей с последней активностью ранее отсечки
        cursor.execute(
            "SELECT user_id FROM user_sessions WHERE last_activity < ?",
            (cutoff_time,)
        )
        
        # Получаем список ID пользователей
        inactive_users = [row[0] for row in cursor.fetchall()]
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при получении неактивных пользователей: {str(e)}")
        
    finally:
        if conn:
            conn.close()
            
    return inactive_users

def get_user_dialog_logs(user_id: int, limit: int = 100) -> List[Dict]:
    """
    Получает логи диалога конкретного пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество сообщений (по умолчанию 100)
        
    Returns:
        Список словарей с информацией о сообщениях
    """
    logs = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Используем Row для получения результатов в виде словарей
        cursor = conn.cursor()
        
        # Получаем последние сообщения пользователя
        cursor.execute(
            '''
            SELECT * FROM message_logs 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''',
            (user_id, limit)
        )
        
        # Преобразуем результаты в список словарей
        for row in cursor.fetchall():
            log_entry = dict(row)
            
            # Десериализуем JSON данные
            if log_entry['topics']:
                log_entry['topics'] = json.loads(log_entry['topics'])
                
            logs.append(log_entry)
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при получении логов диалога: {str(e)}")
        
    finally:
        if conn:
            conn.close()
            
    return logs 

def log_test_result(tester_id: int, question: str, answer: str, score: int,
                  tokens: int, comment: str, generation_time: float, cost: float,
                  chunks: List[str]):
    """
    Сохраняет результат тестирования в базу данных.
    
    Args:
        tester_id: ID тестировщика
        question: Вопрос пользователя
        answer: Ответ нейроконсультанта
        score: Оценка от -2 до +2
        tokens: Количество использованных токенов
        comment: Комментарий тестировщика
        generation_time: Время генерации в секундах
        cost: Стоимость генерации
        chunks: Список использованных чанков
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Сериализуем chunks в JSON
        chunks_json = json.dumps(chunks, ensure_ascii=False)
        
        # Текущая дата и время
        timestamp = datetime.datetime.now().isoformat()
        
        # Вставляем запись в базу данных
        cursor.execute(
            '''
            INSERT INTO test_results (
                timestamp, tester_id, question, answer, score, 
                tokens, comment, generation_time, cost, chunks
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (timestamp, tester_id, question, answer, score, 
             tokens, comment, generation_time, cost, chunks_json)
        )
        
        conn.commit()
        db_logger.info(f"Результат теста сохранен в БД. Тестировщик: {tester_id}, Вопрос: {question[:50]}...")
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при сохранении результата теста: {str(e)}")
        
    finally:
        if conn:
            conn.close()

def get_test_results(limit: int = 100, tester_id: Optional[int] = None) -> List[Dict]:
    """
    Получает результаты тестирования из базы данных.
    
    Args:
        limit: Максимальное количество результатов (по умолчанию 100)
        tester_id: ID тестировщика для фильтрации (опционально)
        
    Returns:
        Список словарей с результатами тестирования
    """
    results = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if tester_id is not None:
            # Фильтрация по ID тестировщика
            cursor.execute(
                '''
                SELECT * FROM test_results
                WHERE tester_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                ''',
                (tester_id, limit)
            )
        else:
            # Получение всех результатов
            cursor.execute(
                '''
                SELECT * FROM test_results
                ORDER BY timestamp DESC
                LIMIT ?
                ''',
                (limit,)
            )
        
        # Преобразуем результаты в список словарей
        for row in cursor.fetchall():
            result = dict(row)
            
            # Десериализуем JSON данные
            if result['chunks']:
                result['chunks'] = json.loads(result['chunks'])
                
            results.append(result)
        
    except sqlite3.Error as e:
        db_logger.error(f"Ошибка при получении результатов тестирования: {str(e)}")
        
    finally:
        if conn:
            conn.close()
            
    return results

def export_test_results_to_csv(output_file: str = "test_results.csv", tester_id: Optional[int] = None):
    """
    Экспортирует результаты тестирования в CSV-файл.
    
    Args:
        output_file: Путь к выходному файлу CSV
        tester_id: ID тестировщика для фильтрации (опционально)
    """
    import csv
    
    try:
        # Получаем результаты тестирования
        results = get_test_results(limit=1000, tester_id=tester_id)
        
        if not results:
            db_logger.warning(f"Нет результатов тестирования для экспорта")
            return
        
        # Записываем результаты в CSV
        with open(output_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Записываем заголовки
            headers = [
                "ID", "Дата и время", "ID тестировщика", "Вопрос", "Ответ", 
                "Оценка", "Токены", "Комментарий", "Время генерации (сек)", 
                "Стоимость", "Чанки"
            ]
            writer.writerow(headers)
            
            # Записываем данные
            for result in results:
                writer.writerow([
                    result['id'],
                    result['timestamp'],
                    result['tester_id'],
                    result['question'],
                    result['answer'],
                    result['score'],
                    result['tokens'],
                    result['comment'],
                    result['generation_time'],
                    result['cost'],
                    json.dumps(result['chunks'], ensure_ascii=False)
                ])
        
        db_logger.info(f"Результаты тестирования экспортированы в {output_file}")
        
    except Exception as e:
        db_logger.error(f"Ошибка при экспорте результатов тестирования: {str(e)}") 