"""
Database Manager Module
Provides database operations for the audiobook player application.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable


def init_database(db_file: Path, log_func: Callable[[str], None] = print):
    """
    Инициализация базы данных - создание таблиц и индексов.
    Вызывается из scanner.py при сканировании библиотеки.
    
    Args:
        db_file: Путь к файлу базы данных
        log_func: Функция для вывода логов (по умолчанию print)
    """
    with sqlite3.connect(db_file) as conn:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        
        # Таблица аудиокниг
        c.execute("""
            CREATE TABLE IF NOT EXISTS audiobooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                parent_path TEXT,
                name TEXT NOT NULL,
                author TEXT,
                title TEXT,
                narrator TEXT,
                tag_author TEXT,
                tag_title TEXT,
                tag_narrator TEXT,
                tag_year TEXT,
                cover_path TEXT,
                file_count INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                listened_duration REAL DEFAULT 0,
                is_folder INTEGER NOT NULL,
                current_file_index INTEGER DEFAULT 0,
                current_position REAL DEFAULT 0,
                playback_speed REAL DEFAULT 1.0,
                progress_percent INTEGER DEFAULT 0,
                is_started INTEGER DEFAULT 0,
                is_completed INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                use_id3_tags INTEGER DEFAULT 1,
                is_expanded INTEGER DEFAULT 0,
                state_hash TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица файлов аудиокниг
        c.execute("""
            CREATE TABLE IF NOT EXISTS audiobook_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audiobook_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT,
                track_number INTEGER,
                duration REAL DEFAULT 0,
                tag_title TEXT,
                tag_artist TEXT,
                tag_album TEXT,
                tag_genre TEXT,
                tag_comment TEXT,
                FOREIGN KEY(audiobook_id) REFERENCES audiobooks(id)
                    ON DELETE CASCADE
            )
        """)
        
        # Индексы
        c.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON audiobooks(parent_path)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_folder ON audiobooks(is_folder)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_started ON audiobooks(is_started)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_completed ON audiobooks(is_completed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audiobook_id ON audiobook_files(audiobook_id)")

        # Миграция: добавляем колонку is_expanded если её нет
        try:
            c.execute("ALTER TABLE audiobooks ADD COLUMN is_expanded INTEGER DEFAULT 0")
            if log_func:
                log_func("scanner.db_added_expanded")
        except sqlite3.OperationalError:
            pass # Колонка уже существует

        # Миграция: добавляем колонку state_hash если её нет
        try:
            c.execute("ALTER TABLE audiobooks ADD COLUMN state_hash TEXT")
        except sqlite3.OperationalError:
            pass # Колонка уже существует
        
        conn.commit()


class DatabaseManager:
    """Manager for audiobook database operations"""
    
    def __init__(self, db_file: Path):
        self.db_file = db_file

    def clear_all_data(self):
        """Полная очистка всех таблиц базы данных"""
        if not self.db_file.exists():
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DELETE FROM audiobook_files")
            cursor.execute("DELETE FROM audiobooks")
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error clearing database: {e}")
            raise e
        finally:
            conn.close()
    
    def load_audiobooks_from_db(self, filter_type: str = 'all') -> Dict:
        """Загрузка аудиокниг из БД с применением фильтра"""
        if not self.db_file.exists():
            return {}
        
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            
            columns = '''
                path, parent_path, name, author, title, narrator, cover_path,
                is_folder, file_count, duration, listened_duration, progress_percent,
                is_started, is_completed, is_available, is_expanded, last_updated
            '''
            
            columns_with_prefix = '''
                p.path, p.parent_path, p.name, p.author, p.title, p.narrator, p.cover_path,
                p.is_folder, p.file_count, p.duration, p.listened_duration, p.progress_percent,
                p.is_started, p.is_completed, p.is_available, p.is_expanded, p.last_updated
            '''
            
            if filter_type == 'all':
                query = f'SELECT {columns} FROM audiobooks WHERE is_available = 1 ORDER BY is_folder DESC, name'
                cursor.execute(query)
                
            else:
                # Условие фильтра для аудиокниг (не папок)
                filter_condition = 'is_folder = 0'
                
                if filter_type == 'completed':
                    filter_condition += ' AND is_completed = 1'
                elif filter_type == 'recent_added':
                    filter_condition += '''
                        AND progress_percent = 0 
                        AND datetime(last_updated) >= datetime('now', '-30 days')
                    '''
                elif filter_type == 'in_progress':
                    filter_condition += ' AND is_started = 1 AND is_completed = 0'
                elif filter_type == 'not_started':
                    filter_condition += ' AND is_started = 0'
                
                # Всегда фильтруем по доступности
                filter_condition += ' AND is_available = 1'
                
                # Рекурсивный запрос для получения всех уровней родительских папок
                query = f'''
                    WITH RECURSIVE 
                    -- 1. Отфильтрованные аудиокниги
                    filtered_audiobooks AS (
                        SELECT {columns} 
                        FROM audiobooks 
                        WHERE {filter_condition}
                    ),
                    -- 2. Рекурсивный поиск ВСЕХ родительских папок
                    all_parent_folders AS (
                        -- Базовый случай: прямые родители отфильтрованных аудиокниг
                        SELECT {columns_with_prefix}
                        FROM audiobooks p
                        WHERE p.is_folder = 1 
                          AND p.path IN (SELECT parent_path FROM filtered_audiobooks)
                        
                        UNION
                        
                        -- Рекурсия: родители родителей
                        SELECT {columns_with_prefix}
                        FROM audiobooks p
                        INNER JOIN all_parent_folders apf ON p.path = apf.parent_path
                        WHERE p.is_folder = 1
                    )
                    -- 3. Объединяем аудиокниги и ВСЕ их родительские папки
                    SELECT * FROM filtered_audiobooks
                    UNION
                    SELECT * FROM all_parent_folders
                    ORDER BY is_folder DESC, name
                '''
                cursor.execute(query)
            
            rows = cursor.fetchall()
            
            data_by_parent = {}
            for row in rows:
                path, parent_path, name, author, title, narrator, cover_path, \
                is_folder, file_count, duration, listened_duration, progress_percent, \
                is_started, is_completed, is_available, is_expanded, last_updated = row
                
                data_by_parent.setdefault(parent_path, []).append({
                    'path': path,
                    'name': name,
                    'author': author,
                    'title': title,
                    'narrator': narrator,
                    'cover_path': cover_path,
                    'is_folder': bool(is_folder),
                    'file_count': file_count or 0,
                    'duration': duration or 0,
                    'listened_duration': listened_duration or 0,
                    'progress_percent': progress_percent or 0,
                    'is_started': bool(is_started),
                    'is_completed': bool(is_completed),
                    'is_available': bool(is_available),
                    'is_expanded': bool(is_expanded),
                    'last_updated': last_updated
                })
            
            return data_by_parent
        except sqlite3.Error as e:
            print(f"Database error in load_audiobooks_from_db: {e}")
            return {}
        finally:
            conn.close()

    def mark_audiobook_started(self, audiobook_id: int):
        """Отметка аудиокниги как начатой"""
        if not audiobook_id:
            return
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE audiobooks
                SET is_started = 1, is_completed = 0
                WHERE id = ?
            ''', (audiobook_id,))
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in mark_audiobook_started: {e}")
        finally:
            conn.close()

    def get_audiobook_info(self, audiobook_path: str) -> Optional[Tuple]:
        """Получение информации об аудиокниге"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, name, author, title, current_file_index, current_position, duration, 
                   COALESCE(playback_speed, 1.0), COALESCE(use_id3_tags, 1)
            FROM audiobooks WHERE path = ? AND is_folder = 0
        ''', (audiobook_path,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_info: {e}")
            return None
        finally:
            conn.close()
    
    def get_audiobook_files(self, audiobook_id: int) -> List[Tuple]:
        """Получение списка файлов аудиокниги"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_path, file_name, duration, track_number, tag_title
                FROM audiobook_files WHERE audiobook_id = ?
                ORDER BY track_number, file_name
            ''', (audiobook_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_files: {e}")
            return []
        finally:
            conn.close()
    
    def save_progress(self, audiobook_id: int, file_index: int, position: float,
                      speed: float, listened_duration: float, progress_percent: int):
        """Сохранение прогресса воспроизведения"""
        if not audiobook_id:
            return
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # Определяем статусы
            # Не сбрасываем is_started в 0, если он уже 1
            cursor.execute("SELECT is_started FROM audiobooks WHERE id = ?", (audiobook_id,))
            row = cursor.fetchone()
            old_is_started = row[0] if row else 0
            
            is_started = 1 if (old_is_started or progress_percent > 0) else 0
            is_completed = 1 if progress_percent >= 100 else 0
            
            cursor.execute('''
                UPDATE audiobooks
                SET current_file_index = ?, current_position = ?, playback_speed = ?,
                    listened_duration = ?, progress_percent = ?,
                    is_started = ?, is_completed = ?
                WHERE id = ?
            ''', (file_index, position, speed, listened_duration, progress_percent,
                  is_started, is_completed, audiobook_id))
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in save_progress: {e}")
        finally:
            conn.close()

    def update_audiobook_speed(self, audiobook_id: int, speed: float):
        """Обновление скорости воспроизведения"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET playback_speed = ?
                WHERE id = ?
            ''', (speed, audiobook_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in update_audiobook_speed: {e}")
        finally:
            conn.close()
    
    def mark_audiobook_completed(self, audiobook_id: int, total_duration: float):
        """Отметка аудиокниги как прослушанной"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET listened_duration = ?, progress_percent = 100,
                    is_completed = 1, is_started = 1
                WHERE id = ?
            ''', (total_duration, audiobook_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in mark_audiobook_completed: {e}")
        finally:
            conn.close()

    def reset_audiobook_status(self, audiobook_id: int):
        """Сброс статуса аудиокниги (не начата)"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET listened_duration = 0, progress_percent = 0,
                    current_file_index = 0, current_position = 0,
                    is_started = 0, is_completed = 0
                WHERE id = ?
            ''', (audiobook_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in reset_audiobook_status: {e}")
        finally:
            conn.close()

    def update_audiobook_id3_state(self, audiobook_id: int, state: bool):
        """Обновление состояния ID3 тегов для книги"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET use_id3_tags = ?
                WHERE id = ?
            ''', (1 if state else 0, audiobook_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in update_audiobook_id3_state: {e}")
        finally:
            conn.close()
    
    def get_audiobook_count(self) -> int:
        """Получение количества аудиокниг"""
        if not self.db_file.exists():
            return 0
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0')
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_count: {e}")
            return 0
        finally:
            conn.close()
    
    def get_audiobook_by_path(self, path: str) -> Optional[Dict]:
        """Получение данных аудиокниги по пути для обновления дерева"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT author, title, narrator, file_count, duration, 
                       listened_duration, progress_percent
                FROM audiobooks 
                WHERE path = ? AND is_folder = 0
            ''', (path,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'author': row[0],
                    'title': row[1],
                    'narrator': row[2],
                    'file_count': row[3],
                    'duration': row[4],
                    'listened_duration': row[5],
                    'progress_percent': row[6]
                }
            return None
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_by_path: {e}")
            return None
        finally:
            conn.close()

    def update_folder_expanded_state(self, path: str, is_expanded: bool):
        """Обновление состояния развернутости папки"""
        # Работаем только с папками (is_folder=1)
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET is_expanded = ?
                WHERE path = ? AND is_folder = 1
            ''', (1 if is_expanded else 0, path))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in update_folder_expanded_state: {e}")
        finally:
            conn.close()
