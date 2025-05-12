import tiktoken
from typing import Dict, List, Union
from utils.logger import logger, get_user_logger, ContextAdapter

class TokenCounter:
    def __init__(self):
        """
        Инициализирует счетчик токенов для моделей OpenAI.
        
        Создает объект для подсчета токенов, отслеживания общего использования
        и расчета стоимости запросов к API OpenAI. Хранит данные о стоимости
        различных моделей и кэширует энкодеры для повышения производительности.
        
        Attributes:
            total_tokens (int): Общее количество использованных токенов
            total_cost (float): Общая стоимость запросов в долларах
            encoders (dict): Кэш энкодеров для различных моделей
            price_per_1k (dict): Стоимость использования 1000 токенов для разных моделей
            last_request (dict): Информация о последнем запросе (для тестирования)
        """
        self.total_tokens = 0
        self.total_cost = 0
        self.encoders = {}
        
        # Данные о последнем запросе (для тестирования)
        self.last_request = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "model": ""
        }
        
        # Стоимость за 1000 токенов (в долларах)
        self.price_per_1k = {
            'gpt-4.1-nano': {
                'input': 0.0001,  # $0.10 / 1M tokens
                'output': 0.0004   # $0.40 / 1M tokens
            },
            'text-embedding-ada-002': {
                'input': 0.0001,   # $0.10 / 1M tokens
                'output': 0.0001   # $0.10 / 1M tokens
            }
        }
        
        self.reset_counters()
    
    def reset_counters(self):
        """
        Сбрасывает счетчики токенов и стоимости.
        
        Устанавливает общее количество токенов и стоимость в ноль.
        Вызывается при старте нового диалога.
        
        Returns:
            None
        """
        self.total_tokens = 0
        self.total_cost = 0
        self._reset_last_request()
    
    def _reset_last_request(self):
        """
        Сбрасывает информацию о последнем запросе.
        
        Вызывается перед каждым новым запросом для тестирования.
        """
        self.last_request = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "model": ""
        }
    
    def _get_encoder(self, model: str) -> tiktoken.Encoding:
        """
        Получает или создает энкодер для указанной модели.
        
        Проверяет наличие энкодера в кэше и создает новый, если он отсутствует.
        Использует механизм fallback для новых или неизвестных моделей.
        
        Args:
            model (str): Название модели OpenAI
            
        Returns:
            tiktoken.Encoding: Энкодер для указанной модели
            
        Raises:
            Exception: В случае невозможности получить энкодер даже с использованием fallback
        """
        if model not in self.encoders:
            try:
                self.encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback для новых моделей
                self.encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self.encoders[model]
    
    def count_tokens(self, text: Union[str, List, Dict], model: str) -> int:
        """
        Подсчитывает количество токенов в тексте или структуре данных.
        
        Рекурсивно обрабатывает различные типы данных (строки, списки, словари)
        и возвращает общее количество токенов для указанной модели.
        
        Args:
            text (Union[str, List, Dict]): Текст или структура данных для подсчета токенов
            model (str): Название модели OpenAI для использования соответствующего энкодера
            
        Returns:
            int: Количество токенов в тексте или структуре данных
            
        Raises:
            Не вызывает исключений напрямую, но может вызвать исключения из _get_encoder
        """
        encoder = self._get_encoder(model)
        
        if isinstance(text, str):
            return len(encoder.encode(text))
        elif isinstance(text, list):
            return sum(self.count_tokens(item, model) for item in text)
        elif isinstance(text, dict):
            return sum(self.count_tokens(str(value), model) for value in text.values())
        else:
            return 0
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int = 0) -> float:
        """
        Рассчитывает стоимость запроса к API на основе количества токенов.
        
        Учитывает разную стоимость входных и выходных токенов для различных моделей.
        Использует fallback на модель по умолчанию, если указанная модель неизвестна.
        
        Args:
            model (str): Название модели OpenAI
            input_tokens (int): Количество входных токенов
            output_tokens (int): Количество выходных токенов, по умолчанию 0
            
        Returns:
            float: Стоимость запроса в долларах США
            
        Raises:
            Не вызывает исключений, использует fallback для неизвестных моделей
        """
        # Создаем контекстный логгер для рассчета стоимости
        tokens_logger = get_user_logger(user_id=0, operation="cost_calculation")
        
        if model not in self.price_per_1k:
            tokens_logger.warning(f"Неизвестная модель {model}, используем цены gpt-4.1-nano")
            model = 'gpt-4.1-nano'
            
        input_cost = (input_tokens / 1000) * self.price_per_1k[model]['input']
        output_cost = (output_tokens / 1000) * self.price_per_1k[model]['output']
        
        return input_cost + output_cost
    
    def log_tokens_usage(self, model: str, input_text: Union[str, List, Dict], output_text: str = "", user_id: int = 0) -> int:
        """
        Логирует использование токенов и стоимость
        
        Args:
            model: Название модели GPT
            input_text: Входной текст или структура
            output_text: Выходной текст (опционально)
            user_id: ID пользователя для контекстного логирования (по умолчанию 0)
            
        Returns:
            int: Количество токенов
        """
        # Создаем контекстный логгер для учета токенов
        tokens_logger = get_user_logger(
            user_id=user_id, 
            operation="token_usage",
            session_id=f"model_{model}"
        )
        
        input_tokens = self.count_tokens(input_text, model)
        output_tokens = self.count_tokens(output_text, model) if output_text else 0
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        self.total_tokens += input_tokens + output_tokens
        self.total_cost += cost
        
        # Обновляем информацию о последнем запросе (для тестирования)
        self.last_request = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "model": model
        }
        
        # Компактный вывод в одну строку
        tokens_logger.info(
            f"Токены: вход={input_tokens}, выход={output_tokens}, цена=${cost:.6f}, всего={self.total_tokens}, общая цена=${self.total_cost:.6f}"
        )
        
        return input_tokens + output_tokens
    
    def get_last_request_info(self) -> Dict:
        """
        Возвращает информацию о последнем запросе.
        
        Returns:
            Dict: Словарь с информацией о токенах и стоимости последнего запроса
        """
        return self.last_request
    
    def start_test_request(self, model: str):
        """
        Начинает новый тестовый запрос.
        
        Args:
            model: Название модели GPT
        """
        self._reset_last_request()
        self.last_request["model"] = model
        
        # Создаем логгер для записи начала теста
        test_logger = get_user_logger(user_id=0, operation="test_tokens")
        test_logger.info(f"Начало тестового запроса с моделью {model}")

# Создаем глобальный счетчик токенов
token_counter = TokenCounter() 