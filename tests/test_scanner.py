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



