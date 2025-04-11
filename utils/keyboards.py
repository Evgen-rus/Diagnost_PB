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
        
        # Добавляем кнопку выбора уровня специалиста
        builder.row(
            InlineKeyboardButton(text="Выбрать уровень специалиста", callback_data="select_level")
        )
        
        keyboard_logger.info("Inline-клавиатура успешно создана")
        return builder.as_markup()
        
    except Exception as e:
        error_msg = f"Ошибка при создании inline-клавиатуры: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise KeyboardError(error_msg, "Не удалось создать интерфейс. Попробуйте позже.")

def create_level_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает inline-клавиатуру для выбора уровня специалиста в области НК.
    
    Клавиатура содержит три кнопки, соответствующие трем уровням квалификации 
    специалистов в сфере неразрушающего контроля согласно стандартам.
    
    Returns:
        InlineKeyboardMarkup: Объект inline-клавиатуры с кнопками выбора уровня
    """
    try:
        keyboard_logger = get_user_logger(user_id=0, operation="level_keyboard_creation")
        keyboard_logger.info("Создание клавиатуры выбора уровня специалиста")
        
        builder = InlineKeyboardBuilder()
        
        # Добавляем кнопки для каждого уровня
        builder.row(
            InlineKeyboardButton(text="Уровень 1 (Технический)", callback_data="level_1")
        )
        builder.row(
            InlineKeyboardButton(text="Уровень 2 (Квалифицированный)", callback_data="level_2")
        )
        builder.row(
            InlineKeyboardButton(text="Уровень 3 (Экспертный)", callback_data="level_3")
        )
        
        # Добавляем кнопку возврата
        builder.row(
            InlineKeyboardButton(text="← Вернуться", callback_data="back_to_main")
        )
        
        keyboard_logger.info("Клавиатура выбора уровня успешно создана")
        return builder.as_markup()
        
    except Exception as e:
        error_msg = f"Ошибка при создании клавиатуры выбора уровня: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise KeyboardError(error_msg, "Не удалось создать интерфейс выбора уровня. Попробуйте позже.") 