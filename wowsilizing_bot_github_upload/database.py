"""База данных для хранения истории, шаблонов, кеша и статистики."""
import aiosqlite
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import config


class Database:
    """Класс для работы с базой данных SQLite."""
    
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц."""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_premium INTEGER DEFAULT 0,
                    start_padding INTEGER DEFAULT 2,
                    end_padding INTEGER DEFAULT 2,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Миграция: добавляем колонки padding, если их нет
            try:
                # Проверяем, есть ли колонка start_padding
                cursor = await db.execute("PRAGMA table_info(users)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'start_padding' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN start_padding INTEGER DEFAULT 2")
                    print("✅ Added start_padding column to users table")
                
                if 'end_padding' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN end_padding INTEGER DEFAULT 2")
                    print("✅ Added end_padding column to users table")
            except Exception as e:
                print(f"Migration check: {e}")
            
            # Таблица истории операций
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    video_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    duration REAL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица шаблонов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    settings_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, name),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Таблица кеша
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    hash TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    access_count INTEGER DEFAULT 0
                )
            """)
            
            # Таблица статистики использования (для премиум)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS usage_stats (
                    user_id INTEGER PRIMARY KEY,
                    api_calls INTEGER DEFAULT 0,
                    minutes_processed REAL DEFAULT 0,
                    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Создание индексов
            await db.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at)")
            
            await db.commit()
    
    async def add_user(self, user_id: int, username: str, is_premium: bool = False):
        """Добавление или обновление пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, is_premium, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    is_premium = excluded.is_premium,
                    last_active = CURRENT_TIMESTAMP
            """, (user_id, username, int(is_premium)))
            await db.commit()
    
    async def is_premium(self, username: str) -> bool:
        """Проверка премиум статуса пользователя."""
        username_clean = username.lower().replace("@", "")
        return username_clean == config.PREMIUM_USERNAME
    
    async def get_padding_settings(self, user_id: int) -> Dict[str, int]:
        """Получение настроек запаса времени для нарезки."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT start_padding, end_padding
                FROM users
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"start_padding": row[0], "end_padding": row[1]}
                # Значения по умолчанию
                return {"start_padding": 2, "end_padding": 2}
    
    async def set_padding_settings(self, user_id: int, start_padding: int, end_padding: int):
        """Установка настроек запаса времени для нарезки."""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли пользователь
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            
            if row:
                # Обновляем существующего пользователя
                await db.execute("""
                    UPDATE users
                    SET start_padding = ?, end_padding = ?
                    WHERE user_id = ?
                """, (start_padding, end_padding, user_id))
            else:
                # Создаем нового пользователя с указанными настройками
                await db.execute("""
                    INSERT INTO users (user_id, username, start_padding, end_padding)
                    VALUES (?, '', ?, ?)
                """, (user_id, start_padding, end_padding))
            
            await db.commit()
    
    async def add_history(self, user_id: int, video_name: str, operation: str, 
                         file_size: int = 0, duration: float = 0):
        """Добавление записи в историю."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO history (user_id, video_name, operation, file_size, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, video_name, operation, file_size, duration))
            await db.commit()
    
    async def get_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории операций пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT video_name, operation, timestamp, duration
                FROM history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def save_template(self, user_id: int, name: str, settings: Dict[str, Any]):
        """Сохранение шаблона настроек."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO templates (user_id, name, settings_json)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    created_at = CURRENT_TIMESTAMP
            """, (user_id, name, json.dumps(settings, ensure_ascii=False)))
            await db.commit()
    
    async def get_template(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        """Получение шаблона по имени."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT settings_json FROM templates
                WHERE user_id = ? AND name = ?
            """, (user_id, name)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
    
    async def get_user_templates(self, user_id: int) -> List[str]:
        """Получение списка шаблонов пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT name FROM templates
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def delete_template(self, user_id: int, name: str):
        """Удаление шаблона."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM templates
                WHERE user_id = ? AND name = ?
            """, (user_id, name))
            await db.commit()
    
    async def get_cache(self, cache_hash: str) -> Optional[str]:
        """Получение результата из кеша."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT file_path FROM cache
                WHERE hash = ? AND created_at > datetime('now', '-' || ? || ' days')
            """, (cache_hash, config.CACHE_EXPIRY_DAYS)) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Увеличиваем счетчик обращений
                    await db.execute("""
                        UPDATE cache SET access_count = access_count + 1
                        WHERE hash = ?
                    """, (cache_hash,))
                    await db.commit()
                    return row[0]
                return None
    
    async def save_cache(self, cache_hash: str, file_path: str, operation: str, file_size: int):
        """Сохранение результата в кеш."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO cache (hash, file_path, operation, file_size)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hash) DO UPDATE SET
                    access_count = access_count + 1
            """, (cache_hash, file_path, operation, file_size))
            await db.commit()
    
    async def clean_old_cache(self):
        """Очистка старого кеша."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM cache
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (config.CACHE_EXPIRY_DAYS,))
            await db.commit()
    
    async def add_api_usage(self, user_id: int, api_calls: int = 1, minutes: float = 0):
        """Добавление статистики использования API."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO usage_stats (user_id, api_calls, minutes_processed)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    api_calls = api_calls + excluded.api_calls,
                    minutes_processed = minutes_processed + excluded.minutes_processed
            """, (user_id, api_calls, minutes))
            await db.commit()
    
    async def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики использования."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT api_calls, minutes_processed, last_reset
                FROM usage_stats
                WHERE user_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return {"api_calls": 0, "minutes_processed": 0, "last_reset": None}
    
    @staticmethod
    def calculate_hash(file_path: str, operation: str, params: Dict[str, Any] = None) -> str:
        """Вычисление хеша для кеширования."""
        hash_obj = hashlib.sha256()
        
        # Добавляем хеш файла
        try:
            with open(file_path, 'rb') as f:
                # Читаем первые 1MB для быстрого хеширования
                hash_obj.update(f.read(1024 * 1024))
        except:
            pass
        
        # Добавляем операцию и параметры
        hash_obj.update(operation.encode())
        if params:
            hash_obj.update(json.dumps(params, sort_keys=True).encode())
        
        return hash_obj.hexdigest()


# Глобальный экземпляр базы данных
db = Database()
