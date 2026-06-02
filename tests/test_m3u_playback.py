import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from database import DatabaseManager, init_database

def test_update_file_duration(tmp_path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(str(db_file))
    
    # Create tables
    init_database(db_file, log_func=None)
    
    # Insert dummy audiobook and files
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audiobooks (path, name, is_folder, is_playlist, duration)
        VALUES ('playlist.m3u', 'Test Book', 0, 1, 0)
    """)
    book_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, is_url)
        VALUES (?, 'https://example.com/track1.mp3', 'track1.mp3', 1, 0, 1)
    """, (book_id,))
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, is_url)
        VALUES (?, 'https://example.com/track2.mp3', 'track2.mp3', 2, 50, 1)
    """, (book_id,))
    conn.commit()
    conn.close()
    
    # Test update_file_duration
    db.update_file_duration(book_id, 'https://example.com/track1.mp3', 120.0)
    
    # Verify values
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT duration FROM audiobook_files WHERE file_name = 'track1.mp3'")
    assert cursor.fetchone()[0] == 120.0
    
    cursor.execute("SELECT duration FROM audiobooks WHERE id = ?", (book_id,))
    assert cursor.fetchone()[0] == 170.0
    conn.close()

def test_playback_controller_url_handling(tmp_path):
    from player import PlaybackController
    db_file = tmp_path / "test.db"
    db = DatabaseManager(str(db_file))
    init_database(db_file, log_func=None)
    
    # Insert audiobook with a URL file
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audiobooks (path, name, is_folder, is_playlist, duration, playback_speed)
        VALUES ('playlist.m3u', 'Test Book', 0, 1, 0, 1.0)
    """)
    book_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, is_url)
        VALUES (?, 'https://example.com/track1.mp3', 'track1.mp3', 1, 0, 1)
    """, (book_id,))
    conn.commit()
    conn.close()
    
    # Setup mocks for player
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.is_playing.return_value = False
    player_mock.load.return_value = True
    player_mock.get_duration.return_value = 150.0
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    controller.library_root = Path(tmp_path)
    
    # Load audiobook
    success = controller.load_audiobook('playlist.m3u')
    assert success is True
    
    # Verify player load called with URL as-is, not combined with library_root
    player_mock.load.assert_called_with('https://example.com/track1.mp3')
    
    # Verify lazy duration update happened
    assert controller.files_list[0]['duration'] == 150.0
    assert controller.total_duration == 150.0
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT duration FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
    assert cursor.fetchone()[0] == 150.0
    cursor.execute("SELECT duration FROM audiobooks WHERE id = ?", (book_id,))
    assert cursor.fetchone()[0] == 150.0
    conn.close()

def test_playback_controller_callbacks(tmp_path):
    from player import PlaybackController
    db_file = tmp_path / "test.db"
    db = DatabaseManager(str(db_file))
    init_database(db_file, log_func=None)
    
    # Insert audiobook with a URL file
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audiobooks (path, name, is_folder, is_playlist, duration, playback_speed)
        VALUES ('playlist.m3u', 'Test Book', 0, 1, 0, 1.0)
    """)
    book_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, is_url)
        VALUES (?, 'https://example.com/track1.mp3', 'track1.mp3', 1, 0, 1)
    """, (book_id,))
    conn.commit()
    conn.close()
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.is_playing.return_value = False
    player_mock.get_position.return_value = 0.0
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    
    start_called = []
    error_called = []
    
    controller.on_load_start = lambda url: start_called.append(url)
    controller.on_load_error = lambda url: error_called.append(url)
    
    # Test case 1: Load fails
    player_mock.load.return_value = False
    success = controller.load_audiobook('playlist.m3u')
    assert success is False
    assert start_called == ['https://example.com/track1.mp3']
    assert error_called == ['https://example.com/track1.mp3']
    
    # Test case 2: Load succeeds
    start_called.clear()
    error_called.clear()
    player_mock.load.return_value = True
    player_mock.get_duration.return_value = 150.0
    success = controller.load_audiobook('playlist.m3u')
    assert success is True
    assert start_called == ['https://example.com/track1.mp3']
    assert error_called == []

