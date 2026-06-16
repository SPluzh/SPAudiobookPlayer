import pytest
from scanner import AudiobookScanner

class TestParseAudiobookName:
    """Tests for _parse_audiobook_name method"""
    
    @pytest.mark.parametrize("folder,expected", [
        # Standard format: Author - Title (Narrator)
        ("Author Name - Book Title (Narrator Name)", 
         ("Author Name", "Book Title", "Narrator Name")),
         
        # Format with square brackets for narrator
        ("John Doe - My Book [Jane Smith]", 
         ("John Doe", "My Book", "Jane Smith")),
         
        # Only title
        ("Just A Title", 
         ("", "Just A Title", "")),
         
        # With technical info in brackets (should be ignored as narrator)
        ("Author - Title (2024)", 
         ("Author", "Title", "")),
        ("Author - Title (128kbps)", 
         ("Author", "Title", "")),
        ("Author - Title (MP3)", 
         ("Author", "Title", "")),
         
        # 'Narrated by' prefixes
        ("Author - Title (читает John)", 
         ("Author", "Title", "John")),
        ("Author - Title (читает Иван)", 
         ("Author", "Title", "Иван")),
         
        # Studio abbreviations removal - requires nested brackets logic in code or single bracket content
        # The code removes studio if it's INSIDE the extracted bracket content and at the end of it.
        # Example: "Author - Title (Narrator (BIG))" -> content="Narrator (BIG)" -> detector finds (BIG) at end
        ("Author - Title (Narrator (BIG))", 
         ("Author", "Title", "Narrator")),
         
        # Multiple dashes
        ("Author - Title - Subtitle (Narrator)", 
         ("Author", "Title - Subtitle", "Narrator")),
         
        # Multiple narrators
        ("Борис Акунин - Азазель (А.Филиппенко, С.Безруков, О.Аросева, И.Безрукова)",
         ("Борис Акунин", "Азазель", "А.Филиппенко, С.Безруков, О.Аросева, И.Безрукова")),
        ("Борис Акунин - Левиафан (А.Клюквин, С.Чонишвили, Д.Мороз, А.Котов)",
         ("Борис Акунин", "Левиафан", "А.Клюквин, С.Чонишвили, Д.Мороз, А.Котов")),
         
        # Mixed narrator and technical info
        ("Author - Title (А.Филиппенко, 2003, 192kbps)",
         ("Author", "Title", "А.Филиппенко")),
         
        # Multiple brackets
        ("Борис Акунин - Азазель (А.Филиппенко, С.Безруков, О.Аросева, И.Безрукова) (2003)",
         ("Борис Акунин", "Азазель", "А.Филиппенко, С.Безруков, О.Аросева, И.Безрукова")),
    ])
    def test_parse_variations(self, folder, expected):
        result = AudiobookScanner._parse_audiobook_name(folder)
        assert result == expected

class TestFixEncoding:
    """Tests for _fix_encoding method"""
    
    def test_empty_input(self):
        assert AudiobookScanner._fix_encoding("") == ""
        assert AudiobookScanner._fix_encoding(None) is None
    
    def test_normal_utf8(self):
        text = "Normal Text 123"
        assert AudiobookScanner._fix_encoding(text) == text
        
    def test_cyrillic_utf8(self):
        text = "Привет мир"
        assert AudiobookScanner._fix_encoding(text) == text
        
    def test_broken_cp1251(self):
        # Create a string that looks like CP1251 interpreted as Latin-1
        # "Привет" in CP1251 bytes interpreted as Latin-1
        original = "Привет"
        broken = original.encode('cp1251').decode('latin-1')
        
        # Verify it's broken
        assert broken != original
        
        # Verify fix works
        fixed = AudiobookScanner._fix_encoding(broken)
        assert fixed == original

class TestTranslation:
    """Tests for tr method"""
    
    def test_simple_translation(self, mock_scanner):
        mock_scanner.translations = {"key": "Value"}
        assert mock_scanner.tr("key") == "Value"
        
    def test_nested_translation(self, mock_scanner):
        mock_scanner.translations = {"section": {"key": "Value"}}
        assert mock_scanner.tr("section.key") == "Value"
        
    def test_missing_key(self, mock_scanner):
        mock_scanner.translations = {}
        assert mock_scanner.tr("missing.key") == "missing.key"
        
    def test_formatting(self, mock_scanner):
        mock_scanner.translations = {"greet": "Hello {name}"}
        assert mock_scanner.tr("greet", name="World") == "Hello World"


class TestScanAndSaveAllCovers:
    """Tests for _scan_and_save_all_covers method"""
    
    @pytest.fixture
    def conn(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE audiobook_covers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audiobook_id INTEGER,
                original_path TEXT,
                cached_path TEXT,
                is_selected INTEGER,
                source_type TEXT
            )
        """)
        conn.commit()
        yield conn
        conn.close()

    def test_scan_and_save_covers_embedded_to_file_transition(self, mock_scanner, conn, temp_dir):
        # Setup temporary directories and files
        audiobook_id = 42
        key = "test_key"
        
        # Mock covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        # Create an existing embedded cover row that is selected
        c = conn.cursor()
        import hashlib
        safe_name = hashlib.md5(key.encode()).hexdigest()
        
        old_cached_path = str(mock_scanner.covers_dir / f"{safe_name}.jpg")
        # Touch the old cached file so Path.exists() is true
        with open(old_cached_path, 'wb') as f:
            f.write(b"fake image data")
            
        c.execute("""
            INSERT INTO audiobook_covers (audiobook_id, original_path, cached_path, is_selected, source_type)
            VALUES (?, ?, ?, ?, ?)
        """, (audiobook_id, None, old_cached_path, 1, 'embedded'))
        conn.commit()
        
        # Now place a new cover.jpg in the audiobook directory
        book_dir = temp_dir / "my_book"
        book_dir.mkdir()
        new_cover_path = book_dir / "cover.jpg"
        with open(new_cover_path, 'wb') as f:
            f.write(b"new fake image data")
            
        # Run scan and save all covers
        mock_scanner._scan_and_save_all_covers(
            conn=conn,
            directory=str(book_dir),
            key=key,
            audiobook_id=audiobook_id,
            selected_cover_cached_path=old_cached_path
        )
        
        # Query covers
        c.execute("SELECT original_path, cached_path, is_selected, source_type FROM audiobook_covers ORDER BY id")
        rows = c.fetchall()
        
        # We expect the newly discovered cover.jpg, which should NOT be selected because the old selected cover was embedded.
        assert len(rows) > 0
        
        cover_jpg_row = None
        for r in rows:
            if r[0] == str(new_cover_path):
                cover_jpg_row = r
                break
                
        assert cover_jpg_row is not None
        # Check that it is NOT selected (is_selected = 0)
        assert cover_jpg_row[2] == 0

    def test_scan_and_save_covers_clears_when_no_covers_exist(self, mock_scanner, conn, temp_dir):
        # Create audiobooks table in connection to verify synchronization
        c = conn.cursor()
        c.execute("""
            CREATE TABLE audiobooks (
                id INTEGER PRIMARY KEY,
                path TEXT,
                cover_path TEXT,
                cached_cover_path TEXT
            )
        """)
        
        audiobook_id = 42
        key = "test_key"
        
        # Insert a book row with a stale cover path and cached cover path
        c.execute("""
            INSERT INTO audiobooks (id, path, cover_path, cached_cover_path)
            VALUES (?, ?, ?, ?)
        """, (audiobook_id, "some_path", "stale_cover.jpg", "stale_cached.jpg"))
        conn.commit()
        
        # Setup empty book directory (no images, no embedded covers)
        book_dir = temp_dir / "empty_book"
        book_dir.mkdir()
        
        # Run scan and save all covers (with no images or embedded covers available)
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        mock_scanner._scan_and_save_all_covers(
            conn=conn,
            directory=str(book_dir),
            key=key,
            audiobook_id=audiobook_id,
            selected_cover_cached_path="stale_cached.jpg"
        )
        
        # Verify audiobook_covers table is empty
        c.execute("SELECT COUNT(*) FROM audiobook_covers WHERE audiobook_id = ?", (audiobook_id,))
        assert c.fetchone()[0] == 0
        
        # Verify that the cover paths in the main audiobooks table have been cleared (synchronized) to NULL
        c.execute("SELECT cover_path, cached_cover_path FROM audiobooks WHERE id = ?", (audiobook_id,))
        row = c.fetchone()
        assert row[0] is None
        assert row[1] is None

    def test_scan_and_save_covers_rescan_embedded_only(self, mock_scanner, conn, temp_dir):
        # Create audiobooks table in connection to verify synchronization
        c = conn.cursor()
        c.execute("""
            CREATE TABLE audiobooks (
                id INTEGER PRIMARY KEY,
                path TEXT,
                cover_path TEXT,
                cached_cover_path TEXT
            )
        """)
        
        audiobook_id = 42
        key = "test_key"
        
        # Mock covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        import hashlib
        safe_name = hashlib.md5(key.encode()).hexdigest()
        old_cached_path = str(mock_scanner.covers_dir / f"{safe_name}.jpg")
        with open(old_cached_path, 'wb') as f:
            f.write(b"fake image data")
            
        # Put book in audiobooks table
        c.execute("""
            INSERT INTO audiobooks (id, path, cover_path, cached_cover_path)
            VALUES (?, ?, ?, ?)
        """, (audiobook_id, key, None, old_cached_path))
        
        # Put cover in audiobook_covers table
        c.execute("""
            INSERT INTO audiobook_covers (audiobook_id, original_path, cached_path, is_selected, source_type)
            VALUES (?, ?, ?, ?, ?)
        """, (audiobook_id, None, old_cached_path, 1, 'embedded'))
        conn.commit()
        
        # Create empty book directory, but with one mp3 file
        book_dir = temp_dir / "embedded_book"
        book_dir.mkdir()
        mp3_file = book_dir / "track.mp3"
        mp3_file.write_bytes(b"some audio data")
        
        # Mock self._get_embedded_image_data to return the fake image bytes
        mock_scanner._get_embedded_image_data = lambda f: b"fake image data"
        
        # Run scan and save all covers
        mock_scanner._scan_and_save_all_covers(
            conn=conn,
            directory=str(book_dir),
            key=key,
            audiobook_id=audiobook_id,
            selected_cover_cached_path=old_cached_path
        )
        
        # Query covers
        c.execute("SELECT original_path, cached_path, is_selected, source_type FROM audiobook_covers")
        rows = c.fetchall()
        
        assert len(rows) == 1
        assert rows[0][2] == 1  # is_selected should be 1!
        
        # Check audiobook
        c.execute("SELECT cover_path, cached_cover_path FROM audiobooks WHERE id = ?", (audiobook_id,))
        row = c.fetchone()
        assert row[1] == old_cached_path

    def test_scan_and_save_covers_merged_rescan_embedded_only(self, mock_scanner, conn, temp_dir):
        # Create audiobooks table in connection to verify synchronization
        c = conn.cursor()
        c.execute("""
            CREATE TABLE audiobooks (
                id INTEGER PRIMARY KEY,
                path TEXT,
                cover_path TEXT,
                cached_cover_path TEXT,
                is_merged INTEGER DEFAULT 0,
                is_playlist INTEGER DEFAULT 0
            )
        """)
        
        audiobook_id = 42
        key = "test_key"
        
        # Mock covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        import hashlib
        safe_name = hashlib.md5(key.encode()).hexdigest()
        old_cached_path = str(mock_scanner.covers_dir / f"{safe_name}.jpg")
        with open(old_cached_path, 'wb') as f:
            f.write(b"fake image data")
            
        # Put book in audiobooks table (marked as merged!)
        c.execute("""
            INSERT INTO audiobooks (id, path, cover_path, cached_cover_path, is_merged)
            VALUES (?, ?, ?, ?, 1)
        """, (audiobook_id, key, None, old_cached_path))
        
        # Put cover in audiobook_covers table
        c.execute("""
            INSERT INTO audiobook_covers (audiobook_id, original_path, cached_path, is_selected, source_type)
            VALUES (?, ?, ?, ?, ?)
        """, (audiobook_id, None, old_cached_path, 1, 'embedded'))
        conn.commit()
        
        # Create a merged directory structure: book_dir/CD1/track.mp3
        book_dir = temp_dir / "merged_book"
        book_dir.mkdir()
        cd_dir = book_dir / "CD1"
        cd_dir.mkdir()
        mp3_file = cd_dir / "track.mp3"
        mp3_file.write_bytes(b"some audio data")
        
        # Mock self._get_embedded_image_data to return the fake image bytes
        mock_scanner._get_embedded_image_data = lambda f: b"fake image data"
        
        # Run scan and save all covers
        mock_scanner._scan_and_save_all_covers(
            conn=conn,
            directory=str(book_dir),
            key=key,
            audiobook_id=audiobook_id,
            selected_cover_cached_path=old_cached_path
        )
        
        # Query covers
        c.execute("SELECT original_path, cached_path, is_selected, source_type FROM audiobook_covers")
        rows = c.fetchall()
        
        assert len(rows) == 1
        assert rows[0][2] == 1  # is_selected should be 1!
        
        # Check audiobook
        c.execute("SELECT cover_path, cached_cover_path FROM audiobooks WHERE id = ?", (audiobook_id,))
        row = c.fetchone()
        assert row[1] == old_cached_path


class TestDetectLanguage:
    """Tests for _detect_language method"""
    
    @pytest.mark.parametrize("folder_name,expected", [
        ("Толстой Лев - Война и мир", "ru"),
        ("Tolkien J.R.R. - The Lord of the Rings", "en"),
        ("The Matrix [English]", "en"),
        ("Абзац 123", "ru"),
        ("", "unknown"),
        (None, "unknown"),
    ])
    def test_detect_language(self, folder_name, expected):
        assert AudiobookScanner._detect_language(folder_name) == expected


class TestParseYears:
    """Tests for _parse_years method"""

    def test_no_years(self):
        written, recorded = AudiobookScanner._parse_years("Book Title", None, None)
        assert written is None
        assert recorded is None

    def test_single_year_pre_2000_no_keyword(self):
        # Default behavior for single old year without keyword: year_written
        written, recorded = AudiobookScanner._parse_years("Pushkin - Evgeniy Onegin (1833)", None, None)
        assert written == "1833"
        assert recorded is None

    def test_single_year_post_2000_no_keyword(self):
        # Single recent year: year_recorded
        written, recorded = AudiobookScanner._parse_years("Some Author - Modern Book (2015)", None, None)
        assert written is None
        assert recorded == "2015"

    def test_single_year_pre_2000_with_keyword(self):
        # Single old year but contains keyword like "чит" or "mp3": year_recorded
        written, recorded = AudiobookScanner._parse_years("Old Book [чит. Клюквин, 1995, MP3]", None, None)
        assert written is None
        assert recorded == "1995"

    def test_multiple_years(self):
        # Multiple years: smallest is written, largest is recorded
        written, recorded = AudiobookScanner._parse_years("Author - Book [Narrator, 1978, 2008]", None, None)
        assert written == "1978"
        assert recorded == "2008"

    def test_multiple_years_with_tags(self):
        # Combine folder and tags, smallest is written, largest is recorded
        written, recorded = AudiobookScanner._parse_years("Author - Book [1999]", "2012", "1954")
        # Years found: 1999, 2012, 1954
        assert written == "1954"
        assert recorded == "2012"


class TestScannerExecution:
    """Tests to verify full scanner execution does not crash during database inserts"""

    def test_scan_audiobook_folder_inserts_successfully(self, mock_scanner, temp_dir):
        # Create an audiobook folder
        book_dir = temp_dir / "Budzhold - Barrayar"
        book_dir.mkdir()
        
        # Create a mock mp3 file
        mp3_file = book_dir / "01.mp3"
        mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
        
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        def mock_extract(directory, files):
            return {
                'author': 'Budzhold',
                'title': 'Barrayar',
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
            # Execute scan
            mock_scanner.scan_directory(str(temp_dir))
            
            # Verify database entry was inserted
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            c.execute("SELECT path, author, title, language, year_recorded FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            assert "Barrayar" in row[0]
            assert row[1] == "Budzhold"
            assert row[2] == "Barrayar"
            assert row[3] in ("en", "ru")
            assert row[4] == "2005"
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

    def test_process_standalone_file_inserts_language_and_years(self, mock_scanner, temp_dir):
        # Create a standalone audio file in root
        standalone_file = temp_dir / "Лев Толстой - Анна Каренина [1978, 2010].mp3"
        standalone_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)

        import sqlite3
        conn = sqlite3.connect(mock_scanner.db_file)
        
        # Initialize temp_state table which _process_standalone_file expects
        c = conn.cursor()
        c.execute("CREATE TABLE temp_state (path TEXT, listened_duration REAL, progress_percent INTEGER, current_file_index INTEGER, current_position REAL, playback_speed REAL, is_started INTEGER, is_completed INTEGER)")
        conn.commit()

        # Mock _extract_file_tags, _analyze_file
        original_extract_tags = mock_scanner._extract_file_tags
        original_analyze = mock_scanner._analyze_file

        mock_scanner._extract_file_tags = lambda path: {
            'author': 'Лев Толстой',
            'title': 'Анна Каренина',
            'album': '',
            'year': '2010',
            'genre': '',
            'comment': '',
            'narrator': '',
            'track': None
        }

        mock_scanner._analyze_file = lambda path, verbose=False: {
            'duration': 200.0,
            'bitrate': 128000,
            'codec': 'mp3',
            'container': 'mp3',
            'is_vbr': False
        }

        try:
            mock_scanner._process_standalone_file(standalone_file, temp_dir, conn)
            
            # Verify database entry has language and years
            c.execute("SELECT path, author, title, language, year_written, year_recorded FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            assert "Анна Каренина" in row[0]
            assert row[1] == "Лев Толстой"
            assert row[2] == "Анна Каренина"
            assert row[3] == "ru"  # Russian language detected
            assert row[4] == "1978"
            assert row[5] == "2010"
        finally:
            mock_scanner._extract_file_tags = original_extract_tags
            mock_scanner._analyze_file = original_analyze
            conn.close()


class TestScanProgressLogging:
    """Tests to verify scanning progress logging outputs correct format and data"""

    def test_scan_progress_logging(self, mock_scanner, temp_dir):
        # Create multiple audiobook folders
        for name in ["Book A", "Book B"]:
            book_dir = temp_dir / name
            book_dir.mkdir()
            mp3_file = book_dir / "01.mp3"
            mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
            
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'Title', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        logged_lines = []
        def mock_log(message, end='\n'):
            logged_lines.append((message, end))
            
        mock_scanner._log = mock_log
        
        try:
            mock_scanner.scan_directory(str(temp_dir))
            
            # Check that we logged progress
            progress_logs = [m for m, e in logged_lines if "\r" in m and "% | " in m]
            assert len(progress_logs) > 0
            
            # Verify structure and format: "percent% | [current/total] Book Title"
            # It should have e.g., "50% | [1/2] Book A" or "100% | [2/2] Book B"
            assert any("50% | " in m for m in progress_logs)
            assert any("100% | " in m for m in progress_logs)
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

    def test_log_progress_clearing(self, mock_scanner, capsys):
        mock_scanner._last_was_progress = False
        
        # Log a progress line
        mock_scanner._log("\r50% | processing", end="")
        captured = capsys.readouterr()
        assert captured.out == "\r50% | processing"
        assert mock_scanner._last_was_progress is True
        
        # Log a standard line (should trigger clearing of progress line)
        mock_scanner._log("Finished processing book")
        captured = capsys.readouterr()
        # Should contain the clear sequence followed by the new log message
        assert "\r" + " " * 90 + "\r" in captured.out
        assert "Finished processing book\n" in captured.out
        assert mock_scanner._last_was_progress is False


class TestSubfolderScanning:
    """Tests to verify scanning of specific subfolders"""

    def test_scan_only_specified_subfolder(self, mock_scanner, temp_dir):
        # Create two audiobook folders
        book_a_dir = temp_dir / "Book A"
        book_a_dir.mkdir()
        (book_a_dir / "01.mp3").write_bytes(b"\xFF\xFB" + b"\x00" * 100)

        book_b_dir = temp_dir / "Book B"
        book_b_dir.mkdir()
        (book_b_dir / "01.mp3").write_bytes(b"\xFF\xFB" + b"\x00" * 100)

        from pathlib import Path
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': Path(dir).name, 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}

        try:
            # 1. Full scan to populate database
            mock_scanner.scan_directory(str(temp_dir))

            # Verify both are inserted and available
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            c.execute("SELECT path, is_available FROM audiobooks WHERE is_folder = 0 ORDER BY path")
            rows = c.fetchall()
            assert len(rows) == 2
            assert rows[0] == ("Book A", 1)
            assert rows[1] == ("Book B", 1)

            # 2. Delete Book A directory from disk, but keep Book B directory
            import shutil
            shutil.rmtree(book_a_dir)

            # Run scan targeting ONLY Book A subfolder
            mock_scanner.scan_directory(str(temp_dir), subfolder_path="Book A")

            # Verify Book A is now unavailable (is_available = 0), but Book B is still available (is_available = 1)
            c.execute("SELECT path, is_available FROM audiobooks WHERE is_folder = 0 ORDER BY path")
            rows = c.fetchall()
            assert len(rows) == 2
            assert rows[0] == ("Book A", 0)
            assert rows[1] == ("Book B", 1)
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze





class TestCoverInheritance:
    """Tests for cover inheritance from parent folders"""

    def test_inherit_parent_cover(self, mock_scanner, temp_dir):
        # Enable cover inheritance for this test
        mock_scanner.inherit_parent_cover = True
        
        # 1. Create a parent folder with a cover image
        parent_dir = temp_dir / "Parent Book"
        parent_dir.mkdir()
        parent_cover = parent_dir / "cover.jpg"
        parent_cover.write_bytes(b"parent cover image data")
        
        # 2. Create a subfolder with no cover image but containing an audio file
        sub_dir = parent_dir / "CD 1"
        sub_dir.mkdir()
        mp3_file = sub_dir / "01.mp3"
        mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
        
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'CD 1', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        # Set covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        try:
            # Run scanner on parent directory
            mock_scanner.scan_directory(str(temp_dir))
            
            # Verify database records
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            
            # Select path and covers of the scanned items
            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0 ORDER BY path")
            rows = c.fetchall()
            
            # We expect CD 1 to have cover_path pointing to parent_dir/cover.jpg
            # since CD 1 doesn't have its own cover.
            assert len(rows) == 1
            path, cover_path, cached_path = rows[0]
            
            assert "CD 1" in path
            assert cover_path == str(parent_cover)
            assert cached_path is not None
            
            # Verify that the inherited cover was added to audiobook_covers as selected
            c.execute("SELECT original_path, is_selected FROM audiobook_covers WHERE audiobook_id = 1")
            covers = c.fetchall()
            assert len(covers) == 1
            assert covers[0][0] == str(parent_cover)
            assert covers[0][1] == 1
            
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

    def test_do_not_inherit_when_own_cover_exists(self, mock_scanner, temp_dir):
        # Enable cover inheritance for this test
        mock_scanner.inherit_parent_cover = True
        
        # 1. Create a parent folder with a cover image
        parent_dir = temp_dir / "Parent Book"
        parent_dir.mkdir()
        parent_cover = parent_dir / "cover.jpg"
        parent_cover.write_bytes(b"parent cover image data")
        
        # 2. Create a subfolder with its own cover image and containing an audio file
        sub_dir = parent_dir / "CD 1"
        sub_dir.mkdir()
        sub_cover = sub_dir / "cover.jpg"
        sub_cover.write_bytes(b"subfolder cover image data")
        
        mp3_file = sub_dir / "01.mp3"
        mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
        
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'CD 1', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        # Set covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        try:
            # Run scanner on parent directory
            mock_scanner.scan_directory(str(temp_dir))
            
            # Verify database records
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            
            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0 ORDER BY path")
            rows = c.fetchall()
            
            # We expect CD 1 to have cover_path pointing to sub_cover, not parent_cover
            assert len(rows) == 1
            path, cover_path, cached_path = rows[0]
            
            assert "CD 1" in path
            assert cover_path == str(sub_cover)
            
            # Verify covers in audiobook_covers
            c.execute("SELECT original_path, is_selected FROM audiobook_covers WHERE audiobook_id = 1")
            covers = c.fetchall()
            # It might find sub_cover (and parent_cover could be found via recursion or not depending on directory scanning boundaries,
            # but sub_cover must be the selected one)
            selected_covers = [cov[0] for cov in covers if cov[1] == 1]
            assert len(selected_covers) == 1
            assert selected_covers[0] == str(sub_cover)
            
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

    def test_do_not_inherit_from_root(self, mock_scanner, temp_dir):
        # 1. Create a cover image directly in the root library directory
        root_cover = temp_dir / "cover.jpg"
        root_cover.write_bytes(b"root cover image data")
        
        # 2. Create a book folder directly under root with no cover but with an audio file
        book_dir = temp_dir / "Book directly in root"
        book_dir.mkdir()
        mp3_file = book_dir / "01.mp3"
        mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
        
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'Book directly in root', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        try:
            # Run scanner
            mock_scanner.scan_directory(str(temp_dir))
            
            # Verify database records
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            
            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            rows = c.fetchall()
            
            # The book directly under root should NOT have inherited the root folder's cover.
            assert len(rows) == 1
            path, cover_path, cached_path = rows[0]
            assert cover_path is None or cover_path == ""
            assert cached_path is None or cached_path == ""
            
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

    def test_do_not_inherit_when_inherit_parent_cover_disabled(self, mock_scanner, temp_dir):
        # Disable parent cover inheritance
        mock_scanner.inherit_parent_cover = False
        
        # 1. Create a parent folder with a cover image
        parent_dir = temp_dir / "Parent Book"
        parent_dir.mkdir()
        parent_cover = parent_dir / "cover.jpg"
        parent_cover.write_bytes(b"parent cover image data")
        
        # 2. Create a subfolder with no cover image but containing an audio file
        sub_dir = parent_dir / "CD 1"
        sub_dir.mkdir()
        mp3_file = sub_dir / "01.mp3"
        mp3_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
        
        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'CD 1', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()
        
        try:
            # Run scanner
            mock_scanner.scan_directory(str(temp_dir))
            
            # Verify database records
            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()
            
            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            rows = c.fetchall()
            
            # We expect CD 1 to have NO cover_path since inheritance is disabled
            assert len(rows) == 1
            path, cover_path, cached_path = rows[0]
            assert cover_path is None or cover_path == ""
            assert cached_path is None or cached_path == ""
            
            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze


class TestM3UCoverChange:
    """Tests that M3U playlist scanner detects cover addition/removal on rescanning"""

    def test_m3u_cover_addition_and_removal(self, mock_scanner, temp_dir):
        # 1. Create playlist directory
        book_dir = temp_dir / "M3U Book"
        book_dir.mkdir()

        # Create mock audio file
        audio_file = book_dir / "track.mp3"
        audio_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)

        # Create M3U playlist pointing to it
        m3u_file = book_dir / "playlist.m3u"
        m3u_file.write_text("track.mp3\n", encoding='utf-8')

        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'M3U Book', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        # Set covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()

        try:
            # First Scan: No cover exists
            mock_scanner.scan_directory(str(temp_dir))

            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()

            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            assert row[1] is None
            assert row[2] is None

            # 2. Add a cover file to the playlist directory
            cover_file = book_dir / "cover.jpg"
            cover_file.write_bytes(b"cover image data")

            # Force state update for file-system (though on many systems mtime is automatic, writing to cover doesn't change m3u itself)
            # Since we included cover files in state info list, even if m3u file has same mtime/size,
            # the new cover file will add a new entry to the state list, causing hash to change.
            mock_scanner.scan_directory(str(temp_dir))

            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            assert row[1] == str(cover_file)
            assert row[2] is not None

            # Verify covers table is populated
            c.execute("SELECT COUNT(*) FROM audiobook_covers WHERE audiobook_id = 1")
            assert c.fetchone()[0] == 1

            # 3. Delete the cover file
            cover_file.unlink()

            # Rescan again
            mock_scanner.scan_directory(str(temp_dir))

            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            assert row[1] is None
            assert row[2] is None

            # Verify covers table is cleared
            c.execute("SELECT COUNT(*) FROM audiobook_covers WHERE audiobook_id = 1")
            assert c.fetchone()[0] == 0

            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze


class TestCoverForcedUpdateOnRescan:
    """Tests that cover files are updated/overwritten when a rescan is triggered"""

    def test_cover_updated_on_rescan(self, mock_scanner, temp_dir):
        # 1. Create book directory
        book_dir = temp_dir / "Rescan Cover Book"
        book_dir.mkdir()

        # Create mock audio file
        audio_file = book_dir / "track.mp3"
        audio_file.write_bytes(b"\xFF\xFB" + b"\x00" * 100)

        # Create initial cover.jpg
        cover_file = book_dir / "cover.jpg"
        cover_file.write_bytes(b"initial cover content")

        import unittest.mock
        original_extract = mock_scanner._extract_metadata
        original_analyze = mock_scanner._analyze_file_fast
        
        mock_scanner._extract_metadata = lambda dir, files: {'author': 'Auth', 'title': 'Rescan Cover Book', 'narrator': ''}
        mock_scanner._analyze_file_fast = lambda path, verbose=False: {'duration': 10.0, 'bitrate': 128, 'codec': 'mp3', 'container': 'mp3', 'is_vbr': False}
        
        # Set covers_dir
        mock_scanner.covers_dir = temp_dir / "covers"
        mock_scanner.covers_dir.mkdir()

        try:
            # First Scan: initial cover cached
            mock_scanner.scan_directory(str(temp_dir))

            import sqlite3
            conn = sqlite3.connect(mock_scanner.db_file)
            c = conn.cursor()

            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            cached_path_1 = row[2]
            assert cached_path_1 is not None
            
            # Read cached file to confirm initial content
            with open(cached_path_1, 'rb') as f:
                content_1 = f.read()
            assert content_1 == b"initial cover content"

            # 2. Modify cover.jpg to have different content
            cover_file.write_bytes(b"updated cover content")

            # Force state update: rescan should be triggered because state_hash changes due to cover.jpg change
            mock_scanner.scan_directory(str(temp_dir))

            c.execute("SELECT path, cover_path, cached_cover_path FROM audiobooks WHERE is_folder = 0")
            row = c.fetchone()
            assert row is not None
            cached_path_2 = row[2]
            
            # Cached path should remain the same (we overwrite the existing file)
            assert cached_path_2 == cached_path_1
            
            # Read cached file to confirm it has been updated/overwritten with the new content
            with open(cached_path_2, 'rb') as f:
                content_2 = f.read()
            assert content_2 == b"updated cover content"

            conn.close()
        finally:
            mock_scanner._extract_metadata = original_extract
            mock_scanner._analyze_file_fast = original_analyze

