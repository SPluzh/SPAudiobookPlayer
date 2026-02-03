"""
Database Manager Module
Provides database operations for the audiobook player application.
"""

import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable


def init_database(db_file: Path, log_func: Callable[[str], None] = print):
    """
    Initialize the database - create tables and indexes.
    Called from scanner.py during library scanning.
    
    Args:
        db_file: Path to the database file
        log_func: Function for logging output (default is print)
    """
    with sqlite3.connect(db_file) as conn:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        
        # Audiobooks table
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
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_favorite INTEGER DEFAULT 0
            )
        """)
        
        # Audiobook files table
        c.execute("""
            CREATE TABLE IF NOT EXISTS audiobook_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audiobook_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT,
                track_number INTEGER,
                duration REAL DEFAULT 0,
                start_offset REAL DEFAULT 0,
                tag_title TEXT,
                tag_artist TEXT,
                tag_album TEXT,
                tag_genre TEXT,
                tag_comment TEXT,
                FOREIGN KEY(audiobook_id) REFERENCES audiobooks(id)
                    ON DELETE CASCADE
            )
        """)
        
        
        # Tags table
        c.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT
            )
        """)
        
        # Audiobooks-Tags Link Table
        c.execute("""
            CREATE TABLE IF NOT EXISTS audiobook_tags (
                audiobook_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (audiobook_id, tag_id),
                FOREIGN KEY (audiobook_id) REFERENCES audiobooks(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)

        # Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON audiobooks(parent_path)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_folder ON audiobooks(is_folder)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_started ON audiobooks(is_started)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_is_completed ON audiobooks(is_completed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audiobook_id ON audiobook_files(audiobook_id)")

        # Migration: add is_expanded column if it doesn't exist
        try:
            c.execute("ALTER TABLE audiobooks ADD COLUMN is_expanded INTEGER DEFAULT 0")
            if log_func:
                log_func("scanner.db_added_expanded")
        except sqlite3.OperationalError:
            pass # Column already exists

        # Migration: add state_hash column if it doesn't exist
        try:
            c.execute("ALTER TABLE audiobooks ADD COLUMN state_hash TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists

        # Migration: add start_offset column to audiobook_files if it doesn't exist
        try:
            c.execute("ALTER TABLE audiobook_files ADD COLUMN start_offset REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Column already exists

        # Migration: add technical info columns
        new_columns = {
            'codec': 'TEXT',
            'bitrate_min': 'INTEGER',
            'bitrate_max': 'INTEGER',
            'bitrate_mode': 'TEXT',
            'container': 'TEXT',
            'time_added': 'TIMESTAMP',
            'time_started': 'TIMESTAMP',
            'time_finished': 'TIMESTAMP'
        }
        
        for col, type_ in new_columns.items():
            try:
                c.execute(f"ALTER TABLE audiobooks ADD COLUMN {col} {type_}")
                if log_func:
                    log_func(f"scanner.db_added_{col}")
            except sqlite3.OperationalError:
                pass

        # Migration: add is_favorite column
        try:
            c.execute("ALTER TABLE audiobooks ADD COLUMN is_favorite INTEGER DEFAULT 0")
            if log_func:
                log_func("scanner.db_added_is_favorite")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Migration: create tags tables if they don't exist (handled by CREATE TABLE IF NOT EXISTS above)

        conn.commit()


class DatabaseManager:
    """Manager for audiobook database operations"""
    
    def __init__(self, db_file: Path):
        """Initialize with database file path"""
        self.db_file = db_file

    def clear_all_data(self):
        """Completely clear all database tables"""
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
        """Load audiobooks from database with specified filter"""
        if not self.db_file.exists():
            return {}
        
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            
            columns = '''
                path, parent_path, name, author, title, narrator, cover_path,
                is_folder, file_count, duration, listened_duration, progress_percent,
                is_started, is_completed, is_available, is_expanded, last_updated,
                codec, bitrate_min, bitrate_max, bitrate_mode, container,
                time_added, time_started, time_finished, is_favorite, id
            '''
            
            columns_with_prefix = '''
                p.path, p.parent_path, p.name, p.author, p.title, p.narrator, p.cover_path,
                p.is_folder, p.file_count, p.duration, p.listened_duration, p.progress_percent,
                p.is_started, p.is_completed, p.is_available, p.is_expanded, p.last_updated,
                p.codec, p.bitrate_min, p.bitrate_max, p.bitrate_mode, p.container,
                p.time_added, p.time_started, p.time_finished, p.is_favorite, p.id
            '''
            
            if filter_type == 'all':
                query = f'SELECT {columns} FROM audiobooks WHERE is_available = 1 ORDER BY is_folder DESC, name'
                cursor.execute(query)
                
            else:
                # Filter condition for audiobooks (not folders)
                filter_condition = 'is_folder = 0'
                order_by = 'is_folder DESC, name'
                
                if filter_type == 'completed':
                    filter_condition += ' AND is_completed = 1'
                    order_by = 'is_folder DESC, time_finished DESC, name'
                elif filter_type == 'in_progress':
                    filter_condition += ' AND is_started = 1 AND is_completed = 0'
                    # Sort primarily by recency, so active books (and their folders) jump to top
                    # is_folder DESC is removed from primary sort so folders don't artificially float to top
                    order_by = 'last_updated DESC, is_folder DESC, name'
                elif filter_type == 'not_started':
                    # "New" filter: Not started, sorted by time_added
                    filter_condition += ' AND is_started = 0'
                    order_by = 'is_folder DESC, time_added DESC, name'
                elif filter_type == 'favorites':
                    filter_condition += ' AND is_favorite = 1'
                    order_by = 'is_folder DESC, name'
                
                # Always filter by availability
                filter_condition += ' AND is_available = 1'
                
                # Recursive query to get all levels of parent folders
                query = f'''
                    WITH RECURSIVE 
                    -- 1. Filtered audiobooks
                    filtered_audiobooks AS (
                        SELECT {columns} 
                        FROM audiobooks 
                        WHERE {filter_condition}
                    ),
                    -- 2. Recursive search for ALL parent folders
                    all_parent_folders AS (
                        -- Base case: direct parents of filtered audiobooks
                        SELECT {columns_with_prefix}
                        FROM audiobooks p
                        WHERE p.is_folder = 1 
                          AND p.path IN (SELECT parent_path FROM filtered_audiobooks)
                        
                        UNION
                        
                        -- Recursion: parents of parents
                        SELECT {columns_with_prefix}
                        FROM audiobooks p
                        INNER JOIN all_parent_folders apf ON p.path = apf.parent_path
                        WHERE p.is_folder = 1
                    )
                    -- 3. Combine audiobooks and ALL their parent folders
                    SELECT * FROM (
                        SELECT * FROM filtered_audiobooks
                        UNION
                        SELECT * FROM all_parent_folders
                    )
                    ORDER BY {order_by}
                '''
                cursor.execute(query)
            
            rows = cursor.fetchall()
            
            data_by_parent = {}
            for row in rows:
                path, parent_path, name, author, title, narrator, cover_path, \
                is_folder, file_count, duration, listened_duration, progress_percent, \
                is_started, is_completed, is_available, is_expanded, last_updated, \
                codec, bitrate_min, bitrate_max, bitrate_mode, container, \
                time_added, time_started, time_finished, is_favorite, audiobook_id = row
                
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
                    'last_updated': last_updated,
                    'codec': codec,
                    'bitrate_min': bitrate_min,
                    'bitrate_max': bitrate_max,
                    'bitrate_mode': bitrate_mode,
                    'container': container,
                    'time_added': time_added,
                    'time_started': time_started,
                    'time_finished': time_finished,
                    'is_favorite': bool(is_favorite),
                    'id': audiobook_id
                })
            
            return data_by_parent
        except sqlite3.Error as e:
            print(f"Database error in load_audiobooks_from_db: {e}")
            return {}
        finally:
            conn.close()

    def update_last_updated(self, audiobook_id: int):
        """Update the last_updated timestamp for an audiobook"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (audiobook_id,))
            
            # Propagate update to parents
            self._propagate_last_updated(cursor, audiobook_id)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in update_last_updated: {e}")
        finally:
            conn.close()

    def mark_audiobook_started(self, audiobook_id: int):
        """Mark an audiobook as started"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET is_started = 1, is_completed = 0,
                    time_started = COALESCE(time_started, CURRENT_TIMESTAMP),
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (audiobook_id,))
            
            # Propagate update to parents
            self._propagate_last_updated(cursor, audiobook_id)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in mark_audiobook_started: {e}")
        finally:
            conn.close()

    def mark_audiobook_completed(self, audiobook_id: int, total_duration: float):
        """Mark an audiobook as completely listened"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET listened_duration = ?, progress_percent = 100,
                    is_completed = 1, is_started = 1,
                    time_started = COALESCE(time_started, CURRENT_TIMESTAMP),
                    time_finished = COALESCE(time_finished, CURRENT_TIMESTAMP),
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (total_duration, audiobook_id))
            
            # Propagate update to parents
            self._propagate_last_updated(cursor, audiobook_id)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in mark_audiobook_completed: {e}")
        finally:
            conn.close()

    def reset_audiobook_status(self, audiobook_id: int):
        """Reset audiobook status to 'not started'"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE audiobooks
                SET listened_duration = 0, progress_percent = 0,
                    current_file_index = 0, current_position = 0,
                    is_started = 0, is_completed = 0,
                    time_started = NULL, time_finished = NULL,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (audiobook_id,))
            
            # Propagate update to parents
            self._propagate_last_updated(cursor, audiobook_id)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in reset_audiobook_status: {e}")
        finally:
            conn.close()

    def _propagate_last_updated(self, cursor, audiobook_id):
        """Helper to recursively update last_updated for parent folders"""
        cursor.execute("SELECT path FROM audiobooks WHERE id = ?", (audiobook_id,))
        row = cursor.fetchone()
        if not row:
            return
        current_path = row[0]
        
        from pathlib import Path
        path_obj = Path(current_path)
        
        while True:
            parent = path_obj.parent
            if str(parent) == '.' or str(parent) == str(path_obj):
                break
                
            path_obj = parent
            parent_str = str(path_obj).replace('\\', '/')
            
            cursor.execute('''
                UPDATE audiobooks 
                SET last_updated = CURRENT_TIMESTAMP 
                WHERE path = ? AND is_folder = 1
            ''', (parent_str,))
            
            if cursor.rowcount == 0:
                 pass

    def get_audiobook_info(self, audiobook_path: str) -> Optional[Tuple]:
        """Get information about a specific audiobook by path"""
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
        """Get list of files for a specific audiobook by ID"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_path, file_name, duration, track_number, tag_title, start_offset
                FROM audiobook_files WHERE audiobook_id = ?
                ORDER BY track_number, start_offset, file_name
            ''', (audiobook_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_files: {e}")
            return []
        finally:
            conn.close()
    
    def save_progress(self, audiobook_id: int, file_index: int, position: float,
                      speed: float, listened_duration: float, progress_percent: int,
                      update_timestamp: bool = True):
        """Save playback progress for an audiobook"""
        if not audiobook_id:
            return
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            # Determine status
            # Do not reset is_started to 0 if it's already 1
            cursor.execute("SELECT is_started FROM audiobooks WHERE id = ?", (audiobook_id,))
            row = cursor.fetchone()
            old_is_started = row[0] if row else 0
            
            is_started = 1 if (old_is_started or progress_percent > 0) else 0
            is_completed = 1 if progress_percent >= 100 else 0
            
            update_sql = '''
                UPDATE audiobooks
                SET current_file_index = ?, current_position = ?, playback_speed = ?,
                    listened_duration = ?, progress_percent = ?,
                    is_started = ?, is_completed = ?,
                    time_started = CASE WHEN ? = 1 AND time_started IS NULL THEN CURRENT_TIMESTAMP ELSE time_started END,
                    time_finished = CASE WHEN ? = 1 AND time_finished IS NULL THEN CURRENT_TIMESTAMP ELSE time_finished END
            '''
            
            params = [file_index, position, speed, listened_duration, progress_percent,
                      is_started, is_completed, is_started, is_completed]
            
            if update_timestamp:
                update_sql += ", last_updated = CURRENT_TIMESTAMP "
            
            update_sql += " WHERE id = ?"
            params.append(audiobook_id)
            
            cursor.execute(update_sql, tuple(params))
            
            if update_timestamp:
                # Recursively update last_updated for all parent folders
                self._propagate_last_updated(cursor, audiobook_id)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in save_progress: {e}")
        finally:
            conn.close()

    def delete_audiobook(self, audiobook_id: int):
        """Delete an audiobook and its associated files from the database"""
        if not audiobook_id:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM audiobooks WHERE id = ?", (audiobook_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in delete_audiobook: {e}")
            raise e
        finally:
            conn.close()

    def delete_folder(self, folder_path: str):
        """Recursively delete a folder and all its contents (audiobooks and subfolders) from the database"""
        if not folder_path:
            return
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            # Delete the folder itself and everything starting with 'folder_path\'
            pattern = folder_path + os.sep + '%'
            cursor.execute('''
                DELETE FROM audiobooks 
                WHERE path = ? OR path LIKE ?
            ''', (folder_path, pattern))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in delete_folder: {e}")
            raise e
        finally:
            conn.close()

    def get_folder_contents(self, folder_path: str) -> List[Tuple[str, bool]]:
        """Get names of all nested audiobooks and subfolders for a given folder path"""
        if not folder_path:
            return []
            
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            pattern = folder_path + os.sep + '%'
            cursor.execute('''
                SELECT name, is_folder FROM audiobooks 
                WHERE path LIKE ?
                ORDER BY is_folder DESC, name ASC
            ''', (pattern,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error in get_folder_contents: {e}")
            return []
        finally:
            conn.close()

    def update_audiobook_speed(self, audiobook_id: int, speed: float):
        """Update playback speed for an audiobook"""
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
    
    def update_audiobook_id3_state(self, audiobook_id: int, state: bool):
        """Update ID3 tags usage state for an audiobook"""
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
        """Get total number of audiobooks in the library"""
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
        """Get audiobook data by its path for tree updates"""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT author, title, narrator, file_count, duration, 
                       listened_duration, progress_percent, is_started, is_completed,
                       codec, bitrate_min, bitrate_max, bitrate_mode, container,
                       time_added, time_started, time_finished, is_favorite
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
                    'progress_percent': row[6],
                    'is_started': bool(row[7]),
                    'is_completed': bool(row[8]),
                    'codec': row[9],
                    'bitrate_min': row[10],
                    'bitrate_max': row[11],
                    'bitrate_mode': row[12],
                    'container': row[13],
                    'time_added': row[14],
                    'time_started': row[15],
                    'time_finished': row[16],
                    'is_favorite': bool(row[17])
                }
            return None
        except sqlite3.Error as e:
            print(f"Database error in get_audiobook_by_path: {e}")
            return None
        finally:
            conn.close()


    def update_folder_expanded_state(self, path: str, is_expanded: bool):
        """Update the is_expanded state for a folder"""
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

    # --- Favorites & Tags Methods ---

    def toggle_favorite(self, audiobook_id: int) -> bool:
        """Toggle the favorite status of an audiobook. Returns the new state."""
        if not audiobook_id:
            return False

        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            
            # Get current state
            cursor.execute("SELECT is_favorite FROM audiobooks WHERE id = ?", (audiobook_id,))
            row = cursor.fetchone()
            if not row:
                return False
                
            new_state = 0 if row[0] else 1
            
            cursor.execute("UPDATE audiobooks SET is_favorite = ? WHERE id = ?", (new_state, audiobook_id))
            conn.commit()
            return bool(new_state)
        except sqlite3.Error as e:
            print(f"Database error in toggle_favorite: {e}")
            return False
        finally:
            conn.close()

    def create_tag(self, name: str, color: str = None) -> Optional[int]:
        """Create a new tag. Returns the tag ID or None if failed (e.g. duplicate)."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
            tag_id = cursor.lastrowid
            conn.commit()
            return tag_id
        except sqlite3.IntegrityError:
            return None # Duplicate name
        except sqlite3.Error as e:
            print(f"Database error in create_tag: {e}")
            return None
        finally:
            conn.close()

    def delete_tag(self, tag_id: int):
        """Delete a tag."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in delete_tag: {e}")
        finally:
            conn.close()
            
    def update_tag(self, tag_id: int, name: str, color: str):
        """Update a tag's name and color."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE tags SET name = ?, color = ? WHERE id = ?", (name, color, tag_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in update_tag: {e}")
        finally:
            conn.close()

    def add_tag_to_audiobook(self, audiobook_id: int, tag_id: int):
        """Assign a tag to an audiobook."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO audiobook_tags (audiobook_id, tag_id) VALUES (?, ?)", 
                           (audiobook_id, tag_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in add_tag_to_audiobook: {e}")
        finally:
            conn.close()

    def remove_tag_from_audiobook(self, audiobook_id: int, tag_id: int):
        """Remove a tag from an audiobook."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM audiobook_tags WHERE audiobook_id = ? AND tag_id = ?", 
                           (audiobook_id, tag_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error in remove_tag_from_audiobook: {e}")
        finally:
            conn.close()

    def get_all_tags(self) -> List[Dict]:
        """Get all defined tags."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, color FROM tags ORDER BY name")
            return [{'id': row[0], 'name': row[1], 'color': row[2]} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error in get_all_tags: {e}")
            return []
        finally:
            conn.close()

    def get_tags_for_audiobook(self, audiobook_id: int) -> List[Dict]:
        """Get tags assigned to a specific audiobook."""
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            query = """
                SELECT t.id, t.name, t.color 
                FROM tags t
                JOIN audiobook_tags at ON t.id = at.tag_id
                WHERE at.audiobook_id = ?
                ORDER BY t.color, t.name
            """
            cursor.execute(query, (audiobook_id,))
            return [{'id': row[0], 'name': row[1], 'color': row[2]} for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error in get_tags_for_audiobook: {e}")
            return []
        finally:
            conn.close()

    def get_all_audiobook_tags(self) -> Dict[int, List[Dict]]:
        """
        Get a mapping of audiobook_id -> list of tags. 
        Used for efficient bulk loading in the library view.
        """
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            query = """
                SELECT at.audiobook_id, t.id, t.name, t.color
                FROM tags t
                JOIN audiobook_tags at ON t.id = at.tag_id
                ORDER BY t.color, t.name
            """
            cursor.execute(query)
            
            result = {}
            for row in cursor.fetchall():
                aid = row[0]
                tag = {'id': row[1], 'name': row[2], 'color': row[3]}
                result.setdefault(aid, []).append(tag)
            return result
        except sqlite3.Error as e:
            print(f"Database error in get_all_audiobook_tags: {e}")
            return {}
        finally:
            conn.close()

