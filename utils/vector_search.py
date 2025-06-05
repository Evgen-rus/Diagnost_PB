"""
Модуль для векторного поиска с использованием FAISS и OpenAI Embeddings.

Предоставляет классы и функции для создания, управления и использования
векторного индекса FAISS для поиска релевантных документов.
"""
import os
import numpy as np
import faiss
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI

# Настраиваем логгер для модуля векторного поиска
vector_logger = logging.getLogger('vector_search')

# Путь к базе данных и файлу индекса
from utils.database import DB_PATH
INDEX_FILE_PATH = os.path.join(os.getcwd(), 'data', 'faiss_index.bin')
VECTOR_MAP_FILE_PATH = os.path.join(os.getcwd(), 'data', 'vector_map.json')

def get_embedding_openai(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Получение эмбеддинга текста через OpenAI API.
    
    Args:
        text: Текст для получения эмбеддинга
        model: Модель OpenAI для эмбеддингов (по умолчанию "text-embedding-3-small")
        
    Returns:
        Список с векторным представлением текста
    """
    try:
        # Инициализируем клиент OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Получаем эмбеддинг
        response = client.embeddings.create(
            input=text,
            model=model
        )
        
        # Извлекаем вектор
        embedding = response.data[0].embedding
        
        vector_logger.info(f"Получен эмбеддинг размерностью {len(embedding)}")
        return embedding
        
    except Exception as e:
        vector_logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        raise

def batch_get_embeddings(texts: List[str], model: str = "text-embedding-3-small", batch_size: int = 100) -> List[List[float]]:
    """
    Получение эмбеддингов для группы текстов с учетом ограничений API.
    
    Args:
        texts: Список текстов для получения эмбеддингов
        model: Модель OpenAI для эмбеддингов (по умолчанию "text-embedding-3-small")
        batch_size: Размер пакета для запроса к API (по умолчанию 100)
        
    Returns:
        Список векторных представлений текстов
    """
    all_embeddings = []
    
    # Обрабатываем тексты пакетами для предотвращения превышения лимитов API
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        
        try:
            # Инициализируем клиент OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Получаем эмбеддинги для пакета текстов
            response = client.embeddings.create(
                input=batch,
                model=model
            )
            
            # Извлекаем векторы и добавляем их в общий список
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            vector_logger.info(f"Получены эмбеддинги для пакета {i}-{i+len(batch)} из {len(texts)}")
            
        except Exception as e:
            vector_logger.error(f"Ошибка при получении пакета эмбеддингов: {str(e)}")
            raise
    
    return all_embeddings

class FAISSVectorStore:
    """
    Класс для управления векторным хранилищем FAISS.
    
    Обеспечивает создание, сохранение, загрузку и поиск в индексе FAISS.
    """
    
    def __init__(self, embedding_dimension: int = 1536, index_file_path: str = INDEX_FILE_PATH):
        """
        Инициализация хранилища FAISS.
        
        Args:
            embedding_dimension: Размерность эмбеддингов (по умолчанию 1536 для OpenAI)
            index_file_path: Путь для сохранения индекса FAISS
        """
        self.embedding_dimension = embedding_dimension
        self.index_file_path = index_file_path
        self.vector_map = {}  # Соответствие между ID в FAISS и ID чанков в базе данных
        
        # Создаем директорию для хранения индекса, если она не существует
        os.makedirs(os.path.dirname(self.index_file_path), exist_ok=True)
        
        # Пытаемся загрузить существующий индекс или создаем новый
        if os.path.exists(self.index_file_path):
            self.load_index()
        else:
            # Создаем индекс L2 (евклидово расстояние)
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
            vector_logger.info(f"Создан новый индекс FAISS с размерностью {self.embedding_dimension}")
            
        # Загружаем маппинг векторов, если файл существует
        if os.path.exists(VECTOR_MAP_FILE_PATH):
            with open(VECTOR_MAP_FILE_PATH, 'r', encoding='utf-8') as f:
                self.vector_map = json.load(f)
            vector_logger.info(f"Загружен маппинг векторов с {len(self.vector_map)} записями")
    
    def build_index(self, conn: sqlite3.Connection, embedding_func, batch_size: int = 100):
        """
        Построение индекса из базы данных.
        
        Args:
            conn: Соединение с базой данных SQLite
            embedding_func: Функция для создания эмбеддингов
            batch_size: Размер пакета для обработки (по умолчанию 100)
        """
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы chunks
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='chunks'
        """)
        
        if not cursor.fetchone():
            vector_logger.error("Таблица 'chunks' не найдена в базе данных")
            raise ValueError("Таблица 'chunks' не найдена в базе данных")
        
        # Получаем все чанки из базы данных
        # Адаптируем запрос к существующей структуре таблицы
        cursor.execute("SELECT chunk_id, text FROM chunks")
        chunks = cursor.fetchall()
        
        if not chunks:
            vector_logger.warning("В базе данных не найдено чанков для индексации")
            return
        
        vector_logger.info(f"Найдено {len(chunks)} чанков для индексации")
        
        # Проверяем существование таблицы vector_map
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='vector_map'
        """)
        if not cursor.fetchone():
            # Создаем таблицу vector_map
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vector_map (
                chunk_id TEXT PRIMARY KEY,
                faiss_id INTEGER NOT NULL
            )
            """)
            vector_logger.info("Создана таблица vector_map")
        else:
            # Проверяем структуру таблицы vector_map
            cursor.execute("PRAGMA table_info(vector_map)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Если в таблице нет столбца faiss_id, добавляем его
            if 'faiss_id' not in column_names:
                cursor.execute("ALTER TABLE vector_map ADD COLUMN faiss_id INTEGER")
                vector_logger.info("Добавлен столбец faiss_id в таблицу vector_map")
        
        # Сбрасываем индекс и маппинг, если они уже существуют
        self.index = faiss.IndexFlatL2(self.embedding_dimension)
        self.vector_map = {}
        
        # Обрабатываем чанки пакетами
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i+batch_size]
            
            # Извлекаем ID и тексты чанков
            chunk_ids = [chunk[0] for chunk in batch_chunks]
            chunk_texts = [chunk[1] for chunk in batch_chunks]
            
            # Получаем эмбеддинги для текстов
            embeddings = embedding_func(chunk_texts)
            
            # Преобразуем список эмбеддингов в массив numpy нужной формы
            embeddings_array = np.array(embeddings).astype('float32')
            
            # Добавляем векторы в индекс
            faiss_start_id = self.index.ntotal
            self.index.add(embeddings_array)
            
            # Обновляем маппинг между FAISS ID и chunk ID
            for j, chunk_id in enumerate(chunk_ids):
                faiss_id = faiss_start_id + j
                self.vector_map[str(faiss_id)] = chunk_id
                
                # Добавляем запись в таблицу vector_map
                cursor.execute(
                    "INSERT OR REPLACE INTO vector_map (chunk_id, faiss_id) VALUES (?, ?)",
                    (chunk_id, faiss_id)
                )
            
            conn.commit()
            vector_logger.info(f"Обработано {i+len(batch_chunks)} из {len(chunks)} чанков")
        
        # Сохраняем индекс и маппинг
        self.save_index()
        
        vector_logger.info(f"Построение индекса завершено. Всего векторов: {self.index.ntotal}")
    
    def save_index(self):
        """
        Сохранение индекса в файл.
        """
        try:
            # Сохраняем индекс FAISS
            faiss.write_index(self.index, self.index_file_path)
            
            # Сохраняем маппинг
            with open(VECTOR_MAP_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.vector_map, f, ensure_ascii=False, indent=2)
            
            vector_logger.info(f"Индекс сохранен в {self.index_file_path}")
            vector_logger.info(f"Маппинг сохранен в {VECTOR_MAP_FILE_PATH}")
            
        except Exception as e:
            vector_logger.error(f"Ошибка при сохранении индекса: {str(e)}")
            raise
    
    def load_index(self):
        """
        Загрузка индекса из файла.
        """
        try:
            # Загружаем индекс FAISS
            self.index = faiss.read_index(self.index_file_path)
            vector_logger.info(f"Индекс загружен из {self.index_file_path}. Всего векторов: {self.index.ntotal}")
            
        except Exception as e:
            vector_logger.error(f"Ошибка при загрузке индекса: {str(e)}")
            # Создаем новый индекс в случае ошибки
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
            vector_logger.info(f"Создан новый индекс с размерностью {self.embedding_dimension}")
    
    def search(self, query_vector: List[float], top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Поиск ближайших соседей для вектора запроса.
        
        Args:
            query_vector: Вектор запроса
            top_k: Количество ближайших соседей для поиска (по умолчанию 5)
            
        Returns:
            Кортеж (distances, indices), где:
            - distances: массив расстояний до ближайших соседей
            - indices: массив индексов ближайших соседей в индексе FAISS
        """
        # Преобразуем вектор запроса в массив numpy нужной формы
        query_vector_array = np.array([query_vector]).astype('float32')
        
        # Выполняем поиск в индексе
        distances, indices = self.index.search(query_vector_array, top_k)
        
        vector_logger.info(f"Найдено {len(indices[0])} ближайших соседей для запроса")
        
        return distances, indices

def update_vector_map(conn: sqlite3.Connection, chunk_id: int, faiss_id: int):
    """
    Обновление таблицы vector_map связями между chunk_id и faiss_id.
    
    Args:
        conn: Соединение с базой данных SQLite
        chunk_id: ID чанка в базе данных
        faiss_id: ID вектора в индексе FAISS
    """
    try:
        cursor = conn.cursor()
        
        # Создаем таблицу vector_map, если она не существует
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vector_map (
            chunk_id INTEGER PRIMARY KEY,
            faiss_id INTEGER NOT NULL
        )
        """)
        
        # Вставляем или заменяем запись
        cursor.execute(
            "INSERT OR REPLACE INTO vector_map (chunk_id, faiss_id) VALUES (?, ?)",
            (chunk_id, faiss_id)
        )
        
        conn.commit()
        vector_logger.info(f"Обновлен маппинг: chunk_id={chunk_id}, faiss_id={faiss_id}")
        
    except sqlite3.Error as e:
        vector_logger.error(f"Ошибка при обновлении маппинга: {str(e)}")
        raise

def get_chunks_by_ids(conn: sqlite3.Connection, chunk_ids: List[str]) -> List[Dict]:
    """
    Получение текстовых чанков по их идентификаторам.
    
    Args:
        conn: Соединение с базой данных SQLite
        chunk_ids: Список ID чанков для получения
        
    Returns:
        Список словарей с информацией о чанках
    """
    chunks = []
    
    try:
        cursor = conn.cursor()
        
        # Преобразуем список ID в строку для SQL запроса
        ids_str = ','.join('?' for _ in chunk_ids)
        
        # Выполняем запрос с учетом структуры таблицы chunks
        cursor.execute(
            f"SELECT * FROM chunks WHERE chunk_id IN ({ids_str})",
            chunk_ids
        )
        
        # Получаем имена столбцов
        column_names = [description[0] for description in cursor.description]
        
        # Преобразуем результаты в список словарей
        for row in cursor.fetchall():
            chunk = {}
            for i, value in enumerate(row):
                chunk[column_names[i]] = value
                
            # Добавляем поля, ожидаемые в коде, для совместимости
            if 'chunk_id' in chunk:
                chunk['id'] = chunk['chunk_id']
            if 'text' in chunk:
                chunk['content'] = chunk['text']
            if 'doc_id' in chunk:
                chunk['document_title'] = chunk['doc_id']
                
            chunks.append(chunk)
        
        vector_logger.info(f"Получено {len(chunks)} чанков из {len(chunk_ids)} запрошенных")
        
    except sqlite3.Error as e:
        vector_logger.error(f"Ошибка при получении чанков: {str(e)}")
        raise
    
    return chunks

def search_relevant_chunks(query: str, vector_store: FAISSVectorStore, conn: sqlite3.Connection, top_k: int = 5) -> List[Dict]:
    """
    Поиск релевантных чанков для запроса.
    
    Args:
        query: Текстовый запрос
        vector_store: Экземпляр класса FAISSVectorStore
        conn: Соединение с базой данных SQLite
        top_k: Количество релевантных чанков для поиска (по умолчанию 5)
        
    Returns:
        Список словарей с информацией о релевантных чанках
    """
    # Получаем эмбеддинг запроса
    query_embedding = get_embedding_openai(query)
    
    # Ищем ближайшие векторы
    distances, indices = vector_store.search(query_embedding, top_k)
    
    # Извлекаем ID чанков из индексов FAISS
    faiss_ids = indices[0].tolist()
    chunk_ids = []
    
    for faiss_id in faiss_ids:
        chunk_id = vector_store.vector_map.get(str(faiss_id))
        if chunk_id:
            chunk_ids.append(chunk_id)
    
    # Получаем чанки из базы данных
    chunks = get_chunks_by_ids(conn, chunk_ids)
    
    # Добавляем информацию о релевантности
    for i, chunk in enumerate(chunks):
        if i < len(distances[0]):
            chunk['distance'] = float(distances[0][i])
    
    return chunks

def get_context_for_query(query: str, vector_store: FAISSVectorStore, conn: sqlite3.Connection, top_k: int = 5, max_tokens: int = 2000) -> str:
    """
    Подготовка контекста для запроса GPT на основе найденных чанков.
    
    Args:
        query: Текстовый запрос
        vector_store: Экземпляр класса FAISSVectorStore
        conn: Соединение с базой данных SQLite
        top_k: Количество релевантных чанков для поиска (по умолчанию 5)
        max_tokens: Максимальное количество токенов для контекста (по умолчанию 2000)
        
    Returns:
        Строка с контекстом, сформированная из найденных чанков
    """
    # Находим релевантные чанки
    chunks = search_relevant_chunks(query, vector_store, conn, top_k)
    
    # Формируем контекст
    context_parts = []
    
    for chunk in chunks:
        # Добавляем информацию о документе
        document_info = f"Документ: {chunk.get('doc_id', chunk.get('document_title', 'Неизвестный документ'))}"
        
        # Добавляем содержимое чанка
        content = chunk.get('text', chunk.get('content', ''))
        
        # Формируем полное описание чанка
        chunk_text = f"{document_info}\n\n{content}\n\n"
        context_parts.append(chunk_text)
    
    # Объединяем части контекста
    context = "--- КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ---\n\n" + "\n".join(context_parts)
    
    # Ограничиваем контекст по длине (примерно)
    if len(context) > max_tokens * 4:  # Примерное соотношение токенов к символам
        context = context[:max_tokens * 4] + "...\n\n--- КОНЕЦ КОНТЕКСТА ---"
    else:
        context += "\n\n--- КОНЕЦ КОНТЕКСТА ---"
    
    return context

def augment_prompt_with_context(prompt: str, context: str) -> str:
    """
    Дополнение промпта контекстом из базы знаний.
    
    Args:
        prompt: Исходный промпт
        context: Контекст из базы знаний
        
    Returns:
        Дополненный промпт
    """
    # Формируем инструкцию для использования контекста
    instruction = """
    Выше представлен контекст из базы знаний, который может быть полезен для ответа на вопрос.
    Если информация в контексте релевантна для ответа, используйте ее.
    Если в контексте нет релевантной информации, отвечайте на основе своих знаний.
    
    КРИТИЧЕСКИ ВАЖНО ДЛЯ НОРМАТИВНЫХ ДОКУМЕНТОВ:
    - ОБЯЗАТЕЛЬНО включи секцию "Источники и нормативные документы" в конце ответа
    - Используй ТОЛЬКО точные названия документов из контекста или проверенные источники
    - НЕ указывай устаревшие документы (например, ГОСТ 14782-86 утратил силу в РФ)
    - При упоминании ГОСТов проверяй их актуальность для РФ
    - Если сомневаешься в названии или актуальности документа - лучше не указывай его
    
    Важно: не упоминайте в ответе, что вы используете контекст, если пользователь явно не спрашивает об источниках.
    """
    
    # Объединяем контекст, инструкцию и исходный промпт
    augmented_prompt = context + "\n\n" + instruction + "\n\n" + prompt
    
    return augmented_prompt 