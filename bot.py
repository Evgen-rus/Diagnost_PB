import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
import json
from openai import AsyncOpenAI
from utils.logger import logger, get_user_logger, log_user_message, log_bot_response
from utils.token_counter import token_counter
from utils.database import init_database, log_message
from utils.session_cleaner import update_user_activity, start_cleaner
import datetime
import re  # Добавляем импорт модуля регулярных выражений
from prompts import LEARNING_ASSISTANT_PROMPT, INSTRUCTION, WELCOME_MESSAGE, FIRST_QUESTION_PROMPT
import sqlite3
from utils.vector_search import FAISSVectorStore, get_context_for_query, augment_prompt_with_context

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота и диспетчера с хранилищем состояний
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация OpenAI клиента
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

# Инициализация векторного хранилища
vector_store = None

# Определение состояний диалога
class BotStates(StatesGroup):
    """
    Определение состояний конечного автомата для диалога бота.
    
    Эта группа состояний используется для отслеживания этапов диалога 
    между пользователем и ботом. В текущей реализации используется только
    одно состояние (LEARNING_ASSISTANT) для проведения всего интервью.
    
    Attributes:
        LEARNING_ASSISTANT (State): Состояние работы помощника в обучении. В этом состоянии
                           бот собирает информацию для создания профиля кандидата.
    
    Note:
        Для расширения функциональности бота можно добавить дополнительные состояния.
        Например, для редактирования профиля или других режимов работы.
    """
    LEARNING_ASSISTANT = State()  # Состояние работы первого и пока единственного агента (помощник в обучении)

# Обработчик команды /start
@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start.
    
    Инициализирует новый диалог с пользователем, сбрасывает счетчики токенов
    и устанавливает начальное состояние бота.
    
    Args:
        message (types.Message): Объект сообщения Telegram
        state (FSMContext): Контекст состояния для хранения данных диалога
    """
    # Создаем контекстный логгер для пользователя
    user_logger = get_user_logger(
        user_id=message.from_user.id, 
        operation="start_command"
    )
    user_logger.info(f"Пользователь {message.from_user.full_name} (ID: {message.from_user.id}) запустил бота")
    
    # Устанавливаем состояние LEARNING_ASSISTANT
    await state.set_state(BotStates.LEARNING_ASSISTANT)
    
    # Инициализируем данные сессии
    await state.update_data(
        messages=[{"role": "system", "content": LEARNING_ASSISTANT_PROMPT}],
        token_count=0,
        cost=0,
        answers={},
        # Новые поля для обучающего ассистента
        topics={
            "current": "",
            "history": [],
            "related_topics": {}
        },
        user_knowledge_level={
            "general": "beginner",
            "topics": {}
        },
        # Инициализируем счетчик сообщений
        message_counter=0
    )
    
    # Обновляем информацию об активности пользователя в базе данных
    await update_user_activity(user_id=message.from_user.id, state=state)
    
    # Отправляем приветственное сообщение
    await message.answer(WELCOME_MESSAGE, parse_mode="HTML")
    
    # Запрашиваем у OpenAI первый вопрос на основе начального промпта
    first_query_response = await get_gpt_response(
        [{"role": "system", "content": FIRST_QUESTION_PROMPT}],
        "",
            user_id=message.from_user.id
        )
        
    # Сохраняем ответ GPT в историю сообщений
    await state.update_data(
        messages=[
            {"role": "system", "content": LEARNING_ASSISTANT_PROMPT},
            {"role": "assistant", "content": first_query_response}
        ]
    )
    
    # Отправляем первый вопрос пользователю с клавиатурой
    sent_message = await message.answer(
        first_query_response, 
        parse_mode="HTML"
    )
    
    # Сохраняем ID сообщения для последующего удаления клавиатуры
    await state.update_data(last_bot_message_id=sent_message.message_id)
    
    # Логируем отправку первого вопроса
    log_bot_response(message.from_user.id, first_query_response)

# Функция для поддержания индикатора набора текста
async def keep_typing(chat_id):
    """
    Непрерывно отправляет действие 'печатает' в чат до отмены.
    
    Эта функция запускается как отдельная асинхронная задача (task) с помощью 
    asyncio.create_task() и поддерживает статус "печатает" в Telegram, 
    пока идет генерация ответа. Это улучшает пользовательский опыт,
    показывая пользователю, что бот активно работает над ответом.
    
    Действия:
    1. В бесконечном цикле отправляет действие "typing" в указанный чат
    2. Пауза между отправками составляет 4.5 секунд (оптимизировано под Telegram API)
    3. При отмене задачи корректно завершает выполнение, обрабатывая CancelledError
    
    Args:
        chat_id (int): Идентификатор чата Telegram, в котором нужно показать статус
        
    Returns:
        None
        
    Raises:
        asyncio.CancelledError: Обрабатывается внутри функции, служит сигналом для завершения
        
    Note:
        Индикатор "печатает" в Telegram API автоматически исчезает примерно через 5 секунд,
        поэтому функция отправляет сигнал каждые 4.5 секунды для непрерывного эффекта.
        Задача должна быть явно отменена с помощью typing_task.cancel() после
        завершения операции, иначе она продолжит выполняться бесконечно.
    """
    try:
        while True:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4.5)  # Индикатор набора текста в Telegram длится ~5 секунд
    except asyncio.CancelledError:
        # Задача отменена, просто выходим
        pass

# Обработчик всех сообщений
@dp.message(BotStates.LEARNING_ASSISTANT)
async def process_message(message: types.Message, state: FSMContext):
    """
    Основной обработчик всех сообщений пользователя в состоянии LEARNING_ASSISTANT.
    
    Этот обработчик принимает все сообщения пользователя,
    анализирует их и формирует ответы с помощью OpenAI API.
       
    Args:
        message (types.Message): Объект сообщения Telegram с данными пользователя
        state (FSMContext): Контекст состояния для хранения данных диалога
    """
    # Создаем контекстный логгер для текущего пользователя
    user_logger = get_user_logger(
        user_id=message.from_user.id,
        operation="process_message"
    )
    
    user_logger.info(f"Пользователь отправил сообщение: {message.text[:50]}..." if len(message.text) > 50 else f"Пользователь отправил сообщение: {message.text}")
    
    # Логируем полное сообщение пользователя
    log_user_message(message.from_user.id, message.text)
    
    # Показываем индикатор набора текста
    typing_task = asyncio.create_task(keep_typing(message.chat.id))
    
    try:
        # Получаем текущее состояние диалога
        data = await state.get_data()
        messages = data.get("messages", [])
        answers = data.get("answers", {})
        topics = data.get("topics", {"current": "", "history": [], "related_topics": {}})
        user_knowledge_level = data.get("user_knowledge_level", {"general": "beginner", "topics": {}})
        
        # Счетчик сообщений пользователя для автоматического сброса контекста
        message_counter = data.get("message_counter", 0)
        message_counter += 1
        
        # Создаем идентификатор сессии для логирования всех действий в рамках этого запроса
        session_id = f"msg_{int(datetime.datetime.now().timestamp())}"
        request_logger = get_user_logger(
            user_id=message.from_user.id,
            session_id=session_id,
            operation="process_message"
        )
        
        # Проверка на необходимость сброса контекста (каждый 3-й вопрос)
        if message_counter > 0 and message_counter % 3 == 0:
            request_logger.info(f"Автоматический сброс контекста после {message_counter} вопросов")
                                   
            # сбрасывая историю диалога
            messages = [{"role": "system", "content": LEARNING_ASSISTANT_PROMPT}]
                        
            # Сбрасываем счетчик сообщений
            message_counter = 0
        
        # Добавляем сообщение пользователя в историю
        messages.append({"role": "user", "content": message.text})     
                      
        # Формируем системный промпт
        system_prompt = LEARNING_ASSISTANT_PROMPT
        
        # Создаем контекст для передачи в GPT
        context = {
            "answers": answers,
            "topics": topics,
            "user_knowledge_level": user_knowledge_level,
            "wait_for_confirmation": data.get("wait_for_confirmation", False)
        }
            
        request_logger.info("Отправка запроса для анализа ответа и генерации ответа")        
        
        # Получаем ответ от GPT с контекстом
        gpt_response = await get_gpt_response(
            messages,
            system_prompt, 
            f"Контекст: {json.dumps(context, ensure_ascii=False)}\n\nИнструкция: {INSTRUCTION}",
            user_id=message.from_user.id
        )
            
        # Парсим ответ от GPT для обновления состояния
        try:
            # Проверяем, есть ли в ответе JSON-строка с обновленным состоянием
            if "```json" in gpt_response and "```" in gpt_response:
                request_logger.info("Обнаружен JSON в ответе GPT, извлечение данных")
                json_str = gpt_response.split("```json")[1].split("```")[0].strip()
                updated_state = json.loads(json_str)
                
                # Обновляем состояние
                answers = updated_state.get("answers", answers)
                
                # Обновляем уровень знаний пользователя, если есть
                if "user_knowledge_level" in updated_state:
                    user_knowledge_level = updated_state["user_knowledge_level"]
                
                # Очищаем ответ от служебной информации
                gpt_response = gpt_response.split("```")[0] + gpt_response.split("```")[-1]
                request_logger.info("Состояние успешно обновлено")
        except Exception as e:
            request_logger.error(f"Ошибка при парсинге ответа GPT: {str(e)}", exc_info=True)
        
        # Добавляем ответ GPT в историю
        messages.append({"role": "assistant", "content": gpt_response})
        
        # Обновляем состояние
        await state.update_data(
            messages=messages,
            answers=answers,
            topics=topics,
            user_knowledge_level=user_knowledge_level,
            message_counter=message_counter  # Сохраняем счетчик сообщений
        )
        
        # Обновляем информацию об активности пользователя в базе данных
        await update_user_activity(user_id=message.from_user.id, state=state)
        
        request_logger.info("Отправка ответа пользователю")

        # Отправляем новое сообщение и сохраняем его ID
        sent_message = await message.answer(
            gpt_response, 
            parse_mode="HTML"
        )
        
        # Сохраняем ID сообщения для последующего удаления клавиатуры
        await state.update_data(last_bot_message_id=sent_message.message_id)
        
        # Логируем полный ответ бота
        log_bot_response(message.from_user.id, gpt_response)
        
        # Отменяем задачу обновления статуса
        typing_task.cancel()
        
    except Exception as e:
        # Отменяем задачу обновления статуса в случае ошибки
        typing_task.cancel()
        user_logger.error(f"Ошибка при обработке сообщения: {str(e)}", exc_info=True)
        await message.answer("Произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз.", parse_mode="HTML")

async def get_gpt_response(messages, system_content, additional_system_content=None, user_id=0):
    """
    Получение ответа от GPT через OpenAI API.
    
    Формирует запрос к модели GPT на основе истории сообщений, системного промпта
    и дополнительного контекста, отправляет запрос и обрабатывает полученный ответ.
    Использует векторный поиск для обогащения контекста релевантной информацией.
    
    Действия:
    1. Создает контекстный логгер для GPT запросов
    2. Получает контекст из базы знаний с помощью векторного поиска
    3. Формирует сообщения для API с системным промптом и историей диалога
    4. Отправляет запрос к выбранной модели OpenAI
    5. Обрабатывает ответ, конвертируя Markdown в HTML
    6. Учитывает токены и стоимость запроса
    
    Args:
        messages (list): История сообщений диалога в формате [{role: str, content: str}, ...]
        system_content (str): Системный промпт для модели
        additional_system_content (str, optional): Дополнительная информация для системного промпта.
                                                По умолчанию None.
        user_id (int, optional): ID пользователя для логирования. По умолчанию 0.
        
    Returns:
        str: Ответ от модели GPT после обработки
        
    Raises:
        Exception: Обрабатывает и логирует все исключения при взаимодействии с API OpenAI,
                   возвращая пользователю сообщение об ошибке. Основные исключения могут возникать
                   при проблемах сетевого соединения, ошибках аутентификации API или превышении
                   лимитов токенов.
    
    Note:
        Функция рассчитывает и логирует использование токенов для контроля затрат.
        При ошибках функция не генерирует исключения, а возвращает сообщение об ошибке
        как результат, что обеспечивает отказоустойчивость бота.
    """
    try:
        # Создаем контекстный логгер для GPT запросов
        gpt_logger = get_user_logger(
            user_id=user_id,  # Используем переданный ID пользователя
            operation="gpt_request"
        )
        
        gpt_logger.info("Формирование запроса к API")
        # Формируем сообщения для API
        api_messages = []
        
        # Получаем последнее сообщение пользователя для поиска контекста
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "")
                break
        
        # Получаем контекст из базы знаний с помощью векторного поиска
        knowledge_context = ""
        if vector_store and user_query:
            try:
                # Подключаемся к базе данных
                conn = sqlite3.connect(os.path.join(os.getcwd(), 'knowledge_base_v2.db'))
                
                # Получаем контекст для запроса
                gpt_logger.info(f"Поиск релевантного контекста для запроса: {user_query[:50]}...")
                knowledge_context = get_context_for_query(user_query, vector_store, conn, top_k=3, max_tokens=1000)
                
                # Закрываем соединение с базой данных
                conn.close()
                
                gpt_logger.info(f"Получен контекст размером {len(knowledge_context)} символов")
            except Exception as e:
                gpt_logger.error(f"Ошибка при получении контекста: {str(e)}")
        
        # Дополняем системное сообщение контекстом
        enhanced_system_content = system_content
        if knowledge_context:
            enhanced_system_content = augment_prompt_with_context(system_content, knowledge_context)
        
        # Добавляем системное сообщение
        if additional_system_content:
            api_messages.append({"role": "system", "content": enhanced_system_content + "\n\n" + additional_system_content})
        else:
            api_messages.append({"role": "system", "content": enhanced_system_content})
        
        # Добавляем историю диалога
        for msg in messages:
            api_messages.append(msg)
        
        # Логируем токены с передачей ID пользователя
        token_count = token_counter.log_tokens_usage(OPENAI_MODEL, api_messages, user_id=user_id)
        gpt_logger.info(f"Использовано токенов: {token_count}")
        
        # Отправляем запрос к API
        gpt_logger.info(f"Отправка запроса к модели {OPENAI_MODEL}")
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=api_messages,
            temperature=0.3,
            max_tokens=2000
        )
        
        gpt_logger.info("Получен ответ от API")
        
        # Постобработка ответа
        response_text = response.choices[0].message.content
        
        # Заменяем Markdown на HTML (** на <b>)
        response_text = convert_markdown_to_html(response_text)
        gpt_logger.info("Постобработка: Markdown заменен на HTML")
        
        # Считаем токены
        token_counter.log_tokens_usage(
            OPENAI_MODEL, 
            messages,
            response_text,
            user_id
        )
        
        return response_text
        
    except Exception as e:
        gpt_logger = get_user_logger(user_id=user_id, operation="gpt_error")
        gpt_logger.error(f"Ошибка при запросе к GPT: {str(e)}", exc_info=True)
        return "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз или обратитесь к администратору."

def convert_markdown_to_html(text):
    """
    Преобразует Markdown разметку в HTML.
    
    Функция выполняет конвертацию базовых элементов Markdown в HTML-теги:
    - **текст** -> <b>текст</b> (жирный шрифт)
    - * элемент списка -> • элемент списка (маркированные списки)
    - # Заголовок -> <b>Заголовок</b> (заголовки разных уровней)
    
    Используется для обработки ответов от OpenAI API, которые 
    иногда содержат Markdown-разметку, не поддерживаемую Telegram.
    
    Args:
        text (str): Входной текст, который может содержать Markdown-разметку
        
    Returns:
        str: Обработанный текст с HTML-тегами вместо Markdown
    
    Note:
        Функция использует регулярные выражения (re.sub) для выполнения замен,
        что может быть не оптимально при очень больших объемах текста. 
        Поддерживаются только основные элементы Markdown (жирный шрифт, 
        маркированные списки и заголовки).
    
    Примеры:
        >>> convert_markdown_to_html("Это **жирный** текст")
        "Это <b>жирный</b> текст"
        
        >>> convert_markdown_to_html("* Элемент списка")
        "• Элемент списка"
        
        >>> convert_markdown_to_html("# Заголовок")
        "<b>Заголовок</b>"
    """
    # Заменяем **текст** на <b>текст</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Заменяем * для маркированных списков, если они отдельно стоят в начале строки
    text = re.sub(r'(?m)^[ \t]*\*[ \t]+', r'• ', text)
    
    # Заменяем #, ##, ### заголовки на <b>текст</b>
    text = re.sub(r'(?m)^[ \t]*#{1,3}[ \t]+(.*?)[ \t]*$', r'<b>\1</b>', text)
    
    return text

# Основная функция запуска бота
async def main():
    """
    Основная функция запуска бота.
    
    Инициализирует и запускает бота Telegram с настроенными командами меню.
    Эта функция является точкой входа для запуска бота в асинхронном режиме.
    
    Действия:
    1. Инициализирует общий логгер для отслеживания старта бота
    2. Инициализирует базу данных SQLite для логирования
    3. Инициализирует векторное хранилище FAISS
    4. Запускает процесс очистки неактивных сессий
    5. Устанавливает команды меню бота в интерфейсе Telegram
    6. Запускает поллинг для обработки сообщений
    
    Args:
        Нет аргументов
        
    Returns:
        None
        
    Raises:
        Не обрабатывает исключения напрямую, они обрабатываются в вызывающей функции
    """
    # Создаем общий логгер без контекста пользователя
    logger.info("Starting bot...")
    
    # Инициализируем базу данных SQLite
    try:
        init_database()
        logger.info("База данных SQLite инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
    
    # Инициализируем векторное хранилище FAISS
    try:
        global vector_store
        vector_store = FAISSVectorStore(embedding_dimension=1536)
        logger.info("Векторное хранилище FAISS инициализировано")
    except Exception as e:
        logger.error(f"Ошибка при инициализации векторного хранилища: {str(e)}")
    
    # Запускаем процесс очистки неактивных сессий в фоновом режиме
    try:
        asyncio.create_task(start_cleaner(storage, interval_seconds=300))  # Проверка каждые 5 минут
        logger.info("Запущен процесс очистки неактивных сессий")
    except Exception as e:
        logger.error(f"Ошибка при запуске очистки сессий: {str(e)}")
    
    # Устанавливаем команды меню бота
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать новый диалог"),
        types.BotCommand(command="cancel", description="Прервать текущее интервью")
    ])
    
    # Запускаем бота
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main()) 