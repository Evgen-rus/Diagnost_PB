"""
Модуль для работы с клавиатурами в Telegram боте.

Предоставляет функции для создания и управления кнопками
в интерфейсе Telegram бота, упрощая взаимодействие пользователя с ботом.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.logger import logger, get_user_logger
from utils.exceptions import BotError

class KeyboardError(BotError):
    """Ошибки при работе с клавиатурами"""
    pass

def create_main_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создает основную inline-клавиатуру с кнопками быстрого доступа.
    
    Returns:
        InlineKeyboardMarkup: Объект inline-клавиатуры с кнопками
    """
    try:
        keyboard_logger = get_user_logger(user_id=0, operation="keyboard_creation")
        keyboard_logger.info("Создание inline-клавиатуры с кнопками")
        
        builder = InlineKeyboardBuilder()
        
        # Добавляем кнопки в первый ряд
        builder.row(
            InlineKeyboardButton(text="Объясни", callback_data="explain")
        )
        
        # Добавляем кнопку "Новый вопрос" во второй ряд
        builder.row(
            InlineKeyboardButton(text="Новый вопрос", callback_data="new_question")
        )
        
        keyboard_logger.info("Inline-клавиатура успешно создана")
        return builder.as_markup()
        
    except Exception as e:
        error_msg = f"Ошибка при создании inline-клавиатуры: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise KeyboardError(error_msg, "Не удалось создать интерфейс. Попробуйте позже.") 