import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QAction
from main import AudiobookPlayerWindow

def test_status_triangle_toggle_and_rendering(tmp_path):
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    # Mock settings directory structure inside tmp_path
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    # Write a dummy settings.ini
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("[Library]\nshow_status_triangle=True\n")

    # Patch DatabaseManager and BassPlayer, and point paths to tmp_path
    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []
         
        window = AudiobookPlayerWindow()
        
        # Verify default loaded setting is True
        assert window.show_status_triangle is True
        assert window.delegate.show_status_triangle is True
        
        # Verify the menu action exists, is checkable, and is checked
        assert hasattr(window, 'show_status_triangle_action')
        assert isinstance(window.show_status_triangle_action, QAction)
        assert window.show_status_triangle_action.isCheckable() is True
        assert window.show_status_triangle_action.isChecked() is True
        
        # Toggle off
        window.show_status_triangle_action.setChecked(False)
        window.toggle_status_triangle(False)
        assert window.show_status_triangle is False
        assert window.delegate.show_status_triangle is False
        
        # Toggle on
        window.show_status_triangle_action.setChecked(True)
        window.toggle_status_triangle(True)
        assert window.show_status_triangle is True
        assert window.delegate.show_status_triangle is True
