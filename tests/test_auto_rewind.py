import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from database import DatabaseManager, init_database
from player import PlaybackController


def setup_test_db_with_chapters(tmp_path):
    db_file = tmp_path / "test_rewind.db"
    db = DatabaseManager(str(db_file))
    init_database(db_file, log_func=None)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audiobooks (path, name, is_folder, is_playlist, duration, playback_speed)
        VALUES ('book_with_chapters.m4b', 'Chapter Book', 0, 0, 1000, 1.0)
    """)
    book_id = cursor.lastrowid

    # Chapter 1: 0 - 300s
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, start_offset)
        VALUES (?, 'book_with_chapters.m4b', 'Chapter 1', 1, 300, 0)
    """, (book_id,))

    # Chapter 2: 300 - 500s (offset: 300, duration: 200)
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, start_offset)
        VALUES (?, 'book_with_chapters.m4b', 'Chapter 2', 2, 200, 300)
    """, (book_id,))

    conn.commit()
    conn.close()
    return db, book_id


def test_playback_controller_rewind_respects_chapter_start_offset(tmp_path):
    """When rewinding within a chapter that has a start_offset > 0, it must not go below start_offset."""
    db, book_id = setup_test_db_with_chapters(tmp_path)

    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.chan = 1
    player_mock.speed_pos = 10
    # Simulate current playback position is 305s (5 seconds into Chapter 2)
    player_mock.get_position.return_value = 305.0
    player_mock.get_duration.return_value = 1000.0

    controller = PlaybackController(player_mock, db)
    # Set current file index to Chapter 2 (index 1)
    controller.files_list = [
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 1', 'duration': 300, 'start_offset': 0, 'is_url': False},
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 2', 'duration': 200, 'start_offset': 300, 'is_url': False},
    ]
    controller.current_file_index = 1

    # Rewind 30 seconds (like auto-rewind on pause or close)
    controller.rewind(-30)

    # Must be clamped to start_offset (300.0), NOT 275.0
    player_mock.set_position.assert_called_once_with(300.0)


def test_playback_controller_rewind_respects_chapter_duration(tmp_path):
    """When fast forwarding, it must not exceed chapter duration (start_offset + duration)."""
    db, book_id = setup_test_db_with_chapters(tmp_path)

    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.chan = 1
    player_mock.speed_pos = 10
    # Current pos is 490s in Chapter 2 (starts at 300, duration 200 -> end is 500)
    player_mock.get_position.return_value = 490.0
    player_mock.get_duration.return_value = 1000.0

    controller = PlaybackController(player_mock, db)
    controller.files_list = [
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 1', 'duration': 300, 'start_offset': 0, 'is_url': False},
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 2', 'duration': 200, 'start_offset': 300, 'is_url': False},
    ]
    controller.current_file_index = 1

    # Forward 30 seconds
    controller.rewind(30)

    # Must be clamped to start_offset + duration (500.0), NOT 520.0
    player_mock.set_position.assert_called_once_with(500.0)


def test_playback_controller_rewind_standard_file(tmp_path):
    """For standard files with start_offset = 0, rewinding clamps to 0."""
    db, book_id = setup_test_db_with_chapters(tmp_path)

    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.chan = 1
    player_mock.speed_pos = 10
    player_mock.get_position.return_value = 5.0
    player_mock.get_duration.return_value = 300.0

    controller = PlaybackController(player_mock, db)
    controller.files_list = [
        {'path': 'track1.mp3', 'name': 'Track 1', 'duration': 300, 'start_offset': 0, 'is_url': False},
    ]
    controller.current_file_index = 0

    controller.rewind(-30)

    # Clamped to 0.0
    player_mock.set_position.assert_called_once_with(0.0)


def test_load_audiobook_repairs_corrupted_saved_position(tmp_path):
    """If saved_position in database was corrupted to be < start_offset, load_audiobook seeks to start_offset."""
    db, book_id = setup_test_db_with_chapters(tmp_path)

    # Corrupt the DB: Chapter 2 (index 1) saved with position 275.0 (which is < 300.0 start_offset)
    conn = sqlite3.connect(tmp_path / "test_rewind.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE audiobooks
        SET current_file_index = 1, current_position = 275.0
        WHERE id = ?
    """, (book_id,))
    conn.commit()
    conn.close()

    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.load.return_value = True
    player_mock.speed_pos = 10

    controller = PlaybackController(player_mock, db)
    controller.library_root = tmp_path

    success = controller.load_audiobook('book_with_chapters.m4b')
    assert success is True

    # set_position should have been called with start_offset (300.0), NOT the corrupted 275.0
    player_mock.set_position.assert_called_with(300.0)


def test_save_current_progress_clamps_to_start_offset(tmp_path):
    """save_current_progress never saves a position less than the chapter's start_offset."""
    db, book_id = setup_test_db_with_chapters(tmp_path)

    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.chan = 1
    player_mock.speed_pos = 10
    # Simulate an edge case where player position somehow reports 250.0 (less than 300.0)
    player_mock.get_position.return_value = 250.0

    controller = PlaybackController(player_mock, db)
    controller.current_audiobook_id = book_id
    controller.files_list = [
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 1', 'duration': 300, 'start_offset': 0, 'is_url': False},
        {'path': 'book_with_chapters.m4b', 'name': 'Chapter 2', 'duration': 200, 'start_offset': 300, 'is_url': False},
    ]
    controller.current_file_index = 1
    controller.total_duration = 500

    controller.save_current_progress()

    conn = sqlite3.connect(tmp_path / "test_rewind.db")
    cursor = conn.cursor()
    cursor.execute("SELECT current_position FROM audiobooks WHERE id = ?", (book_id,))
    saved_pos = cursor.fetchone()[0]
    conn.close()

    # The saved position must be at least start_offset (300.0)
    assert saved_pos == 300.0
