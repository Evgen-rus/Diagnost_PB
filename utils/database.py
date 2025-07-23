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

 