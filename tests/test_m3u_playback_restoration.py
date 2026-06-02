import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from database import DatabaseManager, init_database
from player import PlaybackController

def setup_test_db(tmp_path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(str(db_file))
    init_database(db_file, log_func=None)
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audiobooks (path, name, is_folder, is_playlist, duration, playback_speed)
        VALUES ('playlist.m3u', 'Test Book', 0, 1, 100, 1.0)
    """)
    book_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration, is_url)
        VALUES (?, 'https://example.com/track1.mp3', 'track1.mp3', 1, 100, 1)
    """, (book_id,))
    conn.commit()
    conn.close()
    return db, book_id

def test_save_current_progress_blocked_during_async_load(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.get_position.return_value = 50.0
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    controller.load_audiobook('playlist.m3u')
    
    # Verify that load_audiobook set _url_loading to True
    assert controller._url_loading is True
    
    # We simulate setting progress to something (not zero) in DB
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE audiobooks SET current_position = 45.0 WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    # Now call save_current_progress while loading
    controller.save_current_progress()
    
    # Check that current_position in database was NOT overwritten with 50.0 or 0.0, but remains 45.0
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("SELECT current_position FROM audiobooks WHERE id = ?", (book_id,))
    val = cursor.fetchone()[0]
    conn.close()
    
    assert val == 45.0

def test_load_same_audiobook_does_not_save_progress(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.get_position.return_value = 50.0
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    
    # First load
    controller.load_audiobook('playlist.m3u')
    controller._url_loading = False  # pretend load completed
    
    # Update DB position directly
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE audiobooks SET current_position = 75.0 WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    # Load same audiobook again
    # If the guard works, save_current_progress won't be called, so the position remains 75.0
    controller.load_audiobook('playlist.m3u')
    
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("SELECT current_position FROM audiobooks WHERE id = ?", (book_id,))
    val = cursor.fetchone()[0]
    conn.close()
    
    assert val == 75.0

def test_on_library_play_clicked_async_path():
    # Test checking that on_library_play_clicked does not trigger toggle_play on async load
    main_window_mock = MagicMock()
    playback_controller_mock = MagicMock()
    player_mock = MagicMock()
    
    main_window_mock.playback_controller = playback_controller_mock
    main_window_mock.player = player_mock
    
    # Set up scenario: different book targeted
    playback_controller_mock.current_audiobook_path = "old_book.m3u"
    
    # Simulating load_audiobook starting an async URL load
    def mock_on_audiobook_selected(path):
        playback_controller_mock._url_loading = True
        player_mock.is_playing.return_value = False
        
    main_window_mock.on_audiobook_selected.side_effect = mock_on_audiobook_selected
    player_mock.is_playing.return_value = False
    
    from main import AudiobookPlayerWindow
    # We call the method under test using main_window_mock
    AudiobookPlayerWindow.on_library_play_clicked(main_window_mock, "new_book.m3u")
    
    # Verify: on_audiobook_selected was called
    main_window_mock.on_audiobook_selected.assert_called_once_with("new_book.m3u")
    # Verify: toggle_play was NOT called because _url_loading was True
    main_window_mock.toggle_play.assert_not_called()


def test_async_load_seeks_before_playback_and_clearing_url_loading(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    # We want to restore a session to a saved position of 45.0
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE audiobooks SET current_position = 45.0 WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.get_position.return_value = 0.0 # initially at 0
    player_mock.set_position.return_value = False # seek fails initially (buffering)
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    
    # Call load_audiobook. This will set _url_loading to True and trigger load_url_async.
    controller.load_audiobook('playlist.m3u')
    assert controller._url_loading is True
    
    # Mock callbacks
    complete_called = []
    controller.on_load_complete = lambda: complete_called.append(True)
    
    # Set the context as if it was a restored session (so restore_paused is True)
    controller._url_load_context['restore_paused'] = True
    
    # Now simulate async stream ready
    controller._on_url_stream_ready()
    
    # Verify: _url_loading is STILL True because the seek hasn't succeeded
    assert controller._url_loading is True
    # Verify: player.play was NOT called
    player_mock.play.assert_not_called()
    # Verify: UI callback has NOT been called
    assert len(complete_called) == 0
    
    # Simulate a failed seek retry attempt (still buffering)
    player_mock.set_position.return_value = False
    controller._retry_seek_url(45.0, attempt=1)
    assert controller._url_loading is True
    player_mock.play.assert_not_called()
    assert len(complete_called) == 0
    
    # Now simulate seek success
    player_mock.set_position.return_value = True
    player_mock.get_position.return_value = 45.0
    controller._retry_seek_url(45.0, attempt=2)
    
    # Verify: _url_loading is now False
    assert controller._url_loading is False
    # Verify: player.play was NOT called since restore_paused was True
    player_mock.play.assert_not_called()
    # Verify: UI callback WAS called
    assert complete_called == [True]


def test_async_load_plays_after_seek_succeeds(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    conn = sqlite3.connect(tmp_path / "test.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE audiobooks SET current_position = 45.0 WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.get_position.return_value = 0.0
    player_mock.set_position.return_value = False
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    controller.load_audiobook('playlist.m3u')
    
    # Here, restore_paused is False and start_playing will be True (e.g. user selected track)
    controller._url_load_context['restore_paused'] = False
    controller._url_load_context['start_playing'] = True
    
    controller._on_url_stream_ready()
    
    # Verify not playing yet
    player_mock.play.assert_not_called()
    
    # Seek succeeds
    player_mock.set_position.return_value = True
    player_mock.get_position.return_value = 45.0
    controller._retry_seek_url(45.0, attempt=1, start_playing=True)
    
    # Verify: now playing!
    player_mock.play.assert_called_once()
    assert controller._url_loading is False

