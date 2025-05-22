
# Технический план реализации векторного поиска с FAISS и OpenAI Embeddings

## Структура решения

Мы создадим новый модуль `utils/vector_search.py` с реализацией векторного поиска с использованием FAISS и OpenAI Embeddings. Решение будет состоять из следующих компонентов:

### 1. Зависимости

Добавим необходимые библиотеки в requirements.txt:
- faiss-cpu (или faiss-gpu, если планируется использование GPU)
- numpy
- openai (уже есть)

### 2. Модуль vector_search.py

Модуль будет содержать следующие основные компоненты:

#### 2.1 Класс FAISSVectorStore

Класс для управления векторным хранилищем FAISS:

```python
class FAISSVectorStore:
    def __init__(self, embedding_dimension=1536, index_file_path="data/faiss_index.bin"):
        # Инициализация хранилища FAISS с указанной размерностью эмбеддингов
        # Загрузка существующего индекса или создание нового

    def build_index(self, conn, embedding_func, batch_size=100):
        # Построение индекса из базы данных
        # Использование embedding_func для создания эмбеддингов

    def save_index(self):
        # Сохранение индекса в файл

    def load_index(self):
        # Загрузка индекса из файла

    def search(self, query_vector, top_k=5):
        # Поиск ближайших соседей для вектора запроса
```

#### 2.2 Функции для работы с OpenAI Embeddings

```python
def get_embedding_openai(text, model="text-embedding-3-small"):
    # Получение эмбеддинга текста через OpenAI API

def batch_get_embeddings(texts, model="text-embedding-3-small", batch_size=100):
    # Получение эмбеддингов для группы текстов с учетом ограничений API
```

#### 2.3 Функции для управления базой данных

```python
def update_vector_map(conn, chunk_id, faiss_id):
    # Обновление таблицы vector_map связями между chunk_id и faiss_id

def get_chunks_by_ids(conn, chunk_ids):
    # Получение текстовых чанков по их идентификаторам
```

#### 2.4 Функции для интеграции с GPT

```python
def search_relevant_chunks(query, vector_store, conn, top_k=5):
    # Поиск релевантных чанков для запроса

def get_context_for_query(query, vector_store, conn, top_k=5, max_tokens=2000):
    # Подготовка контекста для запроса GPT на основе найденных чанков

def augment_prompt_with_context(prompt, context):
    # Дополнение промпта контекстом из базы знаний
```

### 3. Скрипт для индексации данных

Создадим скрипт `build_faiss_index.py`, который будет отвечать за индексацию данных.

### 4. Интеграция с существующим кодом

Модифицируем `bot.py` для использования векторного поиска в функции `get_gpt_response`.

## Общий подход к реализации

1. Создать и сохранить индекс FAISS для всех чанков из БД
2. При получении запроса:
   - Найти релевантные чанки с помощью векторного поиска
   - Дополнить промпт контекстом из найденных чанков
   - Отправить дополненный промпт в OpenAI API

## План тестирования

1. Проверить создание и сохранение индекса FAISS
2. Проверить поиск релевантных чанков
3. Проверить интеграцию с GPT и качество ответов

## IMPLEMENTATION CHECKLIST:

1. Добавить необходимые зависимости в requirements.txt (faiss-cpu, numpy)
2. Создать файл utils/vector_search.py
3. Реализовать функцию get_embedding_openai для получения эмбеддингов через OpenAI API
4. Реализовать функцию batch_get_embeddings для батчевой обработки текстов
5. Реализовать класс FAISSVectorStore для управления векторным хранилищем
6. Реализовать метод FAISSVectorStore.init для инициализации хранилища
7. Реализовать метод FAISSVectorStore.build_index для построения индекса
8. Реализовать метод FAISSVectorStore.save_index для сохранения индекса
9. Реализовать метод FAISSVectorStore.load_index для загрузки индекса
10. Реализовать метод FAISSVectorStore.search для поиска ближайших векторов
11. Реализовать функцию update_vector_map для обновления таблицы связей
12. Реализовать функцию get_chunks_by_ids для получения чанков по идентификаторам
13. Реализовать функцию search_relevant_chunks для поиска релевантных чанков
14. Реализовать функцию get_context_for_query для подготовки контекста
15. Реализовать функцию augment_prompt_with_context для дополнения промпта
16. Создать скрипт build_faiss_index.py для построения индекса
17. Модифицировать функцию get_gpt_response в bot.py для использования векторного поиска
18. Добавить инициализацию векторного хранилища в функцию main в bot.py
19. Провести тестирование построения индекса
20. Провести тестирование поиска релевантных чанков
21. Провести тестирование интеграции с GPT и качества ответов
