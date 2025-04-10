import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Dict, Any, Optional  # Добавляем импорт типов для аннотаций
import datetime
import re  # Добавляем импорт для работы с регулярными выражениями
from utils.database import log_message

class ContextAdapter(logging.LoggerAdapter):
    """
    Адаптер для добавления контекстной информации в логи.
    
    Расширяет стандартный логгер, добавляя дополнительную информацию 
    о контексте выполнения (пользователь, сессия, операция и т.д.).
    
    Пример использования:
        user_logger = ContextAdapter(logger, {'user_id': message.from_user.id})
        user_logger.info("Пользователь отправил сообщение")
        # Результат: [User ID: 123456789] Пользователь отправил сообщение
    """
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """
        Инициализирует адаптер логгера с дополнительной информацией.
        
        Args:
            logger: Базовый логгер, к которому добавляется функциональность
            extra: Словарь с дополнительными данными для добавления в лог
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Обрабатывает сообщение перед логированием, добавляя контекстную информацию.
        
        Args:
            msg: Исходное сообщение для логирования
            kwargs: Дополнительные параметры логирования
            
        Returns:
            tuple: Кортеж из модифицированного сообщения и параметров
        """
        # Форматируем сообщение с контекстной информацией
        context_parts = []
        
        # Добавляем данные пользователя, если они есть
        if 'user_id' in self.extra:
            context_parts.append(f"User ID: {self.extra['user_id']}")
        
        # Добавляем данные о сессии, если они есть
        if 'session_id' in self.extra:
            context_parts.append(f"Session: {self.extra['session_id']}")
            
        # Добавляем информацию о текущей операции
        if 'operation' in self.extra:
            context_parts.append(f"Op: {self.extra['operation']}")
            
        # Объединяем все части контекста
        if context_parts:
            context_str = " | ".join(context_parts)
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
            
        # Если в kwargs уже есть extra, обновляем его, иначе создаем новый
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra'].update(self.extra)
            
        return formatted_msg, kwargs

def setup_logging() -> logging.Logger:
    """
    Настройка и инициализация главного логгера приложения.
    
    Функция настраивает корневой логгер приложения, устанавливает уровень логирования
    на основе переменной окружения LOG_LEVEL, создает и подключает обработчики вывода
    логов в консоль. Также устанавливает уровни логирования для сторонних библиотек.
    
    Уровень логирования берется из переменной окружения LOG_LEVEL (по умолчанию: INFO).
    Возможные значения: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    
    Returns:
        logging.Logger: Настроенный экземпляр логгера
        
    Raises:
        Не вызывает исключений непосредственно, но могут возникнуть проблемы
        с файловой системой при настройке обработчиков
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Создаем форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Создаем логгер для нашего приложения
    logger = logging.getLogger('neuro_hr_bot')
    logger.setLevel(getattr(logging, log_level))
    
    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Отключаем логирование в файл - оставляем только консольный вывод
    # Комментируем или убираем создание файлового обработчика
    
    # Устанавливаем уровень логирования для сторонних библиотек
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.INFO)
    
    return logger

# Создаем и экспортируем экземпляр логгера
logger = setup_logging() 

# Вспомогательная функция для создания логгера с контекстом пользователя
def get_user_logger(user_id: int, session_id: Optional[str] = None, 
                   operation: Optional[str] = None) -> ContextAdapter:
    """
    Создает логгер с контекстом пользователя.
    
    Args:
        user_id: ID пользователя в Telegram
        session_id: Опциональный ID сессии
        operation: Опциональное название операции
        
    Returns:
        ContextAdapter: Логгер с добавленным контекстом пользователя
    """
    extra = {'user_id': user_id}
    
    if session_id:
        extra['session_id'] = session_id
        
    if operation:
        extra['operation'] = operation
        
    return ContextAdapter(logger, extra)

# Специальный логгер для сохранения полных диалогов
def setup_dialog_logger() -> logging.Logger:
    """
    Создает отдельный логгер для сохранения полных текстов сообщений и ответов.
    
    Returns:
        logging.Logger: Настроенный логгер для диалогов
    """
    # Проверяем, включено ли логирование диалогов в настройках
    dialog_logging_enabled = os.getenv("ENABLE_DIALOG_LOGGING", "true").lower() in ["true", "1", "yes"]
    
    # Создаем отдельный логгер для диалогов
    dialog_logger = logging.getLogger('dialog_logs')
    
    # Если логирование диалогов отключено, устанавливаем уровень выше INFO
    if not dialog_logging_enabled:
        dialog_logger.setLevel(logging.WARNING)  # Фактически отключаем логирование
        return dialog_logger
        
    dialog_logger.setLevel(logging.INFO)
    
    # Убеждаемся, что логгер не наследует обработчики от родительского
    dialog_logger.propagate = False
    
    # Создаем директорию для диалогов
    log_dir = os.path.join(os.getcwd(), 'logs', 'dialogs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Создаем форматтер с минимальной информацией
    dialog_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Получаем текущую дату для имени файла
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f'chat_{current_date}.log')
    
    # Создаем файловый обработчик с ежедневной ротацией
    dialog_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # Храним логи за 30 дней
        encoding='utf-8'
    )
    dialog_handler.setFormatter(dialog_formatter)
    dialog_logger.addHandler(dialog_handler)
    
    return dialog_logger

# Создаем экземпляр логгера для диалогов
dialog_logger = setup_dialog_logger()

def clean_html_tags(text: str) -> str:
    """
    Очищает текст от HTML-тегов.
    
    Функция использует регулярные выражения для удаления HTML-тегов из текста.
    Применяется для очистки сообщений пользователя и ответов бота перед логированием,
    чтобы обеспечить читаемость логов и упростить их анализ.
    
    Args:
        text (str): Исходный текст с HTML-тегами
        
    Returns:
        str: Очищенный текст без HTML-тегов
        
    Raises:
        Не вызывает исключений, в случае ошибок регулярного выражения возвращает исходный текст
    """
    # Удаляем HTML-теги
    clean_text = re.sub(r'<[^>]+>', '', text)
    return clean_text

def log_user_message(user_id: int, message_text: str) -> None:
    """
    Логирует полный текст сообщения пользователя.
    
    Функция записывает сообщение пользователя в специальный лог-файл диалогов,
    предварительно очищая его от HTML-тегов для лучшей читаемости.
    Также сохраняет сообщение в базу данных SQLite.
    
    Args:
        user_id (int): ID пользователя в Telegram
        message_text (str): Полный текст сообщения пользователя
        
    Returns:
        None
        
    Notes:
        Функция не вызывает исключений и не влияет на работу бота при ошибках логирования.
        Если логирование диалогов отключено (уровень выше INFO), функция не выполняет запись.
    """
    # Очищаем сообщение от HTML-тегов перед логированием
    clean_message = clean_html_tags(message_text)
    
    # Сохраняем сообщение в логи только если уровень логгера INFO или ниже
    if dialog_logger.isEnabledFor(logging.INFO):
        dialog_logger.info(f"[USER {user_id}] {clean_message}")
    
    # Сохраняем в базу данных
    try:
        log_message(user_id=user_id, message_type='user', message_text=clean_message)
    except Exception as e:
        logger.error(f"Ошибка при сохранении сообщения пользователя в базу данных: {str(e)}")

def log_bot_response(user_id: int, response_text: str) -> None:
    """
    Логирует полный текст ответа бота.
    
    Функция записывает ответ бота в специальный лог-файл диалогов,
    предварительно очищая его от HTML-тегов для лучшей читаемости.
    Также сохраняет ответ в базу данных SQLite.
    
    Args:
        user_id (int): ID пользователя в Telegram
        response_text (str): Полный текст ответа бота
        
    Returns:
        None
        
    Notes:
        Функция не вызывает исключений и не влияет на работу бота при ошибках логирования.
        Если логирование диалогов отключено (уровень выше INFO), функция не выполняет запись.
    """
    # Очищаем ответ от HTML-тегов перед логированием
    clean_response = clean_html_tags(response_text)
    
    # Сохраняем ответ в логи только если уровень логгера INFO или ниже
    if dialog_logger.isEnabledFor(logging.INFO):
        dialog_logger.info(f"[BOT TO {user_id}] {clean_response}")
    
    # Сохраняем в базу данных
    try:
        log_message(user_id=user_id, message_type='bot', message_text=clean_response)
    except Exception as e:
        logger.error(f"Ошибка при сохранении ответа бота в базу данных: {str(e)}") 