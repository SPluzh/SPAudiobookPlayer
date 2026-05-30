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
