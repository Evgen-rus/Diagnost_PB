import sqlite3
import csv
from datetime import datetime
import json
import sys

def export_dialogs_to_csv(user_id=None):
    """
    Экспортирует диалоги в CSV файл.
    
    Args:
        user_id (int, optional): ID пользователя для фильтрации. 
                               Если None, экспортируются все диалоги.
    """
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect('data/bot_dialogs.db')
        cursor = conn.cursor()
        
        # Формируем имя файла с текущей датой
        filename = f'dialogs_export_{datetime.now().strftime("%Y%m%d_%H%M")}'
        if user_id:
            filename += f'_user_{user_id}'
        filename += '.csv'
        
        # Формируем SQL запрос
        query = '''
            SELECT 
                id,
                user_id,
                timestamp,
                message_type,
                message_text,
                topics,
                session_id
            FROM message_logs
        '''
        
        # Добавляем фильтрацию по user_id если указан
        params = []
        if user_id:
            query += ' WHERE user_id = ?'
            params.append(user_id)
            
        query += ' ORDER BY user_id, timestamp'
        
        # Выполняем запрос
        cursor.execute(query, params)
        
        # Открываем CSV файл для записи
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Записываем заголовки
            writer.writerow([
                'ID сообщения',
                'ID пользователя',
                'Дата и время',
                'Тип сообщения',
                'Текст сообщения',
                'Темы',
                'ID сессии'
            ])
            
            # Записываем данные
            for row in cursor:
                id_, user_id, timestamp, msg_type, text, topics, session_id = row
                
                # Преобразуем topics из JSON если они есть
                if topics:
                    try:
                        topics = json.dumps(json.loads(topics), ensure_ascii=False)
                    except:
                        pass
                        
                writer.writerow([
                    id_,
                    user_id,
                    timestamp,
                    'Пользователь' if msg_type == 'user' else 'Бот',
                    text,
                    topics,
                    session_id
                ])
        
        print(f'Экспорт успешно завершен. Файл сохранен как: {filename}')
        
    except sqlite3.Error as e:
        print(f'Ошибка при работе с базой данных: {e}')
    except Exception as e:
        print(f'Произошла ошибка: {e}')
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Получаем ID пользователя из аргументов командной строки если он указан
    user_id = None
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print('Ошибка: ID пользователя должен быть числом')
            sys.exit(1)
    
    export_dialogs_to_csv(user_id) 