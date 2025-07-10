#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерактивный анализатор Excel файлов

Описание: Полный анализ данных из Excel файлов с генерацией отчетов
Поддерживает интерактивное меню выбора режимов и файлов
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
import sys
import logging
from datetime import datetime
import argparse
import glob

# Настройка кодировки для Windows
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
warnings.filterwarnings('ignore')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/database_analysis.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def find_excel_files() -> list:
    """
    Находит все Excel файлы в текущей директории
    
    Возвращает:
    list: Список путей к Excel файлам
    """
    patterns = ['*.xlsx', '*.xls', '*.xlsm']
    excel_files = []
    
    for pattern in patterns:
        excel_files.extend(glob.glob(pattern))
    
    return sorted(excel_files)


def interactive_mode_selection() -> dict:
    """
    Интерактивный выбор режима работы анализатора
    
    Возвращает:
    dict: Параметры выбранного режима или None если отменено
    """
    print("\n🎯 ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:")
    print("=" * 60)
    
    modes = [
        {
            'id': 1,
            'name': '👁️  Быстрый просмотр файла',
            'description': 'Мгновенный обзор структуры без создания отчетов',
            'mode': 'preview'
        },
        {
            'id': 2, 
            'name': '🔥 Полный анализ',
            'description': 'Статистика + визуализации + отчет',
            'mode': 'full'
        },
        {
            'id': 3,
            'name': '⚡ Быстрый анализ',
            'description': 'Статистика + отчет (БЕЗ графиков)',
            'mode': 'quick'
        },
        {
            'id': 4,
            'name': '📊 Анализ без визуализаций',
            'description': 'Полный анализ для серверов без GUI',
            'mode': 'no_viz'
        },
        {
            'id': 5,
            'name': '❌ Выход',
            'description': 'Завершить работу',
            'mode': 'exit'
        }
    ]
    
    for mode in modes:
        print(f"{mode['id']:2d}. {mode['name']}")
        print(f"     {mode['description']}")
    
    print("=" * 60)
    
    while True:
        try:
            choice = input(f"👉 Выберите режим (1-{len(modes)}): ").strip()
            
            if not choice:
                continue
            
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(modes):
                selected_mode = modes[choice_num - 1]
                
                if selected_mode['mode'] == 'exit':
                    print("👋 До свидания!")
                    return None
                
                print(f"✅ Выбран режим: {selected_mode['name']}")
                return selected_mode
            else:
                print(f"❌ Неверный выбор. Введите число от 1 до {len(modes)}")
                
        except ValueError:
            print("❌ Введите корректное число")
        except KeyboardInterrupt:
            print("\n👋 Работа прервана пользователем")
            return None


def interactive_file_selection() -> str:
    """
    Интерактивный выбор файла из доступных Excel файлов
    
    Возвращает:
    str: Путь к выбранному файлу или None если отменено
    """
    excel_files = find_excel_files()
    
    if not excel_files:
        print("❌ В текущей директории не найдено Excel файлов!")
        print("💡 Убедитесь, что файлы имеют расширения .xlsx, .xls или .xlsm")
        return None
    
    print("\n📁 ДОСТУПНЫЕ EXCEL ФАЙЛЫ:")
    print("=" * 60)
    
    for i, file_path in enumerate(excel_files, 1):
        file_size = Path(file_path).stat().st_size / 1024**2  # размер в МБ
        print(f"{i:2d}. {file_path:<40} ({file_size:.2f} МБ)")
    
    print(f"{len(excel_files)+1:2d}. ❌ Отменить выбор")
    print("=" * 60)
    
    while True:
        try:
            choice = input(f"👉 Выберите файл (1-{len(excel_files)+1}): ").strip()
            
            if not choice:
                continue
            
            choice_num = int(choice)
            
            if choice_num == len(excel_files) + 1:
                print("🚫 Выбор отменен")
                return None
            
            if 1 <= choice_num <= len(excel_files):
                selected_file = excel_files[choice_num - 1]
                print(f"✅ Выбран файл: {selected_file}")
                return selected_file
            else:
                print(f"❌ Неверный выбор. Введите число от 1 до {len(excel_files)+1}")
                
        except ValueError:
            print("❌ Введите корректное число")
        except KeyboardInterrupt:
            print("\n🚫 Выбор отменен пользователем")
            return None


def quick_preview_mode(file_path: str):
    """
    Быстрый просмотр структуры Excel файла
    
    Параметры:
    file_path (str): Путь к Excel файлу
    """
    print("🔍 БЫСТРЫЙ ПРОСМОТР ФАЙЛА")
    print("=" * 60)
    print(f"📄 Файл: {file_path}")
    print("=" * 60)
    
    try:
        # Проверка существования файла
        if not Path(file_path).exists():
            print(f"❌ Файл {file_path} не найден!")
            return
        
        # Загрузка данных
        print("⏳ Загрузка данных...")
        data = pd.read_excel(file_path, engine='openpyxl')
        
        # Основная информация
        print(f"📊 Размер данных: {data.shape[0]} строк × {data.shape[1]} столбцов")
        print(f"💾 Размер в памяти: {data.memory_usage(deep=True).sum() / 1024**2:.2f} МБ")
        
        print("\n📋 СТОЛБЦЫ И ТИПЫ ДАННЫХ:")
        print("-" * 60)
        for i, (col, dtype) in enumerate(data.dtypes.items(), 1):
            non_null = data[col].count()
            null_count = len(data) - non_null
            print(f"{i:2d}. {col:<30} | {str(dtype):<15} | Заполнено: {non_null}/{len(data)} ({null_count} пропусков)")
        
        print(f"\n📈 ПЕРВЫЕ 5 СТРОК:")
        print("-" * 60)
        print(data.head().to_string())
        
        print(f"\n📊 ПОСЛЕДНИЕ 5 СТРОК:")
        print("-" * 60)
        print(data.tail().to_string())
        
        # Быстрая статистика по числовым столбцам
        numeric_cols = data.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            print(f"\n🔢 ЧИСЛОВЫЕ СТОЛБЦЫ (краткая статистика):")
            print("-" * 60)
            print(data[numeric_cols].describe().round(2).to_string())
        
        # Информация о категориальных столбцах
        text_cols = data.select_dtypes(include=['object']).columns
        if len(text_cols) > 0:
            print(f"\n📝 ТЕКСТОВЫЕ СТОЛБЦЫ:")
            print("-" * 60)
            for col in text_cols:
                unique_count = data[col].nunique()
                print(f"{col}: {unique_count} уникальных значений")
                if unique_count <= 10:
                    print(f"  Значения: {list(data[col].unique())}")
                else:
                    top_values = data[col].value_counts().head(3)
                    print(f"  Топ-3: {dict(top_values)}")
        
        print(f"\n✅ Просмотр завершен!")
        print(f"💡 Для полного анализа выберите соответствующий режим в меню")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
        print(f"💡 Убедитесь, что файл {file_path} существует и имеет правильный формат")


class DatabaseAnalyzer:
    """
    Класс для анализа данных из Excel файлов
    
    Методы:
    - load_data(): Загружает данные из Excel файла
    - basic_info(): Выводит базовую информацию о данных
    - check_data_quality(): Проверяет качество данных
    - statistical_analysis(): Выполняет статистический анализ
    - generate_visualizations(): Создает визуализации
    - generate_report(): Генерирует полный отчет
    """
    
    def __init__(self, file_path: str):
        """
        Инициализация анализатора
        
        Параметры:
        file_path (str): Путь к Excel файлу
        """
        self.file_path = file_path
        self.data = None
        self.report = {}
        self.analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Создание директории для результатов
        self.output_dir = Path("analysis_results")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Инициализирован анализатор для файла: {file_path}")
    
    def load_data(self) -> bool:
        """
        Загружает данные из Excel файла
        
        Возвращает:
        bool: True если загрузка успешна, False в противном случае
        
        Исключения:
        FileNotFoundError: Если файл не найден
        Exception: При других ошибках чтения файла
        """
        try:
            if not Path(self.file_path).exists():
                raise FileNotFoundError(f"Файл {self.file_path} не найден")
            
            logger.info("Загрузка данных из Excel файла...")
            
            # Попытка загрузить данные с разными вариантами кодировки
            try:
                self.data = pd.read_excel(self.file_path, engine='openpyxl')
            except Exception:
                self.data = pd.read_excel(self.file_path, engine='xlrd')
            
            logger.info(f"Данные успешно загружены. Размер: {self.data.shape}")
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Ошибка: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных: {e}")
            return False
    
    def basic_info(self) -> dict:
        """
        Анализирует базовую информацию о данных
        
        Возвращает:
        dict: Словарь с базовой информацией
        """
        if self.data is None:
            logger.error("Данные не загружены")
            return {}
        
        logger.info("Анализ базовой информации...")
        
        info = {
            'общее_количество_строк': len(self.data),
            'количество_столбцов': len(self.data.columns),
            'названия_столбцов': list(self.data.columns),
            'типы_данных': dict(self.data.dtypes.astype(str)),
            'размер_в_памяти_мб': round(self.data.memory_usage(deep=True).sum() / 1024**2, 2)
        }
        
        self.report['базовая_информация'] = info
        
        print("\n" + "="*60)
        print("БАЗОВАЯ ИНФОРМАЦИЯ О ДАННЫХ")
        print("="*60)
        print(f"📊 Общее количество строк: {info['общее_количество_строк']}")
        print(f"📋 Количество столбцов: {info['количество_столбцов']}")
        print(f"💾 Размер в памяти: {info['размер_в_памяти_мб']} МБ")
        print(f"📑 Столбцы: {', '.join(info['названия_столбцов'])}")
        
        return info
    
    def check_data_quality(self) -> dict:
        """
        Проверяет качество данных
        
        Возвращает:
        dict: Отчет о качестве данных
        """
        if self.data is None:
            logger.error("Данные не загружены")
            return {}
        
        logger.info("Проверка качества данных...")
        
        quality_report = {}
        
        # Анализ пропущенных значений
        missing_data = self.data.isnull().sum()
        missing_percentage = (missing_data / len(self.data)) * 100
        
        quality_report['пропущенные_значения'] = {
            'количество': dict(missing_data[missing_data > 0]),
            'процент': dict(missing_percentage[missing_percentage > 0])
        }
        
        # Анализ дубликатов
        duplicates = self.data.duplicated().sum()
        quality_report['дубликаты'] = {
            'количество': duplicates,
            'процент': round((duplicates / len(self.data)) * 100, 2)
        }
        
        # Анализ уникальных значений по столбцам
        unique_values = {}
        for col in self.data.columns:
            unique_count = self.data[col].nunique()
            unique_values[col] = {
                'уникальных_значений': unique_count,
                'процент_уникальности': round((unique_count / len(self.data)) * 100, 2)
            }
        
        quality_report['уникальность'] = unique_values
        
        self.report['качество_данных'] = quality_report
        
        print("\n" + "="*60)
        print("АНАЛИЗ КАЧЕСТВА ДАННЫХ")
        print("="*60)
        
        if quality_report['пропущенные_значения']['количество']:
            print("❌ Пропущенные значения:")
            for col, count in quality_report['пропущенные_значения']['количество'].items():
                percent = quality_report['пропущенные_значения']['процент'][col]
                print(f"   {col}: {count} ({percent:.1f}%)")
        else:
            print("✅ Пропущенные значения: отсутствуют")
        
        print(f"🔄 Дубликаты: {duplicates} ({quality_report['дубликаты']['процент']}%)")
        
        return quality_report
    
    def statistical_analysis(self) -> dict:
        """
        Выполняет статистический анализ данных
        
        Возвращает:
        dict: Статистический отчет
        """
        if self.data is None:
            logger.error("Данные не загружены")
            return {}
        
        logger.info("Статистический анализ...")
        
        stats = {}
        
        # Анализ числовых столбцов
        numeric_columns = self.data.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            stats['числовые_столбцы'] = {}
            for col in numeric_columns:
                col_stats = {
                    'среднее': round(self.data[col].mean(), 2),
                    'медиана': round(self.data[col].median(), 2),
                    'стандартное_отклонение': round(self.data[col].std(), 2),
                    'минимум': self.data[col].min(),
                    'максимум': self.data[col].max(),
                    'квартили': {
                        'Q1': round(self.data[col].quantile(0.25), 2),
                        'Q3': round(self.data[col].quantile(0.75), 2)
                    }
                }
                stats['числовые_столбцы'][col] = col_stats
        
        # Анализ текстовых столбцов
        text_columns = self.data.select_dtypes(include=['object']).columns
        if len(text_columns) > 0:
            stats['текстовые_столбцы'] = {}
            for col in text_columns:
                col_stats = {
                    'уникальных_значений': self.data[col].nunique(),
                    'самые_частые': dict(self.data[col].value_counts().head(5)),
                    'средняя_длина_текста': round(self.data[col].astype(str).str.len().mean(), 2) if self.data[col].dtype == 'object' else None
                }
                stats['текстовые_столбцы'][col] = col_stats
        
        # Анализ дат
        date_columns = self.data.select_dtypes(include=['datetime64']).columns
        if len(date_columns) > 0:
            stats['столбцы_дат'] = {}
            for col in date_columns:
                col_stats = {
                    'диапазон_дат': {
                        'начало': str(self.data[col].min()),
                        'конец': str(self.data[col].max())
                    },
                    'количество_уникальных_дат': self.data[col].nunique()
                }
                stats['столбцы_дат'][col] = col_stats
        
        self.report['статистика'] = stats
        
        print("\n" + "="*60)
        print("СТАТИСТИЧЕСКИЙ АНАЛИЗ")
        print("="*60)
        
        if 'числовые_столбцы' in stats:
            print("📊 Числовые столбцы:")
            for col, col_stats in stats['числовые_столбцы'].items():
                print(f"   {col}:")
                print(f"     Среднее: {col_stats['среднее']}")
                print(f"     Медиана: {col_stats['медиана']}")
                print(f"     Диапазон: {col_stats['минимум']} - {col_stats['максимум']}")
        
        if 'текстовые_столбцы' in stats:
            print("📝 Текстовые столбцы:")
            for col, col_stats in stats['текстовые_столбцы'].items():
                print(f"   {col}: {col_stats['уникальных_значений']} уникальных значений")
        
        return stats
    
    def generate_visualizations(self):
        """
        Создает визуализации данных
        
        Исключения:
        Exception: При ошибках создания графиков
        """
        if self.data is None:
            logger.error("Данные не загружены")
            return
        
        try:
            logger.info("Создание визуализаций...")
            
            # Настройка стиля графиков
            plt.style.use('default')
            sns.set_palette("husl")
            
            # Подсчет количества графиков
            numeric_cols = self.data.select_dtypes(include=[np.number]).columns
            text_cols = self.data.select_dtypes(include=['object']).columns
            
            total_plots = len(numeric_cols) + min(len(text_cols), 3)
            
            if total_plots == 0:
                print("⚠️ Нет данных для визуализации")
                return
            
            # Создание общей фигуры
            fig_rows = (total_plots + 1) // 2
            fig, axes = plt.subplots(fig_rows, 2, figsize=(15, 5 * fig_rows))
            if fig_rows == 1:
                axes = axes.reshape(1, -1)
            
            plot_idx = 0
            
            # Гистограммы для числовых столбцов
            for col in numeric_cols:
                row, col_idx = plot_idx // 2, plot_idx % 2
                self.data[col].hist(bins=30, ax=axes[row, col_idx], alpha=0.7)
                axes[row, col_idx].set_title(f'Распределение: {col}')
                axes[row, col_idx].set_xlabel(col)
                axes[row, col_idx].set_ylabel('Частота')
                plot_idx += 1
            
            # Диаграммы для категориальных столбцов (топ-10 значений)
            for i, col in enumerate(text_cols[:3]):
                if plot_idx >= total_plots:
                    break
                
                row, col_idx = plot_idx // 2, plot_idx % 2
                top_values = self.data[col].value_counts().head(10)
                
                if len(top_values) > 0:
                    top_values.plot(kind='bar', ax=axes[row, col_idx])
                    axes[row, col_idx].set_title(f'Топ-10 значений: {col}')
                    axes[row, col_idx].set_xlabel(col)
                    axes[row, col_idx].set_ylabel('Количество')
                    axes[row, col_idx].tick_params(axis='x', rotation=45)
                
                plot_idx += 1
            
            # Скрытие пустых субплотов
            for i in range(plot_idx, fig_rows * 2):
                row, col_idx = i // 2, i % 2
                axes[row, col_idx].set_visible(False)
            
            plt.tight_layout()
            
            # Сохранение графиков
            viz_path = self.output_dir / f"visualizations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(viz_path, dpi=300, bbox_inches='tight')
            plt.show()
            
            logger.info(f"Визуализации сохранены в: {viz_path}")
            print(f"📈 Визуализации сохранены в: {viz_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при создании визуализаций: {e}")
            print(f"❌ Ошибка при создании визуализаций: {e}")
    
    def generate_report(self) -> str:
        """
        Генерирует полный отчет анализа
        
        Возвращает:
        str: Путь к файлу отчета
        """
        logger.info("Генерация итогового отчета...")
        
        report_path = self.output_dir / f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("ОТЧЕТ АНАЛИЗА EXCEL ФАЙЛА\n")
            f.write("=" * 60 + "\n")
            f.write(f"Файл: {self.file_path}\n")
            f.write(f"Дата анализа: {self.analysis_date}\n\n")
            
            # Базовая информация
            if 'базовая_информация' in self.report:
                f.write("БАЗОВАЯ ИНФОРМАЦИЯ\n")
                f.write("-" * 30 + "\n")
                info = self.report['базовая_информация']
                f.write(f"Строк: {info['общее_количество_строк']}\n")
                f.write(f"Столбцов: {info['количество_столбцов']}\n")
                f.write(f"Размер: {info['размер_в_памяти_мб']} МБ\n")
                f.write(f"Столбцы: {', '.join(info['названия_столбцов'])}\n\n")
            
            # Качество данных
            if 'качество_данных' in self.report:
                f.write("КАЧЕСТВО ДАННЫХ\n")
                f.write("-" * 30 + "\n")
                quality = self.report['качество_данных']
                
                if quality['пропущенные_значения']['количество']:
                    f.write("Пропущенные значения:\n")
                    for col, count in quality['пропущенные_значения']['количество'].items():
                        percent = quality['пропущенные_значения']['процент'][col]
                        f.write(f"  {col}: {count} ({percent:.1f}%)\n")
                else:
                    f.write("Пропущенные значения: отсутствуют\n")
                
                f.write(f"Дубликаты: {quality['дубликаты']['количество']} ({quality['дубликаты']['процент']}%)\n\n")
            
            # Статистика
            if 'статистика' in self.report:
                f.write("СТАТИСТИЧЕСКИЙ АНАЛИЗ\n")
                f.write("-" * 30 + "\n")
                stats = self.report['статистика']
                
                if 'числовые_столбцы' in stats:
                    f.write("Числовые столбцы:\n")
                    for col, col_stats in stats['числовые_столбцы'].items():
                        f.write(f"  {col}:\n")
                        f.write(f"    Среднее: {col_stats['среднее']}\n")
                        f.write(f"    Медиана: {col_stats['медиана']}\n")
                        f.write(f"    Диапазон: {col_stats['минимум']} - {col_stats['максимум']}\n")
                
                if 'текстовые_столбцы' in stats:
                    f.write("Текстовые столбцы:\n")
                    for col, col_stats in stats['текстовые_столбцы'].items():
                        f.write(f"  {col}: {col_stats['уникальных_значений']} уникальных значений\n")
        
        logger.info(f"Отчет сохранен в: {report_path}")
        print(f"📄 Полный отчет сохранен в: {report_path}")
        
        return str(report_path)
    
    def run_full_analysis(self):
        """
        Запускает полный анализ данных
        
        Выполняет все этапы анализа последовательно
        """
        print("🚀 ЗАПУСК ПОЛНОГО АНАЛИЗА")
        print("=" * 60)
        
        try:
            # Загрузка данных
            if not self.load_data():
                print("❌ Анализ прерван из-за ошибки загрузки данных")
                return
            
            # Базовый анализ
            self.basic_info()
            
            # Проверка качества
            self.check_data_quality()
            
            # Статистический анализ
            self.statistical_analysis()
            
            # Визуализации
            self.generate_visualizations()
            
            # Генерация отчета
            self.generate_report()
            
            print("\n✅ АНАЛИЗ ЗАВЕРШЕН УСПЕШНО!")
            print(f"📁 Результаты сохранены в директории: {self.output_dir}")
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении анализа: {e}")
            print(f"❌ Ошибка при выполнении анализа: {e}")


def main():
    """
    Главная функция для запуска анализа
    
    Запускает интерактивное меню для выбора режима и файла
    """
    # Простой парсер для базовых опций
    parser = argparse.ArgumentParser(
        description="🎯 Интерактивный анализатор Excel файлов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Интерактивное меню:
  python analyze_database.py                           # Запуск интерактивного меню
  
Прямой анализ файла:
  python analyze_database.py file.xlsx                 # Прямой полный анализ файла
  python analyze_database.py --output-dir results      # Изменить папку результатов
        """
    )
    
    parser.add_argument(
        'file', 
        nargs='?', 
        default=None,
        help='Путь к Excel файлу для прямого анализа (если не указан - интерактивное меню)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        default="analysis_results",
        help='Директория для сохранения результатов (по умолчанию: analysis_results)'
    )
    
    # Парсинг аргументов
    args = parser.parse_args()
    
    # Создание директории для логов если её нет
    Path("logs").mkdir(exist_ok=True)
    
    print("🎯 ИНТЕРАКТИВНЫЙ АНАЛИЗАТОР EXCEL ФАЙЛОВ")
    print("=" * 60)
    
    # Если файл указан напрямую - выполнить полный анализ
    if args.file:
        if not Path(args.file).exists():
            print(f"❌ Файл '{args.file}' не найден!")
            print(f"💡 Запустите без параметров для интерактивного выбора")
            
            # Показать доступные файлы
            excel_files = find_excel_files()
            if excel_files:
                print(f"\n📋 Доступные Excel файлы:")
                for i, file in enumerate(excel_files, 1):
                    print(f"  {i}. {file}")
            
            sys.exit(1)
        
        # Прямой полный анализ
        print(f"📄 Выполняется полный анализ файла: {args.file}")
        print("=" * 60)
        
        analyzer = DatabaseAnalyzer(args.file)
        if args.output_dir != "analysis_results":
            analyzer.output_dir = Path(args.output_dir)
            analyzer.output_dir.mkdir(exist_ok=True)
        
        analyzer.run_full_analysis()
        sys.exit(0)
    
    # Интерактивный режим
    while True:
        # Выбор режима работы
        selected_mode = interactive_mode_selection()
        if selected_mode is None:
            sys.exit(0)
        
        # Выбор файла
        file_path = interactive_file_selection()
        if file_path is None:
            print("\n🔄 Возврат к выбору режима...")
            continue
        
        # Создание анализатора
        analyzer = DatabaseAnalyzer(file_path)
        if args.output_dir != "analysis_results":
            analyzer.output_dir = Path(args.output_dir)
            analyzer.output_dir.mkdir(exist_ok=True)
        
        try:
            # Выполнение выбранного режима
            if selected_mode['mode'] == 'preview':
                quick_preview_mode(file_path)
                
            elif selected_mode['mode'] == 'full':
                print("\n🚀 ЗАПУСК ПОЛНОГО АНАЛИЗА")
                print("=" * 60)
                analyzer.run_full_analysis()
                
            elif selected_mode['mode'] == 'quick':
                print("\n🚀 ЗАПУСК БЫСТРОГО АНАЛИЗА")
                print("=" * 60)
                if analyzer.load_data():
                    analyzer.basic_info()
                    analyzer.check_data_quality()
                    analyzer.statistical_analysis()
                    analyzer.generate_report()
                    print("\n✅ БЫСТРЫЙ АНАЛИЗ ЗАВЕРШЕН!")
                    print(f"📁 Результаты: {analyzer.output_dir}")
                else:
                    print("❌ Ошибка загрузки данных")
                    
            elif selected_mode['mode'] == 'no_viz':
                print("\n🚀 ЗАПУСК АНАЛИЗА БЕЗ ВИЗУАЛИЗАЦИЙ")
                print("=" * 60)
                if analyzer.load_data():
                    analyzer.basic_info()
                    analyzer.check_data_quality()
                    analyzer.statistical_analysis()
                    analyzer.generate_report()
                    print("\n✅ АНАЛИЗ ЗАВЕРШЕН!")
                    print(f"📁 Результаты: {analyzer.output_dir}")
                else:
                    print("❌ Ошибка загрузки данных")
        
        except Exception as e:
            logger.error(f"Ошибка при выполнении анализа: {e}")
            print(f"❌ Ошибка: {e}")
        
        # Предложение продолжить работу
        print("\n" + "=" * 60)
        while True:
            try:
                continue_choice = input("🔄 Выполнить еще один анализ? (y/n): ").strip().lower()
                if continue_choice in ['y', 'yes', 'д', 'да']:
                    break
                elif continue_choice in ['n', 'no', 'н', 'нет']:
                    print("👋 До свидания!")
                    sys.exit(0)
                else:
                    print("❌ Введите 'y' для продолжения или 'n' для выхода")
            except KeyboardInterrupt:
                print("\n👋 До свидания!")
                sys.exit(0)


if __name__ == "__main__":
    main() 