import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QAction
def test_tag_click_filtering(tmp_path):
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])
    from main import AudiobookPlayerWindow

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
         patch('main.BassPlayer') as mock_player_class, \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_player = mock_player_class.return_value
        mock_player.vol_pos = 1.0
        mock_player.speed_pos = 1.0
        mock_player.volume_boost_enabled = False
        mock_player.volume_boost_level = 4.0
        mock_player.get_position.return_value = 0.0
         
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

        # Verify arrow button click triggers show_tag_filter_menu
        with patch.object(library, 'show_tag_filter_menu') as mock_show_menu:
            library.btn_tags_arrow.click()
            mock_show_menu.assert_called_once()

        # Close window cleanly
        window.close()
        window.deleteLater()
        del window

        # Clear style manager proxy widgets cache
        from styles import StyleManager
        StyleManager._proxy_widgets.clear()

        # Force GC and event loop processing to ensure cleanup happens before app is destroyed
        import gc
        gc.collect()
        app.processEvents()
