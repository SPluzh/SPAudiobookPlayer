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
