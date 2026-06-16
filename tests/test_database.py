import sqlite3
import pytest
from pathlib import Path
from database import DatabaseManager

def test_clear_all_data_clears_statistics_and_other_tables(temp_db):
    # Initialize DatabaseManager
    db = DatabaseManager(temp_db)
    
    # Connect directly to insert dummy records
    conn = sqlite3.connect(temp_db)
    try:
        cursor = conn.cursor()
        
        # Insert dummy audiobook (is_folder, path, name are required)
        cursor.execute("""
            INSERT INTO audiobooks (id, path, name, author, title, is_folder, duration)
            VALUES (1, 'path/to/book', 'Test Book', 'Test Author', 'Test Title', 0, 1000.0)
        """)
        
        # Insert dummy audiobook file (audiobook_id, file_path are required)
        cursor.execute("""
            INSERT INTO audiobook_files (audiobook_id, file_path, duration)
            VALUES (1, 'path/to/book/01.mp3', 1000.0)
        """)
        
        # Insert dummy tag (name is required and unique)
        cursor.execute("""
            INSERT INTO tags (id, name, color)
            VALUES (1, 'Favorite', '#FF0000')
        """)
        
        # Insert dummy audiobook-tag link
        cursor.execute("""
            INSERT INTO audiobook_tags (audiobook_id, tag_id)
            VALUES (1, 1)
        """)
        
        # Insert dummy bookmark (audiobook_id, file_name, time_position are required)
        cursor.execute("""
            INSERT INTO bookmarks (audiobook_id, file_name, time_position, title, description, created_at)
            VALUES (1, '01.mp3', 500.0, 'Comment', 'Desc', '2026-06-16 12:00:00')
        """)
        
        # Insert dummy cover (audiobook_id, cached_path, source_type are required)
        cursor.execute("""
            INSERT INTO audiobook_covers (audiobook_id, original_path, cached_path, is_selected, source_type)
            VALUES (1, 'orig.jpg', 'cached.jpg', 1, 'folder')
        """)
        
        # Insert dummy file metadata cache (file_path is required)
        cursor.execute("""
            INSERT INTO file_metadata_cache (file_path, file_size, mtime, duration, bitrate, codec, is_vbr)
            VALUES ('path/to/book/01.mp3', 1000000, 123456789.0, 1000.0, 128, 'mp3', 0)
        """)
        
        # Insert dummy listening session (audiobook_id, session_date, session_start are required)
        cursor.execute("""
            INSERT INTO listening_sessions (id, audiobook_id, session_date, session_start, session_end, duration_seconds, playback_speed, is_active)
            VALUES (1, 1, '2026-06-16', '2026-06-16 12:00:00', '2026-06-16 12:10:00', 600.0, 1.0, 0)
        """)
        
        # Insert dummy daily listening stat (audiobook_id, listen_date are required)
        cursor.execute("""
            INSERT INTO daily_listening_stats (audiobook_id, listen_date, total_seconds, session_count)
            VALUES (1, '2026-06-16', 600.0, 1)
        """)
        
        conn.commit()
        
        # Verify that everything is inserted
        tables = [
            'audiobooks', 'audiobook_files', 'tags', 'audiobook_tags',
            'bookmarks', 'audiobook_covers', 'file_metadata_cache',
            'listening_sessions', 'daily_listening_stats'
        ]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count > 0, f"Table {table} should have records before clearing"
    finally:
        conn.close()
    
    # Call clear_all_data
    db.clear_all_data()
    
    # Re-verify that all tables are cleared
    conn = sqlite3.connect(temp_db)
    try:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count == 0, f"Table {table} should be empty after clearing"
    finally:
        conn.close()
