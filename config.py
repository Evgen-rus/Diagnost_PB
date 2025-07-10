import os
from typing import Optional
from dotenv import load_dotenv
from utils.exceptions import ConfigError
from utils.logger import logger

def get_env_var(name: str, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Получение переменной окружения с обработкой ошибок"""
    value = os.getenv(name, default)
    if required and not value:
        raise ConfigError(
            f"Отсутствует обязательная переменная окружения: {name}",
            f"Ошибка конфигурации. Проверьте наличие переменной {name}"
        )
    return value

try:
    # Загрузка переменных окружения
    if not load_dotenv():
        raise ConfigError("Не удалось загрузить файл .env")
    
    # Telegram Bot configuration
    TELEGRAM_BOT_TOKEN = get_env_var("TELEGRAM_BOT_TOKEN")
    
    # OpenAI configuration
    OPENAI_API_KEY = get_env_var("OPENAI_API_KEY")
    OPENAI_MODEL = get_env_var("OPENAI_MODEL", required=False, default="gpt-4.1-nano")
    
    # Vector search configuration
    DEFAULT_TOP_K = 3  # Количество чанков для поиска по умолчанию
    MAX_CONTEXT_TOKENS = 1000  # Максимальное количество токенов для контекста
    EMBEDDING_DIMENSION = 1536  # Размерность эмбеддингов OpenAI text-embedding-3-small
    
    logger.info("Конфигурация успешно загружена")

except Exception as e:
    logger.critical(f"Ошибка при инициализации конфигурации: {e}", exc_info=True)
    raise 