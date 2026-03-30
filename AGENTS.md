# Agent Guidelines for SP Audiobook Player

This document provides essential information for AI coding agents working on the SP Audiobook Player codebase.

## Project Overview

SP Audiobook Player is a Windows desktop audiobook player built with PyQt6 and the BASS audio library. It features automatic library scanning, progress tracking, metadata management, and audio processing capabilities.

**Tech Stack:**
- Python 3.8+
- PyQt6 (GUI framework)
- BASS audio library (via ctypes, x64 only)
- SQLite3 (database)
- Mutagen + FFprobe (audio metadata)
- pytest (testing)

**Important:** Module structure is established and should not be changed. Each module has a specific purpose.

## Build, Test & Run Commands

### Running the Application
```bash
python main.py
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_scanner.py

# Run specific test class or function
pytest tests/test_scanner.py::TestParseAudiobookName
pytest tests/test_scanner.py::TestParseAudiobookName::test_parse_variations

# Run with verbose output
pytest -v

# Run with keyword expression
pytest -k "test_parse"

# Exit on first failure
pytest -x
```

### Building Executable
```bash
cd _build_
__build.bat
```
The executable will be created in `_build_/dist/`.

### Installing Dependencies
```bash
pip install -r requirements.txt
```

## Code Style Guidelines

### Import Organization
1. Standard library imports
2. Third-party imports (PyQt6, etc.)
3. Local application imports
4. Blank line between each group

Example:
```python
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import QMainWindow, QWidget
from PyQt6.QtCore import Qt, QTimer

from bass_player import BassPlayer
from database import DatabaseManager
from translations import tr, trf
```

### Type Hints
- Use type hints for function parameters and return values
- Import types from `typing` module: `Dict`, `List`, `Optional`, `Tuple`, `Callable`
- Example:
```python
def get_audiobook_info(self, path: str) -> Optional[Tuple]:
    """Retrieve audiobook information from database"""
    pass
```

### Naming Conventions
- **Classes**: PascalCase (e.g., `AudiobookScanner`, `DatabaseManager`)
- **Functions/Methods**: snake_case (e.g., `load_audiobook`, `save_progress`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DARK_STYLE`, `ROOT_DIR`)
- **Private methods**: Prefix with underscore (e.g., `_load_settings`, `_parse_audiobook_name`)
- **Instance variables**: snake_case (e.g., `self.current_file_index`)
- **QSS Object names**: camelCase (e.g., `filterBtn`, `playBtn`)

### Docstrings
- Use docstrings for classes and public methods
- Keep them concise and descriptive
- Format:
```python
def load_audiobook(self, audiobook_path: str) -> bool:
    """Load audiobook data from the database and prepare the player for playback"""
    pass
```

### Path Handling
- Use `pathlib.Path` for all file system operations
- Get base path with `get_base_path()` utility (handles frozen exe and dev modes)
- Store relative paths in database, resolve to absolute at runtime
- Example:
```python
from pathlib import Path
from utils import get_base_path

script_dir = get_base_path()
config_file = script_dir / 'resources' / 'settings.ini'
```

### Database Operations
- Always use context managers for database connections
- Enable foreign keys: `c.execute("PRAGMA foreign_keys = ON")`
- Use parameterized queries to prevent SQL injection
- Example:
```python
with sqlite3.connect(self.db_file) as conn:
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (path,))
```

### Error Handling
- Use try-except blocks for operations that may fail
- Log errors appropriately
- Fail gracefully without crashing the application
- Example:
```python
try:
    result = self.player.load(file_path)
except Exception as e:
    print(f"Error loading file: {e}")
    return False
```

### Translations
- Use `tr()` for simple translations: `tr("window.title")`
- Use `trf()` for formatted translations: `trf("status.files", count=5)`
- Translation keys use dot notation: `"section.key"`
- Never hardcode user-facing strings
- All UI elements should update text when language changes (implement `update_texts()` method)
- Validate translations with: `python tests/check_translations.py`

### Styling (QSS)
- **All styles centralized in QSS files**: `resources/styles/dark.qss`, `resources/styles/miku.qss`
- **Never use inline styles** in Python code (e.g., `widget.setStyleSheet("color: red")`)
- **Always set object names** for styled widgets: `button.setObjectName("filterBtn")`
- Use `StyleManager.apply_style(app, theme="dark")` to apply themes
- Use `StyleManager.get_theme_property("delegate_title")` to get colors/fonts from QSS
- For dynamic states, use properties:
```python
widget.setProperty("playing", True)
widget.style().unpolish(widget)
widget.style().polish(widget)
```

### Qt-Specific Guidelines
- Connect signals properly: `button.clicked.connect(self.on_button_clicked)`
- Use Qt enums with full path: `Qt.AlignmentFlag.AlignCenter`, `Qt.GlobalColor.black`
- Clean up resources in closeEvent or destructor
- Use `QTimer.singleShot()` for delayed execution

### Testing
- Place all test files in `tests/` directory
- Test file names: `test_*.py`
- Use pytest fixtures from `conftest.py`
- Use `@pytest.mark.parametrize` for multiple test cases
- Mock external dependencies (file system, database)

## Project Structure

```
SPAudiobookPlayer/
├── main.py                 # Application entry point
├── player.py               # Playback controller and player widget
├── bass_player.py          # BASS audio library wrapper
├── library.py              # Library tree widget and scanner thread
├── scanner.py              # Audiobook scanner and metadata parser
├── database.py             # Database operations
├── translations.py         # Internationalization
├── utils.py                # Utility functions
├── styles.py               # Qt stylesheets
├── hotkeys.py              # Global hotkey management
├── settings_dialog.py      # Settings UI
├── bookmarks_dialog.py     # Bookmarks UI
├── metadata_dialog.py      # Metadata editor UI
├── tags_dialog.py          # Tags management UI
├── visualizer.py           # Audio visualizer
├── updater.py              # Auto-update functionality
├── tests/                  # Test files
│   ├── conftest.py         # Pytest fixtures
│   ├── test_scanner.py     # Scanner tests
│   └── test_utils.py       # Utility tests
├── resources/              # Icons, translations, settings
├── data/                   # Database and extracted covers
└── requirements.txt        # Python dependencies
```

## Agent-Specific Rules (from .cursorrules)

- **Always use the 'mcp_serena' toolset** for code analysis, navigation, and editing when available
- **Do not use standard file reading tools** if Serena offers a semantic alternative (e.g. `find_symbol`, `get_symbols_overview`)
- **Create all test scripts and verification scripts strictly in the `tests/` directory**

## Common Patterns

### Loading Icons
```python
from utils import get_icon
icon = get_icon("play", self.icons_dir)
button.setIcon(icon)
```

### Database Queries
```python
audiobook_info = self.db.get_audiobook_info(audiobook_path)
files = self.db.get_audiobook_files(audiobook_id)
self.db.save_progress(audiobook_id, file_index, position)
```

### Playback Control
```python
self.player.load(file_path)
self.player.play()
self.player.pause()
self.player.set_speed(speed_value)  # 10 = 1.0x
self.player.seek(position_seconds)
```

### Saving Progress
```python
# When switching books - DO NOT update timestamp
db.save_progress(..., update_timestamp=False)

# When pausing/stopping - update timestamp
db.save_progress(..., update_timestamp=True)
```

### Safety Patterns

**Unpacking UserRole data safely:**
```python
# WRONG (can crash if fields are added)
id, path, title = item.data(0, Qt.ItemDataRole.UserRole)

# CORRECT
data = item.data(0, Qt.ItemDataRole.UserRole)
if data and len(data) >= 3:
    id, path, title = data[0], data[1], data[2]
```

**Release BASS resources before file operations:**
```python
self.bass_player.stream_free()  # Before deleting/moving files
```

**Check widget existence:**
```python
if hasattr(self, 'widget') and self.widget:
    self.widget.update()
```

## Important Notes

- The application is Windows-only (uses BASS library and Windows-specific APIs)
- Audio files are organized by folder structure (each folder = one audiobook)
- Progress is tracked per audiobook and persisted to SQLite
- The app supports frozen executable mode (PyInstaller) and development mode
- FFmpeg/FFprobe are optional dependencies for enhanced metadata extraction
- All user-facing strings must be translatable (12 languages supported)

## When Making Changes

1. Maintain backward compatibility with existing database schema
2. Test with both development and frozen executable modes
3. Ensure translations are updated if adding new UI strings
4. Add tests for new functionality in `tests/` directory
5. Follow existing code patterns and style conventions
6. Update this document if adding new major features or changing architecture
