import pytest
import sqlite3
from pathlib import Path
from scanner import AudiobookScanner

def _create_test_schema(conn):
    """Create minimal database schema for M3U tests"""
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE audiobooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            parent_path TEXT DEFAULT '',
            name TEXT, author TEXT, title TEXT, narrator TEXT,
            language TEXT,
            year_written TEXT,
            year_recorded TEXT,
            file_count INTEGER DEFAULT 0,
            duration REAL DEFAULT 0,
            is_folder INTEGER DEFAULT 0,
            is_playlist INTEGER DEFAULT 0,
            playlist_path TEXT,
            cover_path TEXT, cached_cover_path TEXT,
            state_hash TEXT,
            listened_duration REAL DEFAULT 0,
            progress_percent REAL DEFAULT 0,
            current_file_index INTEGER DEFAULT 0,
            current_position REAL DEFAULT 0,
            playback_speed REAL DEFAULT 1.0,
            is_started INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            codec TEXT,
            bitrate_min INTEGER,
            bitrate_max INTEGER,
            bitrate_mode TEXT,
            container TEXT,
            total_size INTEGER DEFAULT 0,
            time_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE audiobook_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audiobook_id INTEGER,
            file_path TEXT,
            file_name TEXT,
            track_number INTEGER,
            duration REAL DEFAULT 0,
            start_offset REAL DEFAULT 0,
            tag_title TEXT, tag_artist TEXT, tag_album TEXT,
            tag_genre TEXT, tag_comment TEXT,
            is_url INTEGER DEFAULT 0
        );
        CREATE TABLE audiobook_covers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audiobook_id INTEGER,
            original_path TEXT,
            cached_path TEXT,
            is_selected INTEGER DEFAULT 0,
            source_type TEXT
        );
    """)
    conn.commit()

def test_parse_m3u_local_files(mock_scanner, temp_dir):
    """parse_m3u_file correctly extracts local tracks"""
    # Create mock mp3 file
    mp3 = temp_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
    
    m3u = temp_dir / "playlist.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        "#EXTINF:99,Track 1\n"
        "01.mp3\n",
        encoding="utf-8"
    )
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 1
    assert entries[0]['is_url'] is False
    assert entries[0]['title'] == "Track 1"
    assert entries[0]['duration'] == 99
    assert Path(entries[0]['path']).exists()

def test_parse_m3u_url_entries(mock_scanner, temp_dir):
    """parse_m3u_file correctly parses URL entries"""
    m3u = temp_dir / "stream.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        "#EXTINF:3600,Radio Stream\n"
        "https://example.com/stream.mp3\n"
        "#EXTINF:-1,Live\n"
        "http://example.com/live\n",
        encoding="utf-8"
    )
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 2
    assert all(e['is_url'] for e in entries)
    assert entries[0]['duration'] == 3600
    assert entries[1]['duration'] == 0

def test_parse_m3u_cp1251_encoding(mock_scanner, temp_dir):
    """parse_m3u_file correctly parses CP1251 encoded files"""
    mp3 = temp_dir / "трек.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
    
    content = "#EXTM3U\n#EXTINF:100,Кириллика\nтрек.mp3\n"
    m3u = temp_dir / "playlist.m3u"
    m3u.write_bytes(content.encode("cp1251"))
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 1
    assert entries[0]['title'] == "Кириллика"

def test_save_playlist_as_book_single(mock_scanner, temp_dir):
    """Saving a single playlist within a directory configures a playlist audiobook correctly"""
    book_dir = temp_dir / "Author - Book [Narrator]"
    book_dir.mkdir()
    mp3 = book_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    m3u = book_dir / "playlist.m3u"
    m3u.write_text("#EXTM3U\n#EXTINF:10,Track\n01.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_test_schema(conn)
    
    mock_scanner._save_playlist_as_book(
        m3u_path=m3u,
        book_path="Author - Book [Narrator]",
        parent_path="",
        name="Author - Book [Narrator]",
        root=temp_dir,
        conn=conn
    )
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT * FROM audiobooks WHERE is_playlist = 1")
    row = c.fetchone()
    
    assert row is not None
    assert row['path'] == "Author - Book [Narrator]"
    assert row['is_playlist'] == 1
    assert row['playlist_path'] == str(Path("Author - Book [Narrator]/playlist.m3u"))
    assert row['file_count'] == 1
    assert row['author'] == "Author"
    assert row['narrator'] == "Narrator"
    
    c.execute("SELECT * FROM audiobook_files WHERE audiobook_id = ?", (row['id'],))
    files = c.fetchall()
    assert len(files) == 1
    assert files[0]['is_url'] == 0
    assert files[0]['track_number'] == 1
    conn.close()

def test_save_playlist_idempotent(mock_scanner, temp_dir):
    """Subsequent scanning runs do not duplicate rows or increment addition dates"""
    book_dir = temp_dir / "Book"
    book_dir.mkdir()
    mp3 = book_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    m3u = book_dir / "book.m3u"
    m3u.write_text("#EXTM3U\n01.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    
    kwargs = dict(m3u_path=m3u, book_path="Book", parent_path="",
                  name="Book", root=temp_dir, conn=conn)
    
    mock_scanner._save_playlist_as_book(**kwargs)
    conn.commit()
    mock_scanner._save_playlist_as_book(**kwargs)
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_playlist = 1")
    assert c.fetchone()[0] == 1
    conn.close()

def test_process_playlist_multiple_m3u(mock_scanner, temp_dir):
    """Multiple M3U files in a single folder result in multiple independent audiobook instances"""
    folder = temp_dir / "Collection"
    folder.mkdir()
    mp3 = folder / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    
    for name in ["Book1", "Book2"]:
        m3u = folder / f"{name}.m3u"
        m3u.write_text("#EXTM3U\n01.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    
    m3u_files = sorted(folder.glob("*.m3u"))
    mock_scanner._process_playlist_in_folder(
        folder=folder, root=temp_dir,
        m3u_files=m3u_files, conn=conn,
        save_folder_callback=lambda p: None
    )
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT path, parent_path FROM audiobooks WHERE is_playlist = 1 ORDER BY path")
    rows = c.fetchall()
    
    assert len(rows) == 2
    for row in rows:
        assert row[0].endswith(".m3u")
        assert "Collection" in row[1]
    conn.close()

def test_process_playlist_single_non_generic_with_subdirs(mock_scanner, temp_dir):
    """A single non-generic M3U file in a directory with subdirectories is processed under its file path"""
    folder = temp_dir / "Category"
    folder.mkdir()
    
    # Subdirectory
    sub = folder / "Subfolder"
    sub.mkdir()
    
    m3u = folder / "specific_book.m3u"
    m3u.write_text("#EXTM3U\nhttps://example.com/stream.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    
    m3u_files = [m3u]
    mock_scanner._process_playlist_in_folder(
        folder=folder, root=temp_dir,
        m3u_files=m3u_files, conn=conn,
        save_folder_callback=lambda p: None
    )
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT path, name, is_playlist FROM audiobooks")
    rows = c.fetchall()
    
    assert len(rows) == 1
    assert rows[0][0] == str(Path("Category/specific_book.m3u"))
    assert rows[0][1] == "specific_book"
    assert rows[0][2] == 1
    conn.close()
