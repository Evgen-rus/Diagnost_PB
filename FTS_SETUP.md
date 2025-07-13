# 📝 Настройка полнотекстового поиска (FTS5)

## 📋 Обзор

Этот гайд поможет настроить полнотекстовый поиск FTS5 для работы параллельно с векторным поиском в Telegram боте.

## 🔍 Что такое FTS5?

FTS5 (Full-Text Search) - это встроенная система полнотекстового поиска SQLite, которая:
- ✅ Находит точные совпадения слов и фраз
- ✅ Поддерживает русский язык через tokenizer unicode61
- ✅ Работает быстро (< 5 мс на ~100,000 документов)
- ✅ Не требует внешних зависимостей

## 🚀 Быстрая настройка

### Шаг 1: Создание FTS индекса

```bash
# Создаем FTS индекс из существующих данных
python build_fts_index.py
```

**Что происходит:**
- ✅ Создается FTS5 виртуальная таблица `chunks_fts`
- ✅ Индексируются все тексты из таблицы `chunks`
- ✅ Настраивается токенизация для русского языка
- ✅ Оптимизируется индекс для быстрого поиска

### Шаг 2: Тестирование FTS поиска

```bash
# Тестируем FTS поиск
python test_fts_search.py
```

### Шаг 3: Тестирование гибридного поиска

```bash
# Тестируем гибридный поиск (FTS + векторный)
python test_hybrid_search.py
```

## 🔧 Техническая архитектура

### Структура FTS таблицы

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_text,                              -- Поле для поиска
    content='chunks',                        -- Источник данных
    content_rowid='id',                      -- Связь с основной таблицей
    tokenize="unicode61 remove_diacritics 2" -- Токенизация для русского языка
);
```

### Как работает гибридный поиск

```mermaid
graph LR
    A[Запрос пользователя] --> B[Векторный поиск]
    A --> C[FTS поиск]
    B --> D[Топ-3 результата]
    C --> E[Топ-3 результата]
    D --> F[Объединение без дублей]
    E --> F
    F --> G[До 6 уникальных результатов]
    G --> H[Контекст для GPT]
```

## 📊 Сравнение типов поиска

| Тип поиска | Лучше для | Пример запроса |
|------------|-----------|----------------|
| **Векторный** | Семантический поиск | "проблемы с сердцем" |
| **FTS** | Точные термины | "гипертония", "ГОСТ-123" |
| **Гибридный** | Комбинированный | "диагностика гипертонии" |

## 🎯 Настройка параметров

### В файле `config.py`:

```python
# FTS search configuration
FTS_ENABLED = True                    # Включение/выключение FTS поиска
FTS_DEFAULT_LIMIT = 3                # Количество результатов FTS поиска
HYBRID_SEARCH_ENABLED = True         # Включение гибридного поиска
```

### Возможные значения:

- `FTS_ENABLED = False` - отключить FTS, использовать только векторный поиск
- `FTS_DEFAULT_LIMIT = 5` - получать больше результатов от FTS
- `HYBRID_SEARCH_ENABLED = False` - отключить гибридный поиск

## 📈 Мониторинг и отладка

### Проверка статуса FTS индекса:

```python
from utils.fts_search import get_fts_statistics

stats = get_fts_statistics()
print(f"FTS таблица существует: {stats['fts_table_exists']}")
print(f"Количество записей: {stats['total_records']}")
```

### Логирование:

FTS поиск логируется в модуле `fts_search`:
```python
fts_logger.info(f"FTS поиск по запросу '{query}' нашел {len(results)} результатов")
```

Гибридный поиск логируется в модуле `hybrid_search`:
```python
hybrid_logger.info(f"Объединено {len(merged_results)} уникальных результатов")
```

## 🔍 Синтаксис FTS запросов
"дефекты сварных швов",
        "ультразвуковой контроль",
        "рентгенографический контроль"

### Основные возможности:

```python
# Простой поиск
fts_search("дефекты сварных швов")

# Поиск фразы
fts_search('"ультразвуковой контроль"')

# Поиск с префиксом
fts_search("диагност*")

# Поиск нескольких слов
fts_search("рентгенографический контроль")

```

## 🚨 Устранение неполадок

### Проблема: FTS таблица не найдена

**Решение:**
```bash
python build_fts_index.py
```

### Проблема: Пустые результаты FTS поиска

**Диагностика:**
```python
# Проверка количества записей
import sqlite3
conn = sqlite3.connect('knowledge_base_v2.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM chunks_fts")
print(f"Записей в FTS: {cursor.fetchone()[0]}")
```

**Решение:**
```bash
# Пересоздание индекса
python build_fts_index.py
```

### Проблема: Медленный поиск

**Оптимизация:**
```sql
-- Запустить оптимизацию индекса
INSERT INTO chunks_fts(chunks_fts) VALUES('optimize');
```

## 🎛️ Дополнительные возможности

### Морфологический поиск

Для поиска по разным формам слова (лечение/лечить/лечил):

1. Установите pymorphy2:
```bash
pip install pymorphy2
```

2. Создайте поле со стеммингом:
```sql
ALTER TABLE chunks ADD COLUMN stemmed_text TEXT;
```

3. Заполните поле стеммами и создайте FTS индекс по нему.

### Поиск по категориям документов

```python
# Поиск только в клинических рекомендациях
def fts_search_by_category(query, doc_type):
    sql = """
    SELECT chunks.* FROM chunks_fts
    JOIN chunks ON chunks.id = chunks_fts.rowid
    WHERE chunks_fts MATCH ? AND chunks.doc_type_short = ?
    """
    # ... выполнение запроса
```

## 📚 Полезные ресурсы

- [SQLite FTS5 Documentation](https://sqlite.org/fts5.html)
- [FTS5 Query Syntax](https://sqlite.org/fts5.html#fts5_query_syntax)
- [Unicode61 Tokenizer](https://sqlite.org/fts5.html#unicode61_tokenizer)

## ✅ Чек-лист готовности

После настройки проверьте:

- [ ] `python build_fts_index.py` выполнился без ошибок
- [ ] `python test_fts_search.py` показывает результаты поиска
- [ ] `python test_hybrid_search.py` показывает объединенные результаты
- [ ] В логах бота есть сообщения о гибридном поиске
- [ ] Бот отвечает с использованием FTS контекста

🎉 **Готово!** Ваш бот теперь использует гибридный поиск! 