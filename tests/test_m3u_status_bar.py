import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from database import DatabaseManager, init_database
from player import PlaybackController
from main import AudiobookPlayerWindow

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

def test_playback_controller_status_emissions(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    player_mock = MagicMock()
    player_mock.initialized = True
    player_mock.get_position.return_value = 0.0
    player_mock.speed_pos = 10
    
    controller = PlaybackController(player_mock, db)
    
    emitted_statuses = []
    controller.on_status_update = lambda msg: emitted_statuses.append(msg)
    
    # 1. Loading the playlist
    controller.load_audiobook('playlist.m3u')
    assert len(emitted_statuses) > 0
    assert "playlist" in emitted_statuses[0].lower() or "загрузка" in emitted_statuses[0].lower()
    
    # Reset emitted statuses for stream ready phase
    emitted_statuses.clear()
    
    # Set saved position to trigger seeking status
    controller._url_load_context['saved_position'] = 50.0
    controller._on_url_stream_ready()
    
    # 2. Restoring position
    assert len(emitted_statuses) > 0
    assert any("restoring" in s.lower() or "восстановление" in s.lower() for s in emitted_statuses)
    
    # 3. Seeking retry attempts
    emitted_statuses.clear()
    player_mock.set_position.return_value = False
    controller._retry_seek_url(50.0, attempt=2)
    assert len(emitted_statuses) > 0
    assert any("seeking" in s.lower() or "попытка 2" in s.lower() or "attempt" in s.lower() for s in emitted_statuses)

def test_main_window_status_routing():
    # Test checking that _on_playback_status emits status_requested
    main_window_mock = MagicMock()
    main_window_mock.status_requested = MagicMock()
    
    # Call the method statically passing the mock
    AudiobookPlayerWindow._on_playback_status(main_window_mock, "Test status message")
    
    # Verify that the signal was emitted
    main_window_mock.status_requested.emit.assert_called_once_with("Test status message")

def test_network_connection_retries(tmp_path):
    db, book_id = setup_test_db(tmp_path)
    
    player_mock = MagicMock()
    player_mock.initialized = True
    
    controller = PlaybackController(player_mock, db)
    controller.load_audiobook('playlist.m3u')
    
    # Reset loading state for unit testing error path
    controller._url_loading = True
    
    emitted_statuses = []
    controller.on_status_update = lambda msg: emitted_statuses.append(msg)
    
    load_errors = []
    controller.on_load_error = lambda url: load_errors.append(url)
    
    # Mock QTimer.singleShot to execute immediately so we don't have to wait or block
    with patch('PyQt6.QtCore.QTimer.singleShot') as mock_timer:
        # Trigger stream connection error
        controller._on_url_stream_error()
        
        # Verify a retry timer was scheduled
        mock_timer.assert_called_once()
        
        # Verify the connecting retry status message was emitted
        assert len(emitted_statuses) > 0
        assert "attempt 1" in emitted_statuses[0].lower() or "попытка 1" in emitted_statuses[0].lower()
        
        # Verify context now has connect_attempt = 2
        assert controller._url_load_context.get('connect_attempt') == 2
        
        # Run the timer callback
        do_retry_cb = mock_timer.call_args[0][1]
        do_retry_cb()
        
        # Verify it started a new load attempt
        player_mock.load_url_async.assert_called()

    # Now test reaching max attempts
    controller._url_load_context['connect_attempt'] = 5
    controller._on_url_stream_error()
    
    # Verify we did not schedule another retry, but failed completely
    assert controller._url_loading is False
    assert len(load_errors) == 1

