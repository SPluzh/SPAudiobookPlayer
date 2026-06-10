import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QAction
from main import AudiobookPlayerWindow

def test_remember_folders_per_filter_behavior(tmp_path):
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    # Mock settings directory structure inside tmp_path
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    # Write a dummy settings.ini
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(
            "[Library]\n"
            "remember_filter_folders=True\n"
            "show_folders=False\n"
            "show_folders_all=True\n"
            "show_folders_not_started=False\n"
            "show_folders_in_progress=True\n"
            "show_folders_completed=False\n"
        )

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
        
        # Verify loaded settings
        assert window.remember_filter_folders is True
        assert window.library_show_folders["all"] is True
        assert window.library_show_folders["not_started"] is False
        assert window.library_show_folders["in_progress"] is True
        assert window.library_show_folders["completed"] is False
        
        # Verify the menu action exists
        assert hasattr(window, 'remember_filter_folders_action')
        assert isinstance(window.remember_filter_folders_action, QAction)
        assert window.remember_filter_folders_action.isCheckable() is True
        assert window.remember_filter_folders_action.isChecked() is True
        
        # Check initial widget state (default library_filter_mode is "all")
        assert window.library_widget.remember_filter_folders is True
        assert window.library_widget.show_folders is True
        assert window.library_widget.btn_show_folders.isChecked() is True

        # Switch to "not_started" filter and verify folders are hidden
        window.library_widget.apply_filter("not_started")
        assert window.library_widget.show_folders is False
        assert window.library_widget.btn_show_folders.isChecked() is False
        assert window.show_folders is False
        
        # Switch to "in_progress" filter and verify folders are shown
        window.library_widget.apply_filter("in_progress")
        assert window.library_widget.show_folders is True
        assert window.library_widget.btn_show_folders.isChecked() is True
        assert window.show_folders is True

        # Toggle folder view off while in "in_progress"
        window.library_widget.on_show_folders_toggled(False)
        assert window.library_widget.show_folders is False
        assert window.library_widget.show_folders_by_filter["in_progress"] is False
        assert window.library_show_folders["in_progress"] is False

        # Toggle remember off via window method
        window.toggle_remember_filter_folders(False)
        assert window.remember_filter_folders is False
        assert window.library_widget.remember_filter_folders is False
        assert window.remember_filter_folders_action.isChecked() is False

        # Toggle folders back on
        window.library_widget.on_show_folders_toggled(True)
        # Verify global state is updated, but show_folders_by_filter doesn't get updated when remember is off
        assert window.library_widget.show_folders is True
        
        # Toggle remember back on
        window.toggle_remember_filter_folders(True)
        assert window.remember_filter_folders is True
        assert window.library_widget.remember_filter_folders is True
        # Current active filter is "in_progress", so it should now map to True
        assert window.library_widget.show_folders_by_filter["in_progress"] is True
