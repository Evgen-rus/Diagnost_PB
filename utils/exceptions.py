from typing import Optional
from utils.logger import logger

class BotError(Exception):
    """
    Базовый класс для всех исключений, возникающих в боте.
    
    Этот класс расширяет стандартный Exception, добавляя поле для сообщения,
    которое можно безопасно показать пользователю. Все специфичные исключения
    в боте должны наследоваться от этого класса.
    
    Attributes:
        message (str): Техническое сообщение об ошибке для логирования
        user_message (str): Сообщение, которое можно показать пользователю
    """
    def __init__(self, message: str, user_message: Optional[str] = None):
        """
        Инициализирует исключение с техническим и пользовательским сообщением.
        
        Args:
            message (str): Техническое сообщение об ошибке для логирования
            user_message (Optional[str]): Сообщение для пользователя, 
                                          по умолчанию используется общее сообщение
        """
        self.message = message
        self.user_message = user_message or "Произошла ошибка. Пожалуйста, попробуйте позже."
        super().__init__(self.message)

class ConfigError(BotError):
    """
    Исключение, возникающее при ошибках в конфигурации бота.
    
    Используется для обработки ошибок, связанных с настройками бота,
    окружением, переменными среды и файлами конфигурации.
    """
    pass

class OpenAIError(BotError):
    """
    Исключение, возникающее при ошибках во взаимодействии с OpenAI API.
    
    Используется для обработки ошибок при отправке запросов к API,
    проблем с авторизацией, превышения лимитов и других ошибок API.
    """
    pass

async def handle_error(error: Exception, context: Optional[dict] = None) -> str:
    """
    Централизованная обработка ошибок с логированием.
    
    Функция обрабатывает различные типы исключений, логирует их
    с соответствующим уровнем и возвращает сообщение для пользователя.
    
    Args:
        error (Exception): Объект исключения, которое требуется обработать
        context (Optional[dict]): Дополнительная контекстная информация
                                  для логирования (например, user_id, chat_id)
    
    Returns:
        str: Сообщение для отправки пользователю
    
    Notes:
        Для BotError используется сообщение из user_message.
        Для всех остальных исключений используется общее сообщение.
    """
    error_id = id(error)  # Уникальный идентификатор ошибки
    
    if isinstance(error, BotError):
        logger.error(f"Error ID {error_id}: {error.message}", extra={"context": context})
        return error.user_message
    
    # Для неожиданных ошибок
    logger.critical(
        f"Error ID {error_id}: Необработанная ошибка: {str(error)}",
        exc_info=True,
        extra={"context": context}
    )
    return "Произошла непредвиденная ошибка. Мы уже работаем над её устранением." 