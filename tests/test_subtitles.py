import pytest
import sqlite3
from pathlib import Path
from subtitle_panel import parse_srt, SubtitlePanel
from PyQt6.QtWidgets import QApplication

def test_srt_parser(temp_dir):
    """Verify that SRT timestamps and text are correctly parsed"""
    srt_content = """1
00:00:01,500 --> 00:00:04,200
Hello World!

2
00:00:05,000 --> 00:00:07,150
Second subtitle line.
Multiple words.
"""
    srt_file = temp_dir / "test_parser.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    items = parse_srt(str(srt_file))
    assert len(items) == 2
    
    # Check first item
    assert items[0].start == 1.5
    assert items[0].end == 4.2
    assert items[0].text == "Hello World!"
    
    # Check second item
    assert items[1].start == 5.0
    assert items[1].end == 7.15
    assert items[1].text == "Second subtitle line.\nMultiple words."

def test_subtitle_panel_loading_and_update(temp_dir):
    """Verify that SubtitlePanel loads SRT files and updates active line highlight based on time"""
    # Write a temporary SRT file
    srt_file = temp_dir / "test.srt"
    srt_file.write_text("""1
00:00:01,000 --> 00:00:03,000
Line A

2
00:00:04,000 --> 00:00:06,000
Line B
""", encoding="utf-8")
    
    # Create SubtitlePanel
    panel = SubtitlePanel()
    
    # Initially empty
    assert panel.browser.toPlainText() == ""
    
    # Load SRT
    panel.load_srt(str(srt_file))
    assert "Line A" in panel.browser.toPlainText()
    assert "Line B" in panel.browser.toPlainText()
    
    # Test position 0.0 (no active subtitles)
    panel.update_position(0.0)
    
    # Test position 2.0 (should highlight Line A)
    panel.update_position(2.0)
    
    # Test position 3.5 (no active subtitles)
    panel.update_position(3.5)
    
    # Test position 5.0 (should highlight Line B)
    panel.update_position(5.0)
    
    # Clear panel
    panel.clear()
    assert panel.browser.toPlainText() == ""

def test_database_srt_path_migration(temp_db):
    """Verify database initialization creates the srt_path column on audiobook_files"""
    from database import DatabaseManager
    db = DatabaseManager(temp_db)
    
    # Verify srt_path column exists
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(audiobook_files)")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    
    assert "srt_path" in columns

def test_scanner_subtitle_auto_detection(mock_scanner, temp_dir):
    """Verify scanner automatically binds local SRT files to matching audio files"""
    # Create mock book directory
    book_dir = temp_dir / "Test Author - Test Book"
    book_dir.mkdir()
    
    # Create audio track
    audio_file = book_dir / "01_intro.mp3"
    audio_file.write_bytes(b"\xFF\xFB" + b"\x00" * 1000) # dummy mp3
    
    # Create matching srt file next to it
    srt_file = book_dir / "01_intro.srt"
    srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello!", encoding="utf-8")
    
    # Mock scanner's metadata and file analysis methods to handle dummy file
    original_extract = mock_scanner._extract_metadata
    original_analyze = mock_scanner._analyze_file_fast
    
    def mock_extract(directory, files):
        return {
            'author': 'Test Author',
            'title': 'Test Book',
            'narrator': '',
            'year': '2005'
        }
        
    def mock_analyze(path, verbose=False):
        return {
            'duration': 100.0,
            'bitrate': 128,
            'codec': 'mp3',
            'container': 'mp3',
            'is_vbr': False,
            'needs_ffprobe': False
        }
        
    mock_scanner._extract_metadata = mock_extract
    mock_scanner._analyze_file_fast = mock_analyze
    
    try:
        # Run mock scanner
        mock_scanner.scan_directory(str(temp_dir))
        
        # Verify in DB that files record was populated with correct relative srt_path
        conn = sqlite3.connect(mock_scanner.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM audiobook_files")
        files = cursor.fetchall()
        conn.close()
        
        assert len(files) == 1
        rel_audio_path = str(Path("Test Author - Test Book") / "01_intro.mp3")
        rel_srt_path = str(Path("Test Author - Test Book") / "01_intro.srt")
        
        assert files[0]["file_path"] == rel_audio_path
        assert files[0]["srt_path"] == rel_srt_path
    finally:
        mock_scanner._extract_metadata = original_extract
        mock_scanner._analyze_file_fast = original_analyze

def test_subtitle_font_size_zoom():
    """Verify font size increase/decrease, clamping, and signal emission on SubtitlePanel"""
    panel = SubtitlePanel()
    
    # Check default font size
    assert panel.font_size == 15
    
    # Test setting font size
    panel.font_size = 20
    assert panel.font_size == 20
    
    # Test signal emission on font size change
    emitted_sizes = []
    panel.font_size_changed.connect(emitted_sizes.append)
    
    # Increase font size (zoom in button)
    panel.increase_font_size()
    assert panel.font_size == 21
    assert emitted_sizes == [21]
    
    # Decrease font size (zoom out button)
    panel.decrease_font_size()
    assert panel.font_size == 20
    assert emitted_sizes == [21, 20]
    
    # Test clamping limits (10 to 40)
    panel.font_size = 40
    panel.increase_font_size()
    assert panel.font_size == 40  # should not exceed 40
    
    panel.font_size = 10
    panel.decrease_font_size()
    assert panel.font_size == 10  # should not go below 10

def test_subtitle_translation_toggle():
    """Verify that translation_on_hover attribute, toggle button, and signals work correctly"""
    panel = SubtitlePanel()
    
    # Check default state
    assert panel.translation_on_hover is True
    assert panel.btn_translation_toggle.isChecked() is True
    assert panel.browser.translation_on_hover is True
    
    # Listen to signal
    emitted_states = []
    panel.translation_on_hover_changed.connect(emitted_states.append)
    
    # Simulate clicking toggle button to turn off hover translation
    panel.btn_translation_toggle.click()
    assert panel.translation_on_hover is False
    assert panel.btn_translation_toggle.isChecked() is False
    assert panel.browser.translation_on_hover is False
    assert emitted_states == [False]
    
    # Toggle it back on
    panel.btn_translation_toggle.click()
    assert panel.translation_on_hover is True
    assert panel.btn_translation_toggle.isChecked() is True
    assert panel.browser.translation_on_hover is True
    assert emitted_states == [False, True]
