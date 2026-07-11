import os
import sys
import pytest
import tempfile
import sqlite3
from pathlib import Path

# Add project root to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent / "src"))

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


_created_loaders = []
_created_widgets = []
_created_windows = []
_patched_classes = False
_global_app = None

@pytest.fixture(autouse=True, scope="function")
def cleanup_cover_loaders():
    global _patched_classes, _global_app
    
    # Initialize and keep global reference to QApplication so it never gets GC'd during pytest run
    from PyQt6.QtWidgets import QApplication
    if not _global_app:
        _global_app = QApplication.instance() or QApplication([])
        
    if not _patched_classes:
        try:
            from library import CoverLoader, LibraryWidget
            
            # Patch CoverLoader
            original_loader_init = CoverLoader.__init__
            def new_loader_init(self, *args, **kwargs):
                original_loader_init(self, *args, **kwargs)
                _created_loaders.append(self)
            CoverLoader.__init__ = new_loader_init

            # Patch LibraryWidget
            original_widget_init = LibraryWidget.__init__
            def new_widget_init(self, *args, **kwargs):
                original_widget_init(self, *args, **kwargs)
                _created_widgets.append(self)
            LibraryWidget.__init__ = new_widget_init
            
            # Patch AudiobookPlayerWindow if importable
            try:
                from main import AudiobookPlayerWindow
                original_window_init = AudiobookPlayerWindow.__init__
                def new_window_init(self, *args, **kwargs):
                    original_window_init(self, *args, **kwargs)
                    _created_windows.append(self)
                AudiobookPlayerWindow.__init__ = new_window_init
            except ImportError:
                pass

            # Patch QTimer.singleShot to prevent long-delayed timers from running during tests
            from PyQt6.QtCore import QTimer
            original_single_shot = QTimer.singleShot
            def patched_single_shot(msecs, *args, **kwargs):
                if msecs <= 0:
                    original_single_shot(msecs, *args, **kwargs)
                else:
                    # Ignore long-running timers in unit tests to prevent crashes on exit
                    pass
            QTimer.singleShot = patched_single_shot

            _patched_classes = True
        except ImportError:
            pass


    yield

    # 1. Stop all active QTimer attributes on windows and widgets to prevent timeout events
    from PyQt6.QtCore import QTimer
    for window in _created_windows:
        try:
            for attr_name in dir(window):
                try:
                    attr = getattr(window, attr_name)
                    if isinstance(attr, QTimer):
                        attr.stop()
                except Exception:
                    pass
        except Exception:
            pass

    for widget in _created_widgets:
        try:
            for attr_name in dir(widget):
                try:
                    attr = getattr(widget, attr_name)
                    if isinstance(attr, QTimer):
                        attr.stop()
                except Exception:
                    pass
        except Exception:
            pass

    # 2. Clean up loaders first (stop, wait, and disconnect signals)
    print(f"DEBUG TEARDOWN: cleaning up {len(_created_loaders)} loaders", flush=True)
    while _created_loaders:
        loader = _created_loaders.pop()
        try:
            print(f"DEBUG TEARDOWN: stopping loader {loader}", flush=True)
            try:
                loader.cover_loaded.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            if loader.isRunning():
                loader.stop()
                loader.wait()
        except RuntimeError as e:
            print(f"DEBUG TEARDOWN: loader error {e}", flush=True)

    # 3. Process events to drain any pending slot signals while widgets are still alive
    print("DEBUG TEARDOWN: processing events after stopping loaders", flush=True)
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.processEvents()


    # 3. Clean up windows
    print(f"DEBUG TEARDOWN: cleaning up {len(_created_windows)} windows", flush=True)
    while _created_windows:
        window = _created_windows.pop()
        try:
            print(f"DEBUG TEARDOWN: deleting window {window}", flush=True)
            window.close()
            window.deleteLater()
        except RuntimeError as e:
            print(f"DEBUG TEARDOWN: window delete error {e}", flush=True)

    # 4. Clean up widgets
    print(f"DEBUG TEARDOWN: cleaning up {len(_created_widgets)} widgets", flush=True)
    while _created_widgets:
        widget = _created_widgets.pop()
        try:
            print(f"DEBUG TEARDOWN: deleting widget {widget}", flush=True)
            # Break reference cycles
            if hasattr(widget, "delegate") and widget.delegate:
                try:
                    widget.delegate.tree = None
                except (RuntimeError, AttributeError):
                    pass
                widget.delegate = None
            if hasattr(widget, "tree") and widget.tree:
                try:
                    widget.tree.setItemDelegate(None)
                except (RuntimeError, AttributeError):
                    pass
            widget.deleteLater()
        except RuntimeError as e:
            print(f"DEBUG TEARDOWN: widget delete error {e}", flush=True)

    # 5. Process events to finalize widget and window deletions
    print("DEBUG TEARDOWN: processing events to finalize deletions", flush=True)
    if app:
        app.processEvents()

    # 6. Clear StyleManager proxy widgets and property cache
    print("DEBUG TEARDOWN: clearing StyleManager cache", flush=True)
    try:
        from styles import StyleManager
        StyleManager._proxy_widgets.clear()
        StyleManager._property_cache.clear()
    except ImportError:
        pass

    print("DEBUG TEARDOWN: forcing garbage collection", flush=True)
    import gc
    gc.collect()
    print("DEBUG TEARDOWN: completed", flush=True)








