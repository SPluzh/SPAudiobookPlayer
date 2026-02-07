import os
import sys
import pytest
import tempfile
import sqlite3
from pathlib import Path

# Add project root to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent))

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary database file."""
    db_path = temp_dir / "test.db"
    yield db_path
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass

@pytest.fixture
def mock_scanner(temp_db, temp_dir):
    """Create an AudiobookScanner instance with temporary paths."""
    from scanner import AudiobookScanner
    
    # Create a minimal settings.ini
    config_path = temp_dir / "settings.ini"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(f"""[Paths]
library={temp_dir}
database={temp_db}
ffprobe=ffprobe
""")
    
    # Mock the _load_translations method to avoid needing actual translation files
    original_load = AudiobookScanner._load_translations
    def mock_load(self):
        self.translations = {}
    
    AudiobookScanner._load_translations = mock_load
    
    scanner = AudiobookScanner(str(config_path))
    
    yield scanner
    
    # Restore method
    AudiobookScanner._load_translations = original_load
