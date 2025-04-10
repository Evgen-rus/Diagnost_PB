"""
Модуль для управления сессиями пользователей и очистки неактивных сессий.
"""
import asyncio
import logging
from typing import Dict, Any, Set
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from utils.database import get_inactive_users, update_user_session

# Настраиваем логгер для модуля очистки сессий
cleaner_logger = logging.getLogger('session_cleaner')

# Время неактивности в минутах, после которого сессия считается устаревшей
INACTIVITY_TIMEOUT = 30

async def cleanup_inactive_sessions(storage: MemoryStorage):
    """
    Очищает неактивные сессии из хранилища памяти.
    
    Args:
        storage: Хранилище состояний пользователей
    """
    cleaner_logger.info("Запуск очистки неактивных сессий")
    
    # Получаем ID неактивных пользователей из базы данных
    inactive_users = get_inactive_users(timeout_minutes=INACTIVITY_TIMEOUT)
    
    if not inactive_users:
        cleaner_logger.info("Неактивные пользователи не найдены")
        return
    
    cleaner_logger.info(f"Найдено {len(inactive_users)} неактивных пользователей")
    
    # В версии MVP просто выводим информацию о неактивных пользователях, 
    # но реально не удаляем из хранилища, так как это может вызвать проблемы
    # и требует более глубокой интеграции с aiogram
    for user_id in inactive_users:
        try:
            cleaner_logger.info(f"Обнаружен неактивный пользователь {user_id}")
            # В полной версии здесь будет код для безопасной очистки данных конкретного пользователя
        except Exception as e:
            cleaner_logger.error(f"Ошибка при обработке неактивного пользователя {user_id}: {str(e)}")
    
    cleaner_logger.info(f"Обработка неактивных пользователей завершена, найдено {len(inactive_users)} пользователей")

async def update_user_activity(user_id: int, state: FSMContext):
    """
    Обновляет информацию о последней активности пользователя в базе данных.
    
    Args:
        user_id: ID пользователя
        state: Контекст состояния пользователя
    """
    try:
        # Получаем текущие данные состояния
        data = await state.get_data()
        
        # Обновляем запись о сессии пользователя в базе данных
        topics = data.get("topics", {})
        current_topic = topics.get("current", "")
        knowledge_level = data.get("user_knowledge_level", {})
        
        # Сохраняем минимальный набор данных в базу
        session_data = {
            "last_message_id": data.get("last_bot_message_id"),
            "token_count": data.get("token_count", 0),
            "cost": data.get("cost", 0)
        }
        
        # Обновляем информацию о сессии в базе данных
        update_user_session(
            user_id=user_id,
            knowledge_level=knowledge_level,
            current_topic=current_topic,
            session_data=session_data
        )
        
    except Exception as e:
        cleaner_logger.error(f"Ошибка при обновлении активности пользователя {user_id}: {str(e)}")

async def start_cleaner(storage: MemoryStorage, interval_seconds: int = 300):
    """
    Запускает периодическую очистку неактивных сессий.
    
    Args:
        storage: Хранилище состояний пользователей
        interval_seconds: Интервал между запусками очистки в секундах (по умолчанию 5 минут)
    """
    cleaner_logger.info(f"Запуск планировщика очистки сессий с интервалом {interval_seconds} секунд")
    
    while True:
        try:
            # Выполняем очистку
            await cleanup_inactive_sessions(storage)
            
            # Ждем заданный интервал
            await asyncio.sleep(interval_seconds)
            
        except asyncio.CancelledError:
            cleaner_logger.info("Планировщик очистки сессий остановлен")
            break
            
        except Exception as e:
            cleaner_logger.error(f"Ошибка в планировщике очистки сессий: {str(e)}")
            # Продолжаем работу даже при ошибке
            await asyncio.sleep(interval_seconds) 