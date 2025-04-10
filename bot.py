import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
import json
from openai import AsyncOpenAI
from utils.logger import logger, get_user_logger, log_user_message, log_bot_response
from utils.token_counter import token_counter
from utils.keyboards import create_main_inline_keyboard
import datetime
import re  # Добавляем импорт модуля регулярных выражений
from prompts import INTERVIEWER_PROMPT, INSTRUCTION, WELCOME_MESSAGE, FIRST_QUESTION_PROMPT

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
    одно состояние (INTERVIEWER) для проведения всего интервью.
    
    Attributes:
        INTERVIEWER (State): Состояние работы HR-интервьюера. В этом состоянии
                           бот собирает информацию для создания профиля кандидата.
    
    Note:
        Для расширения функциональности бота можно добавить дополнительные состояния.
        Например, для редактирования профиля или других режимов работы.
    """
    INTERVIEWER = State()  # Состояние работы первого агента (Интервьюер)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start. Инициализирует новый диалог с пользователем.
    
    Действия:
    1. Создает контекстный логгер для отслеживания действий пользователя
    2. Очищает предыдущее состояние и историю диалога
    3. Инициализирует новый диалог в состоянии INTERVIEWER
    4. Отправляет приветственное сообщение напрямую из константы
    5. Запрашивает первый вопрос через GPT
    6. Отображает индикатор "печатает" во время генерации ответа
    
    Args:
        message (types.Message): Объект сообщения Telegram с данными пользователя и чата
        state (FSMContext): Контекст состояния для хранения данных диалога
        
    Returns:
        None
        
    Raises:
        openai.APIError: Возникает при проблемах с OpenAI API, таких как ошибки аутентификации,
                         превышение лимитов запросов или недоступность сервиса
        aiogram.exceptions.TelegramAPIError: Возникает при проблемах отправки сообщения в Telegram API
        asyncio.TimeoutError: Возникает при превышении времени ожидания ответа от API
        Exception: Обработка всех остальных ошибок с логированием и отправкой пользователю 
                 сообщения об ошибке
    
    Note:
        Команда /start всегда сбрасывает предыдущее состояние диалога и начинает новое интервью.
        Также сбрасывается счетчик токенов для корректного учета использования API.
        Первое сообщение отправляется без клавиатуры, так как это приветствие.
    """
    # Создаем логгер с контекстом пользователя
    user_logger = get_user_logger(
        user_id=message.from_user.id, 
        operation="start_command"
    )
    
    user_logger.info(f"Пользователь запустил бота командой /start")
    
    # Сбрасываем счетчик токенов при запуске нового диалога
    token_counter.reset_counters()
    user_logger.info("Счетчик токенов сброшен")
    
    # Логируем команду запуска
    log_user_message(message.from_user.id, "[COMMAND] /start")
    
    # Очищаем предыдущую историю диалога
    await state.clear()
    
    # Инициализируем новый диалог
    await state.set_state(BotStates.INTERVIEWER)
    await state.update_data(
        answers={},
        profile_generated=False
    )
    
    # Отправляем приветственное сообщение напрямую из константы
    await message.answer(
        WELCOME_MESSAGE, 
        parse_mode="HTML"
    )
    
    # Логируем ответ бота
    log_bot_response(message.from_user.id, WELCOME_MESSAGE)
    
    # Показываем индикатор набора текста
    typing_task = asyncio.create_task(keep_typing(message.chat.id))
    
    try:
        user_logger.info("Отправка запроса на первый вопрос")
        # Отправляем запрос на получение первого вопроса
        response = await get_gpt_response(
            [],
            INTERVIEWER_PROMPT,
            FIRST_QUESTION_PROMPT,
            user_id=message.from_user.id
        )
        
        # Сохраняем сообщения в истории
        await state.update_data(messages=[
            {"role": "system", "content": INTERVIEWER_PROMPT},
            {"role": "assistant", "content": WELCOME_MESSAGE},  # Добавляем приветствие в историю
            {"role": "assistant", "content": response}  # Добавляем первый вопрос в историю
        ])
        
        user_logger.info("Отправка первого вопроса пользователю")
        
        # Отправляем сообщение БЕЗ клавиатуры
        await message.answer(
            response, 
            parse_mode="HTML"
        )
        
        # Логируем полный ответ бота
        log_bot_response(message.from_user.id, response)
        
        # Отменяем задачу обновления статуса
        typing_task.cancel()
        
    except Exception as e:
        # Отменяем задачу обновления статуса в случае ошибки
        typing_task.cancel()
        user_logger.error(f"Ошибка при обработке /start: {str(e)}", exc_info=True)
        await message.answer("Произошла ошибка при запуске бота. Пожалуйста, попробуйте еще раз.", parse_mode="HTML")

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
@dp.message(BotStates.INTERVIEWER)
async def process_message(message: types.Message, state: FSMContext):
    """
    Основной обработчик всех сообщений пользователя в состоянии INTERVIEWER.
    
    Этот обработчик принимает все сообщения пользователя,
    анализирует их и формирует ответы с помощью OpenAI API.
    
    Действия:
    1. Создает контекстный логгер для текущего пользователя и сообщения
    2. Извлекает текущее состояние диалога
    3. Добавляет сообщение пользователя в историю диалога    
    4. Обновляет состояние диалога
    
    Args:
        message (types.Message): Объект сообщения Telegram с данными пользователя
        state (FSMContext): Контекст состояния для хранения данных диалога
        
    Returns:
        None
        
    Raises:
        aiogram.exceptions.TelegramAPIError: Возникает при проблемах взаимодействия с Telegram API,
                                            например, при удалении клавиатуры или отправке сообщения
        json.JSONDecodeError: Возникает при ошибках парсинга JSON в ответе от GPT
        openai.APIError: Возникает при проблемах с OpenAI API
        asyncio.TimeoutError: Возникает при превышении времени ожидания ответа от API
        Exception: Обработка всех остальных ошибок с логированием
    
    Note:
        Функция использует индикатор "печатает" для улучшения пользовательского опыта.
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
        
        # Создаем идентификатор сессии для логирования всех действий в рамках этого запроса
        session_id = f"msg_{int(datetime.datetime.now().timestamp())}"
        request_logger = get_user_logger(
            user_id=message.from_user.id,
            session_id=session_id,
            operation="process_message"
        )
        
        # Добавляем сообщение пользователя в историю
        messages.append({"role": "user", "content": message.text})
        
        # Проверяем, нужно ли показывать кнопки в этом сообщении
        # Используем функцию should_show_buttons для определения момента появления кнопок
        show_buttons = should_show_buttons(messages)
        
        # Формируем системный промпт
        system_prompt = INTERVIEWER_PROMPT
        
        # Создаем контекст для передачи в GPT
        context = {
            "answers": answers,
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
            answers=answers
        )
        
        request_logger.info("Отправка ответа пользователю")

        # Отправляем новое сообщение и сохраняем его ID
        sent_message = await message.answer(
            gpt_response, 
            parse_mode="HTML",
            reply_markup=create_main_inline_keyboard() if show_buttons else None
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
            temperature=0.5,
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
    2. Устанавливает команды меню бота в интерфейсе Telegram
    3. Запускает поллинг для обработки сообщений
    
    Args:
        Нет аргументов
        
    Returns:
        None
        
    Raises:
        Не обрабатывает исключения напрямую, они обрабатываются в вызывающей функции
    """
    # Создаем общий логгер без контекста пользователя
    logger.info("Starting bot...")
    
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
    
    # Показываем индикатор набора текста
    typing_task = asyncio.create_task(keep_typing(callback.message.chat.id))
    
    try:
        # Получаем ответ от модели
        response = await get_gpt_response(
            messages,
            INTERVIEWER_PROMPT,
            user_id=callback.from_user.id
        )
        
        # Сохраняем ответ
        messages.append({"role": "assistant", "content": response})
        await state.update_data(messages=messages)
        
        # Проверяем, нужно ли показывать кнопки
        show_buttons = should_show_buttons(messages)
        
        # Отправляем ответ
        sent_message = await callback.message.answer(
            response, 
            parse_mode="HTML", 
            reply_markup=create_main_inline_keyboard() if show_buttons else None
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
    
    # Сбрасываем историю, но сохраняем базовое состояние
    await state.update_data(
        messages=[{"role": "system", "content": INTERVIEWER_PROMPT}],
        answers=data.get("answers", {}),
        profile_generated=data.get("profile_generated", False)
    )
    
    # Отправляем сообщение о начале нового диалога
    response = "Контекст беседы сброшен. Вы можете задать новый вопрос по любому направлению неразрушающего контроля."
    
    sent_message = await callback.message.answer(
        response,
        parse_mode="HTML",
        reply_markup=create_main_inline_keyboard()
    )
    
    # Сохраняем ID сообщения для последующего удаления клавиатуры
    await state.update_data(last_bot_message_id=sent_message.message_id)
    
    # Логируем ответ бота
    log_bot_response(callback.from_user.id, response)

if __name__ == "__main__":
    asyncio.run(main()) 