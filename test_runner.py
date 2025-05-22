"""
Скрипт для запуска тестирования нейроконсультанта.

Использование:
1. Одиночный тест: python test_runner.py --question "Ваш вопрос"
2. Тестирование из файла: python test_runner.py --file questions.txt
3. Экспорт результатов: python test_runner.py --export results.csv
4. Для сохранения в Excel используйте расширение .xlsx:
   python test_runner.py --question "Ваш вопрос" --output results.xlsx
5. Для отключения векторного поиска:
   python test_runner.py --question "Ваш вопрос" --no-vector-search
"""
import os
import sys
import asyncio
import argparse
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импортируем бота и токены
from bot import bot, OPENAI_MODEL, get_gpt_response
from utils.test_framework import TestTable
from utils.logger import logger
from utils.database import init_database

# Примечание: объект bot передается в test_framework, но его методы не используются напрямую.
# Вместо этого используется импортированная функция get_gpt_response
async def run_tests():
    """
    Основная функция для запуска тестирования.
    Обрабатывает аргументы командной строки и запускает соответствующие тесты.
    """
    # Инициализируем базу данных перед началом тестирования
    try:
        init_database()
        logger.info("База данных SQLite инициализирована для тестирования")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        print(f"Ошибка при инициализации базы данных: {str(e)}")
    
    # Создаем парсер аргументов
    parser = argparse.ArgumentParser(description="Тестирование нейроконсультанта")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question", "-q", type=str, help="Вопрос для тестирования")
    group.add_argument("--file", "-f", type=str, help="Файл с вопросами для тестирования")
    group.add_argument("--export", "-e", type=str, help="Экспорт результатов в CSV или Excel (.xlsx)")
    parser.add_argument("--output", "-o", type=str, help="Файл для сохранения результатов (.csv или .xlsx)", default="test_results.xlsx")
    parser.add_argument("--tester", "-t", type=int, help="ID тестировщика", default=999)
    parser.add_argument("--no-vector-search", action="store_true", help="Отключить векторный поиск при тестировании")
    
    args = parser.parse_args()
    
    # Инициализируем векторное хранилище FAISS, если не указан флаг --no-vector-search
    if not args.no_vector_search:
        try:
            from utils.vector_search import FAISSVectorStore
            import bot
            bot.vector_store = FAISSVectorStore(embedding_dimension=1536)
            logger.info("Векторное хранилище FAISS инициализировано для тестирования")
            print("Векторное хранилище FAISS инициализировано для тестирования")
        except Exception as e:
            logger.error(f"Ошибка при инициализации векторного хранилища: {str(e)}")
            print(f"Ошибка при инициализации векторного хранилища: {str(e)}")
    else:
        logger.info("Векторный поиск отключен")
        print("Векторный поиск отключен")
        # Устанавливаем vector_store в None, чтобы отключить векторный поиск
        import bot
        bot.vector_store = None
    
    # Создаем экземпляр тестировщика
    test_table = TestTable(output_csv=args.output)
    
    # Обработка аргументов
    if args.export:
        # Экспорт результатов
        TestTable.export_results(args.export)
        return
    
    # Выводим информацию о тесте
    print(f"Тестирование нейроконсультанта")
    print(f"Модель: {OPENAI_MODEL}")
    print(f"Тестировщик ID: {args.tester}")
    print(f"Результаты будут сохранены в: {args.output}")
    print("-" * 50)
    
    if args.question:
        # Одиночный тест
        print(f"Запуск одиночного теста с вопросом: {args.question}")
        result = await test_table.run_test(args.question, bot, args.tester)
        if result:
            print("\nТест завершен успешно.")
    
    elif args.file:
        # Тестирование из файла
        print(f"Запуск тестирования из файла: {args.file}")
        results = await test_table.run_tests_from_file(args.file, bot, args.tester)
        if results:
            print(f"\nТестирование из файла завершено. Проведено {len(results)} тестов.")

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(run_tests()) 