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
from utils.keyboards import create_main_inline_keyboard, create_level_selection_keyboard, create_mixed_inline_keyboard
from utils.database import init_database, log_message
from utils.session_cleaner import update_user_activity, start_cleaner
import datetime
import re  # Добавляем импорт модуля регулярных выражений
from prompts import LEARNING_ASSISTANT_PROMPT, INSTRUCTION, WELCOME_MESSAGE, FIRST_QUESTION_PROMPT, RELATED_TOPICS_PROMPT, SUMMARY_PROMPT, DEEPER_TOPIC_PROMPT, UNDERSTANDING_CHECK_PROMPT, MAIN_POINTS_PROMPT, SUMMARY_GENERATION_PROMPT

# Количество сообщений пользователя, после которых начинают показываться кнопки
BUTTONS_APPEAR_AFTER_USER_MESSAGES = 2

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота и диспетчера с хранилищем состояний
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация OpenAI клиента
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
        parse_mode="HTML",
        reply_markup=create_mixed_inline_keyboard(show_additional_buttons=False)
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
    
    Действия:
    1. Создает контекстный логгер для текущего пользователя и сообщения
    2. Извлекает текущее состояние диалога
    3. Добавляет сообщение пользователя в историю диалога    
    4. Анализирует тему вопроса и определяет связанные темы
    5. Выбирает дополнительный промпт в зависимости от контекста
    6. Получает ответ от GPT, включая предложения связанных тем
    7. Обновляет состояние диалога
    8. Обновляет информацию об активности пользователя в базе данных
    9. Автоматически резюмирует и сбрасывает контекст после 3 вопросов пользователя,
       сохраняя при этом краткое содержание предыдущего диалога для сохранения контекста
    
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
        # Получаем данные о последнем сообщении с кнопками
        data = await state.get_data()
        last_bot_message_id = data.get("last_bot_message_id")
        
        # Если есть предыдущее сообщение с кнопками, удаляем клавиатуру
        if last_bot_message_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=last_bot_message_id,
                    reply_markup=None
                )
            except Exception as e:
                user_logger.error(f"Ошибка при удалении старой клавиатуры: {str(e)}")
        
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
            
            # Генерируем резюме диалога перед сбросом контекста
            dialog_summary = await generate_dialog_summary(messages, message.from_user.id)
            request_logger.info("Создано резюме диалога для сохранения контекста")
            
            # Сохраняем только системное сообщение и резюме, сбрасывая историю диалога
            messages = [{"role": "system", "content": LEARNING_ASSISTANT_PROMPT}]
            
            # Если удалось создать резюме, добавляем его как системное сообщение
            if dialog_summary:
                messages.append({"role": "system", "content": f"Предыдущий контекст диалога: {dialog_summary}"})
                request_logger.info(f"Добавлено резюме диалога размером {len(dialog_summary)} символов")
            
            # Сбрасываем счетчик сообщений
            message_counter = 0
        
        # Добавляем сообщение пользователя в историю
        messages.append({"role": "user", "content": message.text})
        
        # Проверяем, нужно ли показывать кнопки в этом сообщении
        show_buttons = should_show_buttons(messages)
        
        # Анализируем тему вопроса
        topic_data = await analyze_topic(messages, message.from_user.id)
        main_topic = topic_data.get("main_topic", "")
        related_topics = topic_data.get("related_topics", [])
        
        # Обновляем информацию о темах
        if main_topic:
            if main_topic != topics["current"] and topics["current"]:
                # Если тема изменилась, добавляем предыдущую в историю
                topics["history"].append(topics["current"])
            
            topics["current"] = main_topic
            
            # Сохраняем связанные темы
            topics["related_topics"][main_topic] = related_topics
        
        # Выбираем дополнительный промпт
        additional_prompt = select_additional_prompt(messages, user_knowledge_level)
        
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
        
        # Добавляем инструкцию с дополнительным промптом
        instruction = INSTRUCTION
        if additional_prompt:
            instruction += f"\n\n{additional_prompt}"
        
        # Добавляем информацию об уровне специалиста
        level_descriptions = {
            "beginner": "Технический специалист (Уровень 1): Базовый уровень знаний, работа под руководством, выполнение стандартных процедур.",
            "intermediate": "Квалифицированный специалист (Уровень 2): Самостоятельное проведение контроля, интерпретация результатов, соответствие стандартам.",
            "advanced": "Экспертный специалист (Уровень 3): Глубокое понимание методик, разработка процедур контроля, сертификация и обучение."
        }
        
        level_info = f"Уровень пользователя: {level_descriptions.get(user_knowledge_level['general'], 'Не определен')}"
        instruction += f"\n\nВАЖНО: {level_info}\nАдаптируй сложность и детализацию ответа в соответствии с уровнем пользователя."
        
        # Получаем ответ от GPT с контекстом
        gpt_response = await get_gpt_response(
            messages,
            system_prompt, 
            f"Контекст: {json.dumps(context, ensure_ascii=False)}\n\nИнструкция: {instruction}",
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
            parse_mode="HTML",
            reply_markup=create_mixed_inline_keyboard(show_additional_buttons=show_buttons)
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
    
    Действия:
    1. Создает контекстный логгер для GPT запросов
    2. Формирует сообщения для API с системным промптом и историей диалога
    3. Отправляет запрос к выбранной модели OpenAI
    4. Обрабатывает ответ, конвертируя Markdown в HTML
    5. Учитывает токены и стоимость запроса
    
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
        
        # Добавляем системное сообщение
        if additional_system_content:
            api_messages.append({"role": "system", "content": system_content + "\n\n" + additional_system_content})
        else:
            api_messages.append({"role": "system", "content": system_content})
        
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
        
        # Логируем ответ от GPT - ТОЛЬКО один раз
        # Удаляем дублирующий лог:
        # log_bot_response(user_id, f"[RAW GPT RESPONSE] {response_text}")
        
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

def should_show_buttons(messages):
    """
    Определяет, нужно ли показывать вспомогательные кнопки в текущем состоянии диалога.
    
    Функция анализирует историю сообщений диалога и на основе 
    константы BUTTONS_APPEAR_AFTER_USER_MESSAGES определяет, 
    должны ли отображаться кнопки "Дай пример" и "Объясни" в интерфейсе.
    
    Кнопки показываются только после определенного количества сообщений
    пользователя, чтобы не перегружать интерфейс в начале диалога, когда
    пользователь только знакомится с ботом.
    
    Args:
        messages (list): Список словарей с историей сообщений диалога.
                        Каждое сообщение имеет ключи "role" (роль: "user" или "assistant")
                        и "content" (содержимое сообщения).
        
    Returns:
        bool: True, если кнопки должны отображаться, False в противном случае.
    
    Note:
        Количество сообщений, после которого появятся кнопки, настраивается через
        константу BUTTONS_APPEAR_AFTER_USER_MESSAGES. При значении 4 кнопки появятся
        после 4-го сообщения пользователя (т.е. на 5-м сообщении бота).
    """
    # Если сообщений нет или их меньше 2, кнопки не показываем
    if not messages or len(messages) < 2:
        return False
    
    # Подсчитываем количество сообщений пользователя в истории диалога
    user_messages_count = len([msg for msg in messages if msg["role"] == "user"])
    
    # Проверяем, достаточно ли сообщений от пользователя для отображения кнопок
    return user_messages_count >= BUTTONS_APPEAR_AFTER_USER_MESSAGES

# Основная функция запуска бота
async def main():
    """
    Основная функция запуска бота.
    
    Инициализирует и запускает бота Telegram с настроенными командами меню.
    Эта функция является точкой входа для запуска бота в асинхронном режиме.
    
    Действия:
    1. Инициализирует общий логгер для отслеживания старта бота
    2. Инициализирует базу данных SQLite для логирования
    3. Запускает процесс очистки неактивных сессий
    4. Устанавливает команды меню бота в интерфейсе Telegram
    5. Запускает поллинг для обработки сообщений
    
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

@dp.callback_query(lambda c: c.data in ["give_example", "explain"])
async def process_main_keyboard_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    # Получаем текст команды
    text = "Объясни"
    
    # Логируем команду как обычное сообщение
    log_user_message(callback.from_user.id, text)
    
    # Обрабатываем команду напрямую как сообщение пользователя
    data = await state.get_data()
    messages = data.get("messages", [])
    messages.append({"role": "user", "content": text})
    
    # Получаем информацию об уровне знаний пользователя
    user_knowledge_level = data.get("user_knowledge_level", {"general": "beginner", "topics": {}})
    
    # Показываем индикатор набора текста
    typing_task = asyncio.create_task(keep_typing(callback.message.chat.id))
    
    try:
        # Создаем дополнительную инструкцию с учетом уровня специалиста
        level_descriptions = {
            "beginner": "Технический специалист (Уровень 1): Базовый уровень знаний, работа под руководством, выполнение стандартных процедур.",
            "intermediate": "Квалифицированный специалист (Уровень 2): Самостоятельное проведение контроля, интерпретация результатов, соответствие стандартам.",
            "advanced": "Экспертный специалист (Уровень 3): Глубокое понимание методик, разработка процедур контроля, сертификация и обучение."
        }
        
        level_info = f"Уровень пользователя: {level_descriptions.get(user_knowledge_level['general'], 'Не определен')}"
        additional_instruction = f"\n\nВАЖНО: {level_info}\nДай объяснение с учетом уровня пользователя, адаптируя сложность и детализацию ответа."
        
        # Получаем ответ от модели
        response = await get_gpt_response(
            messages,
            LEARNING_ASSISTANT_PROMPT,
            additional_system_content=additional_instruction,
            user_id=callback.from_user.id
        )
        
        # Сохраняем ответ
        messages.append({"role": "assistant", "content": response})
        await state.update_data(messages=messages)
        
        # Обновляем информацию об активности пользователя в базе данных
        await update_user_activity(user_id=callback.from_user.id, state=state)
        
        # Проверяем, нужно ли показывать кнопки
        show_buttons = should_show_buttons(messages)
        
        # Отправляем ответ
        sent_message = await callback.message.answer(
            response, 
            parse_mode="HTML", 
            reply_markup=create_mixed_inline_keyboard(show_additional_buttons=show_buttons)
        )
        await state.update_data(last_bot_message_id=sent_message.message_id)
        
        # Логируем ответ
        log_bot_response(callback.from_user.id, response)
        
        # Отменяем задачу обновления статуса
        typing_task.cancel()
        
    except Exception as e:
        # Отменяем задачу обновления статуса в случае ошибки
        typing_task.cancel()
        logger.error(f"Ошибка при обработке callback-запроса: {str(e)}", exc_info=True)
        await callback.message.answer("Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз.", parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "new_question")
async def process_new_question_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия на кнопку "Новый вопрос".
    
    Действия:
    1. Сбрасывает контекст беседы (историю сообщений)
    2. Сохраняет базовое состояние бота
    3. Отправляет сообщение о начале нового диалога
    4. Обновляет информацию об активности пользователя в базе данных
    
    Args:
        callback (types.CallbackQuery): Объект callback-запроса
        state (FSMContext): Контекст состояния бота
    """
    await callback.answer("Начинаем новый вопрос")
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Логируем действие
    log_user_message(callback.from_user.id, "[ACTION] Новый вопрос")
    
    user_logger = get_user_logger(
        user_id=callback.from_user.id,
        operation="new_question"
    )
    user_logger.info("Пользователь запросил сброс контекста беседы")
    
    # Сохраняем текущее состояние, но сбрасываем историю сообщений
    data = await state.get_data()
    
    # Сбрасываем историю, но сохраняем базовое состояние и информацию о темах
    await state.update_data(
        messages=[{"role": "system", "content": LEARNING_ASSISTANT_PROMPT}],
        answers=data.get("answers", {}),
        topics=data.get("topics", {"current": "", "history": [], "related_topics": {}}),
        user_knowledge_level=data.get("user_knowledge_level", {"general": "beginner", "topics": {}}),
        message_counter=0  # Сбрасываем счетчик сообщений
    )
    
    # Обновляем информацию об активности пользователя в базе данных
    await update_user_activity(user_id=callback.from_user.id, state=state)
    
    # Отправляем сообщение о начале нового диалога
    response = "Контекст беседы сброшен. Вы можете задать новый вопрос по любой интересующей вас теме."
    
    sent_message = await callback.message.answer(
        response,
        parse_mode="HTML",
        reply_markup=create_main_inline_keyboard()
    )
    
    # Сохраняем ID сообщения для последующего удаления клавиатуры
    await state.update_data(last_bot_message_id=sent_message.message_id)
    
    # Логируем ответ бота
    log_bot_response(callback.from_user.id, response)

@dp.callback_query(lambda c: c.data == "select_level")
async def process_select_level_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия на кнопку "Выбрать уровень специалиста".
    
    Действия:
    1. Отображает клавиатуру с выбором уровня специалиста в области НК
    2. Логирует действие пользователя
    
    Args:
        callback (types.CallbackQuery): Объект callback-запроса
        state (FSMContext): Контекст состояния бота
    """
    await callback.answer("Выберите ваш уровень квалификации в НК")
    
    # Логируем действие
    log_user_message(callback.from_user.id, "[ACTION] Запрос выбора уровня специалиста")
    
    user_logger = get_user_logger(
        user_id=callback.from_user.id,
        operation="select_level"
    )
    user_logger.info("Пользователь запросил выбор уровня специалиста")
    
    # Отправляем сообщение с описанием уровней и клавиатурой выбора
    message_text = """<b>Выберите ваш уровень квалификации в неразрушающем контроле:</b>

<b>Уровень 1 (Технический)</b>
Специалисты, которые выполняют контроль под руководством более опытных коллег. Могут использовать оборудование и следовать установленным процедурам.

<b>Уровень 2 (Квалифицированный)</b>
Специалисты, которые самостоятельно проводят контроль, интерпретируют результаты и обеспечивают соответствие стандартам. Могут обучать других.

<b>Уровень 3 (Экспертный)</b>
Специалисты с глубокими знаниями в области НК. Разрабатывают методики контроля, проводят анализ результатов, участвуют в разработке стандартов.

Я адаптирую свои ответы в соответствии с выбранным уровнем.
"""
    
    # Отправляем сообщение с кнопками выбора уровня
    sent_message = await callback.message.answer(
        message_text,
        parse_mode="HTML",
        reply_markup=create_level_selection_keyboard()
    )
    
    # Сохраняем ID сообщения для последующего удаления клавиатуры
    await state.update_data(last_bot_message_id=sent_message.message_id)
    
    # Скрываем кнопки предыдущего сообщения
    await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(lambda c: c.data in ["level_1", "level_2", "level_3"])
async def process_level_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора уровня специалиста.
    
    Действия:
    1. Обновляет информацию о выбранном уровне специалиста в состоянии диалога
    2. Адаптирует последующие ответы бота под выбранный уровень
    3. Отправляет подтверждение о выборе уровня
    
    Args:
        callback (types.CallbackQuery): Объект callback-запроса
        state (FSMContext): Контекст состояния бота
    """
    level_data = {
        "level_1": {"level": "beginner", "name": "Технический (Уровень 1)"},
        "level_2": {"level": "intermediate", "name": "Квалифицированный (Уровень 2)"},
        "level_3": {"level": "advanced", "name": "Экспертный (Уровень 3)"}
    }
    
    selected_level = level_data[callback.data]
    await callback.answer(f"Выбран {selected_level['name']} уровень")
    
    # Логируем выбор пользователя
    log_user_message(callback.from_user.id, f"[ACTION] Выбран уровень специалиста: {selected_level['name']}")
    
    user_logger = get_user_logger(
        user_id=callback.from_user.id,
        operation="level_selected"
    )
    user_logger.info(f"Пользователь выбрал уровень специалиста: {selected_level['name']}")
    
    # Получаем текущее состояние
    data = await state.get_data()
    user_knowledge_level = data.get("user_knowledge_level", {"general": "beginner", "topics": {}})
    
    # Обновляем уровень знаний пользователя
    user_knowledge_level["general"] = selected_level["level"]
    
    # Сохраняем обновленное состояние
    await state.update_data(user_knowledge_level=user_knowledge_level)
    
    # Отправляем подтверждение
    confirmation_text = f"""<b>Выбран уровень: {selected_level['name']}</b>

Я буду адаптировать свои ответы в соответствии с вашим уровнем знаний.
Вы можете изменить уровень в любой момент через кнопку "Выбрать уровень специалиста".

Задавайте вопросы по неразрушающему контролю, и я постараюсь дать наиболее подходящие ответы.
"""
    
    sent_message = await callback.message.answer(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=create_mixed_inline_keyboard(show_additional_buttons=True)
    )
    
    # Сохраняем ID сообщения
    await state.update_data(last_bot_message_id=sent_message.message_id)
    
    # Скрываем кнопки предыдущего сообщения
    await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(lambda c: c.data == "back_to_main")
async def process_back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия на кнопку возврата к основной клавиатуре.
    
    Действия:
    1. Возвращает основную клавиатуру с кнопками
    2. Логирует действие пользователя
    
    Args:
        callback (types.CallbackQuery): Объект callback-запроса
        state (FSMContext): Контекст состояния бота
    """
    await callback.answer("Возврат к основному меню")
    
    # Логируем действие
    log_user_message(callback.from_user.id, "[ACTION] Возврат к основному меню")
    
    # Скрываем кнопки предыдущего сообщения
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Отправляем сообщение с основной клавиатурой
    sent_message = await callback.message.answer(
        "Вы вернулись в основное меню. Задавайте вопросы по неразрушающему контролю.",
        parse_mode="HTML",
        reply_markup=create_mixed_inline_keyboard(show_additional_buttons=True)
    )
    
    # Сохраняем ID сообщения
    await state.update_data(last_bot_message_id=sent_message.message_id)

async def generate_dialog_summary(messages, user_id):
    """
    Создает краткое резюме предыдущего диалога для сохранения контекста при уменьшении токенов.
    
    Функция отправляет запрос к модели GPT для создания компактного резюме диалога,
    которое сохраняет ключевую информацию и контекст, но занимает меньше токенов,
    чем полная история сообщений.
    
    Действия:
    1. Создает контекстный логгер для операции резюмирования
    2. Отправляет запрос к GPT с историей сообщений и специальным промптом
    3. Получает и возвращает сгенерированное резюме
    
    Args:
        messages (list): История сообщений диалога для резюмирования
        user_id (int): ID пользователя для логирования
        
    Returns:
        str: Краткое резюме диалога, содержащее ключевую информацию
        
    Raises:
        Exception: Обрабатывается внутри функции, в случае ошибки возвращается
                   пустое резюме и информация логируется
    """
    # Создаем контекстный логгер
    summary_logger = get_user_logger(
        user_id=user_id,
        operation="dialog_summary"
    )
    
    summary_logger.info("Создание резюме диалога из истории сообщений")
    
    # Проверяем, достаточно ли сообщений для резюмирования
    if len(messages) < 3:
        summary_logger.info("Недостаточно сообщений для резюмирования")
        return ""
    
    try:
        # Отправляем запрос к GPT для создания резюме
        response = await get_gpt_response(
            # Отправляем историю сообщений для анализа, но без системного промпта
            [msg for msg in messages if msg["role"] != "system"],
            # Используем специальный промпт для генерации резюме
            SUMMARY_GENERATION_PROMPT,
            user_id=user_id
        )
        
        summary_logger.info("Резюме диалога успешно создано")
        return response
        
    except Exception as e:
        summary_logger.error(f"Ошибка при создании резюме диалога: {str(e)}", exc_info=True)
        return ""

async def analyze_topic(messages, user_id):
    """
    Анализирует тему вопроса пользователя и определяет связанные темы.
    
    Args:
        messages (list): История сообщений диалога
        user_id (int): ID пользователя для логирования
        
    Returns:
        dict: Словарь с основной темой и связанными темами
    """
    # Создаем контекстный логгер
    topic_logger = get_user_logger(
        user_id=user_id,
        operation="analyze_topic"
    )
    
    topic_logger.info("Анализ темы вопроса пользователя")
    
    # Определяем последний вопрос пользователя
    user_messages = [msg for msg in messages if msg["role"] == "user"]
    if not user_messages:
        topic_logger.warning("История сообщений не содержит вопросов пользователя")
        return {"main_topic": "", "related_topics": []}
    
    last_user_message = user_messages[-1]["content"]
    
    # Запрашиваем у GPT анализ темы и связанных тем
    try:
        response = await get_gpt_response(
            [{"role": "system", "content": RELATED_TOPICS_PROMPT},
             {"role": "user", "content": last_user_message}],
            "",
            user_id=user_id
        )
        
        # Извлекаем JSON с темами
        topic_data = {}
        try:
            # Ищем JSON в ответе
            import re
            import json
            
            # Паттерн для поиска JSON-объекта в тексте
            json_match = re.search(r'({[\s\S]*})', response)
            if json_match:
                json_str = json_match.group(1)
                topic_data = json.loads(json_str)
                topic_logger.info(f"Определена основная тема: {topic_data.get('main_topic')}")
            else:
                topic_logger.warning("JSON с темами не найден в ответе")
                topic_data = {"main_topic": "", "related_topics": []}
        except Exception as e:
            topic_logger.error(f"Ошибка при извлечении тем из ответа: {str(e)}")
            topic_data = {"main_topic": "", "related_topics": []}
            
        return topic_data
        
    except Exception as e:
        topic_logger.error(f"Ошибка при анализе темы: {str(e)}")
        return {"main_topic": "", "related_topics": []}

def select_additional_prompt(messages, user_knowledge_level):
    """
    Выбирает дополнительный промпт на основе контекста диалога.
    
    Args:
        messages (list): История сообщений диалога
        user_knowledge_level (dict): Уровень знаний пользователя
        
    Returns:
        str: Выбранный дополнительный промпт или пустая строка
    """
    # Если сообщений мало, не используем дополнительные промпты
    if len(messages) < 2:
        return ""
    
    # Определяем количество сообщений пользователя
    user_messages = [msg for msg in messages if msg["role"] == "user"]
    
    # При первых нескольких сообщениях часто предлагаем главные тезисы
    # для помощи пользователю в структурировании знаний
    if 1 <= len(user_messages) <= 3:
        return MAIN_POINTS_PROMPT
    
    # Если это серия вопросов по одной теме (4 и более), предлагаем резюме
    elif len(user_messages) >= 4:
        return SUMMARY_PROMPT
    
    # Если у пользователя продвинутый уровень по теме, предлагаем углубление
    # Уровень знаний определяется по контексту предыдущих сообщений
    general_level = user_knowledge_level.get("general", "beginner")
    if general_level in ["intermediate", "advanced"]:
        return DEEPER_TOPIC_PROMPT
    
    # По умолчанию чередуем проверку понимания и предложение тезисов
    if len(user_messages) % 2 == 0:
        return UNDERSTANDING_CHECK_PROMPT
    else:
        return MAIN_POINTS_PROMPT

if __name__ == "__main__":
    asyncio.run(main()) 