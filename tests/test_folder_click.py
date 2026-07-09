import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QRect, QRectF
from PyQt6.QtGui import QMouseEvent, QKeySequence
from main import AudiobookPlayerWindow

def test_folder_row_click_toggles_expansion(tmp_path):
    app = QApplication.instance() or QApplication([])

    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(
            "[Library]\n"
            "remember_filter_folders=True\n"
            "show_folders=True\n"
        )

    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 2
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []

        def make_mock_book(id_, path, name):
            return {
                "id": id_,
                "path": path,
                "name": name,
                "title": name,
                "author": "Author",
                "narrator": "Narrator X",
                "time_added": 100.0,
                "is_folder": False,
                "file_count": 1,
                "duration": 1000,
                "listened_duration": 0,
                "progress_percent": 0.0,
                "codec": "mp3",
                "bitrate_min": 128,
                "bitrate_max": 128,
                "bitrate_mode": "cbr",
                "container": "mp3",
                "description": "",
                "total_size": 1000000,
                "is_started": False,
                "is_completed": False,
                "is_favorite": False,
            }

        mock_db.load_audiobooks_from_db.return_value = {
            "": [
                {
                    "is_folder": True,
                    "path": "path/FolderX",
                    "name": "Folder X",
                    "is_expanded": False,
                }
            ],
            "path/FolderX": [
                make_mock_book(1, "path/FolderX/BookA", "Book A"),
            ]
        }

        window = AudiobookPlayerWindow()
        library = window.library_widget
        library.load_audiobooks(use_cache=False)

        tree = library.tree
        assert tree.topLevelItemCount() > 0
        
        root_item = tree.invisibleRootItem()
        folder_item = root_item.child(0)
        assert folder_item.text(0).startswith("Folder X")
        assert folder_item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder"
        assert folder_item.isExpanded() is False

        # Set up delegate mocks for checking clicks
        mock_delegate = MagicMock()
        mock_delegate.get_checkbox_rect.return_value = QRectF(10, 10, 20, 20)  # Checkbox at (10, 10)
        mock_delegate.get_icon_rect.return_value = QRectF(0, 0, 50, 50)
        
        with patch.object(tree, 'itemDelegate', return_value=mock_delegate), \
             patch.object(tree, 'indexAt') as mock_index_at, \
             patch.object(tree, 'itemFromIndex') as mock_item_from_index, \
             patch.object(tree, 'visualRect', return_value=QRect(0, 0, 200, 40)):
            
            mock_index_at.return_value = tree.model().index(0, 0)
            mock_item_from_index.return_value = folder_item

            # 1. Normal mode click anywhere on the folder row (e.g. at 150, 20)
            from PyQt6.QtCore import QEvent
            event_click1 = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(150.0, 20.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            tree.mousePressEvent(event_click1)
            # Folder X should now be expanded
            assert folder_item.isExpanded() is True

            # Click again to collapse
            tree.mousePressEvent(event_click1)
            assert folder_item.isExpanded() is False

            # 2. Enable mass select mode
            library.btn_mass_select.click()
            assert tree.mass_selection_mode is True

            # Click folder row outside checkbox (e.g. at 150, 20) -> should toggle expansion
            tree.mousePressEvent(event_click1)
            assert folder_item.isExpanded() is True
            # Selection should NOT be toggled
            assert "path/FolderX" not in tree.selected_audiobook_paths

            # Click folder row on the checkbox (e.g. at 15, 15) -> should toggle selection
            event_click_cb = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(15.0, 15.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            tree.mousePressEvent(event_click_cb)
            assert "path/FolderX" in tree.selected_audiobook_paths
            # Expansion state should remain True
            assert folder_item.isExpanded() is True

            # Click checkbox again -> deselects folder
            tree.mousePressEvent(event_click_cb)
            assert "path/FolderX" not in tree.selected_audiobook_paths

        # Clean up window
        window.close()
        window.deleteLater()
        del window
        from styles import StyleManager
        StyleManager._proxy_widgets.clear()
        import gc
        gc.collect()
        app.processEvents()
