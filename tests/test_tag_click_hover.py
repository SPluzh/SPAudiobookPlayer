import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QAction
from main import AudiobookPlayerWindow

def test_tag_click_filtering(tmp_path):
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
            "tag_filter_active=False\n"
            "tag_filter_ids=\n"
        )

    # Patch DatabaseManager and BassPlayer, and point paths to tmp_path
    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = [{'id': 42, 'name': 'TestTag', 'color': '#00ff00'}]
         
        window = AudiobookPlayerWindow()
        library = window.library_widget

        # Initial check
        assert library.is_tag_filter_active is False
        assert not library.tag_filter_ids

        # Simulate clicking a tag
        tag = {'id': 42, 'name': 'TestTag', 'color': '#00ff00'}
        library.on_tree_tag_clicked(tag)

        # Verify tag filtering is active and filter ID is set
        assert library.is_tag_filter_active is True
        assert library.tag_filter_ids == {42}
        assert library.btn_tags.isChecked() is True
