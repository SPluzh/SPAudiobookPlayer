import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from main import AudiobookPlayerWindow

def test_mass_select_ui_behavior(tmp_path):
    app = QApplication.instance() or QApplication([])

    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(
            "[Library]\n"
            "remember_filter_folders=True\n"
            "show_folders=False\n"
        )

    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []
         
        window = AudiobookPlayerWindow()
        library = window.library_widget

        # Verify mass select button exists and is configured
        assert hasattr(library, 'btn_mass_select')
        assert library.btn_mass_select.isCheckable() is True
        assert library.btn_mass_select.isChecked() is False
        assert hasattr(library, 'btn_mass_select_arrow')

        # Toggle mass selection
        library.btn_mass_select.click()
        assert library.tree.mass_selection_mode is True
        assert library.btn_mass_select.isChecked() is True
        assert library.delegate.tree == library.tree

        # Check path selection persistence
        library.tree.selected_audiobook_paths.add("dummy_path")
        assert "dummy_path" in library.tree.selected_audiobook_paths
        
        # Untoggle mass selection clears paths
        library.btn_mass_select.click()
        assert library.tree.mass_selection_mode is False
        assert library.btn_mass_select.isChecked() is False
        assert len(library.tree.selected_audiobook_paths) == 0

        # Test select all / deselect all logic
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
        
        books = [
            make_mock_book(1, "path/A", "Book A"),
            make_mock_book(2, "path/B", "Book B"),
        ]
        
        mock_db.get_audiobook_count.return_value = 2
        mock_db.load_audiobooks_from_db.return_value = {"": books}
        
        library.load_audiobooks(use_cache=False)
        
        library.select_all_audiobooks()
        assert library.tree.mass_selection_mode is True
        assert library.btn_mass_select.isChecked() is True
        assert "path/A" in library.tree.selected_audiobook_paths
        assert "path/B" in library.tree.selected_audiobook_paths
        assert len(library.tree.selected_audiobook_paths) == 2
        
        library.deselect_all_audiobooks()
        assert len(library.tree.selected_audiobook_paths) == 0


def test_mass_select_mark_actions(tmp_path):
    from PyQt6.QtCore import Qt
    app = QApplication.instance() or QApplication([])

    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(
            "[Library]\n"
            "remember_filter_folders=True\n"
            "show_folders=False\n"
        )

    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []
         
        window = AudiobookPlayerWindow()
        library = window.library_widget

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
                "duration": 1000.0,
                "listened_duration": 0.0,
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
        
        books = [
            make_mock_book(1, "path/A", "Book A"),
            make_mock_book(2, "path/B", "Book B"),
        ]
        
        mock_db.get_audiobook_count.return_value = 2
        mock_db.load_audiobooks_from_db.return_value = {"": books}
        
        def get_info_side_effect(path):
            if path == "path/A":
                return (1, "Book A", "Author", "Book A", 0, 0, 1000.0)
            elif path == "path/B":
                return (2, "Book B", "Author", "Book B", 0, 0, 1000.0)
            return None
        mock_db.get_audiobook_info.side_effect = get_info_side_effect
        
        library.load_audiobooks(use_cache=False)
        
        library.select_all_audiobooks()
        assert len(library.tree.selected_audiobook_paths) == 2
        
        # Trigger mark as read
        library.mark_as_read(1, 1000.0, "path/A")
        
        # Verify db.mark_audiobook_completed was called for both
        mock_db.mark_audiobook_completed.assert_any_call(1, 1000.0)
        mock_db.mark_audiobook_completed.assert_any_call(2, 1000.0)
        
        item_a = library.find_item_by_path(library.tree.invisibleRootItem(), "path/A")
        item_b = library.find_item_by_path(library.tree.invisibleRootItem(), "path/B")
        assert item_a.data(0, Qt.ItemDataRole.UserRole + 3) == (True, True, False)
        assert item_b.data(0, Qt.ItemDataRole.UserRole + 3) == (True, True, False)
        
        # Reset mock calls
        mock_db.reset_mock()
        mock_db.get_audiobook_info.side_effect = get_info_side_effect
        
        # Trigger mark as unread
        library.mark_as_unread(1, "path/A")
        
        # Verify db.reset_audiobook_status was called for both
        mock_db.reset_audiobook_status.assert_any_call(1)
        mock_db.reset_audiobook_status.assert_any_call(2)
        
        assert item_a.data(0, Qt.ItemDataRole.UserRole + 3) == (False, False, False)
        assert item_b.data(0, Qt.ItemDataRole.UserRole + 3) == (False, False, False)


def test_folder_mass_selection(tmp_path):
    from PyQt6.QtCore import Qt
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

        # Return a structure with folders and subfolders
        mock_db.load_audiobooks_from_db.return_value = {
            "": [
                {
                    "is_folder": True,
                    "path": "path/FolderX",
                    "name": "Folder X",
                    "is_expanded": True,
                }
            ],
            "path/FolderX": [
                make_mock_book(1, "path/FolderX/BookA", "Book A"),
                make_mock_book(2, "path/FolderX/BookB", "Book B"),
            ]
        }

        window = AudiobookPlayerWindow()
        library = window.library_widget
        library.load_audiobooks(use_cache=False)

        tree = library.tree
        assert tree.topLevelItemCount() > 0
        
        # Enable mass select mode
        library.btn_mass_select.click()
        assert tree.mass_selection_mode is True

        # Let's locate the tree items
        root_item = tree.invisibleRootItem()
        folder_item = root_item.child(0)
        assert folder_item.text(0).startswith("Folder X")
        assert folder_item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder"

        book_a_item = folder_item.child(0)
        book_b_item = folder_item.child(1)

        # 1. Test clicking a folder recursively selects children
        tree._set_item_selected_recursive(folder_item, True)
        tree._update_parent_checkbox_states(folder_item)

        assert "path/FolderX" in tree.selected_audiobook_paths
        assert "path/FolderX/BookA" in tree.selected_audiobook_paths
        assert "path/FolderX/BookB" in tree.selected_audiobook_paths

        # 2. Test deselecting a child deselects the parent folder
        tree.selected_audiobook_paths.remove("path/FolderX/BookA")
        tree._update_parent_checkbox_states(book_a_item)
        assert "path/FolderX" not in tree.selected_audiobook_paths
        assert "path/FolderX/BookB" in tree.selected_audiobook_paths

        # 3. Test selecting the child again selects the parent folder back
        tree.selected_audiobook_paths.add("path/FolderX/BookA")
        tree._update_parent_checkbox_states(book_a_item)
        assert "path/FolderX" in tree.selected_audiobook_paths
        assert "path/FolderX/BookB" in tree.selected_audiobook_paths

        # 4. Test deselecting folder recursively deselects children
        tree._set_item_selected_recursive(folder_item, False)
        tree._update_parent_checkbox_states(folder_item)
        assert "path/FolderX" not in tree.selected_audiobook_paths
        assert "path/FolderX/BookA" not in tree.selected_audiobook_paths
        assert "path/FolderX/BookB" not in tree.selected_audiobook_paths

        # 5. Test select_all_audiobooks selects folders too via sync
        library.select_all_audiobooks()
        assert "path/FolderX" in tree.selected_audiobook_paths
        assert "path/FolderX/BookA" in tree.selected_audiobook_paths
        assert "path/FolderX/BookB" in tree.selected_audiobook_paths


def test_mass_select_shift_range_selection(tmp_path):
    from PyQt6.QtCore import Qt, QPointF, QRect, QRectF
    from PyQt6.QtGui import QMouseEvent
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
        mock_db.get_audiobook_count.return_value = 4
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
                make_mock_book(1, "path/BookA", "Book A"),
                make_mock_book(2, "path/BookB", "Book B"),
                make_mock_book(3, "path/BookC", "Book C"),
                make_mock_book(4, "path/BookD", "Book D"),
            ]
        }

        window = AudiobookPlayerWindow()
        library = window.library_widget
        library.load_audiobooks(use_cache=False)

        tree = library.tree
        # Enable mass select mode
        library.btn_mass_select.click()
        assert tree.mass_selection_mode is True

        root_item = tree.invisibleRootItem()
        item_a = root_item.child(0)
        item_b = root_item.child(1)
        item_c = root_item.child(2)
        item_d = root_item.child(3)

        all_items = tree._get_all_tree_items()
        assert len(all_items) == 4

        # Let's mock delegate.get_checkbox_rect to return a rect that contains event.pos()
        mock_delegate = MagicMock()
        mock_delegate.get_play_button_rect.return_value = QRectF(0, 0, 0, 0)
        mock_delegate.get_checkbox_rect.return_value = QRectF(0, 0, 100, 100)
        mock_delegate.get_icon_rect.return_value = QRectF(0, 0, 50, 50)
        
        with patch.object(tree, 'itemDelegate', return_value=mock_delegate), \
             patch.object(tree, 'indexAt') as mock_index_at, \
             patch.object(tree, 'itemFromIndex') as mock_item_from_index, \
             patch.object(tree, 'visualRect', return_value=QRect(0, 0, 100, 100)):
            
            # Click A (no Shift)
            mock_index_at.return_value = tree.model().index(0, 0)
            mock_item_from_index.return_value = item_a
            
            # Mouse event with LeftButton and no modifiers
            from PyQt6.QtCore import QEvent
            event_a = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10.0, 10.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            tree.mousePressEvent(event_a)
            
            assert "path/BookA" in tree.selected_audiobook_paths
            assert tree._last_checked_item == item_a

            # Shift-Click D
            mock_index_at.return_value = tree.model().index(3, 0)
            mock_item_from_index.return_value = item_d
            
            # Mouse event with LeftButton and Shift modifier
            event_d = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10.0, 10.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ShiftModifier
            )
            tree.mousePressEvent(event_d)
            
            # Since target state (D) was unchecked, clicking D checks it, so target state is checked.
            # All items in range A to D should now be checked.
            assert "path/BookA" in tree.selected_audiobook_paths
            assert "path/BookB" in tree.selected_audiobook_paths
            assert "path/BookC" in tree.selected_audiobook_paths
            assert "path/BookD" in tree.selected_audiobook_paths
            assert tree._last_checked_item == item_d

            # Shift-Click B (unchecking)
            # D is currently checked, but let's click B. B is checked, so clicking it will uncheck it.
            # Thus target state is unchecked. Range B to D should be unchecked.
            mock_index_at.return_value = tree.model().index(1, 0)
            mock_item_from_index.return_value = item_b
            
            tree.mousePressEvent(event_d) # event_d has ShiftModifier
            
            assert "path/BookA" in tree.selected_audiobook_paths
            assert "path/BookB" not in tree.selected_audiobook_paths
            assert "path/BookC" not in tree.selected_audiobook_paths
            assert "path/BookD" not in tree.selected_audiobook_paths
            assert tree._last_checked_item == item_b


def test_mass_select_row_click(tmp_path):
    from PyQt6.QtCore import Qt, QPointF, QRect, QRectF
    from PyQt6.QtGui import QMouseEvent
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
        mock_db.get_audiobook_count.return_value = 1
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
                "description": "Some description",
                "total_size": 1000000,
                "is_started": False,
                "is_completed": False,
                "is_favorite": True,
            }

        mock_db.load_audiobooks_from_db.return_value = {
            "": [
                make_mock_book(1, "path/BookA", "Book A"),
            ]
        }

        window = AudiobookPlayerWindow()
        library = window.library_widget
        library.load_audiobooks(use_cache=False)

        tree = library.tree
        library.btn_mass_select.click()
        assert tree.mass_selection_mode is True

        root_item = tree.invisibleRootItem()
        item_a = root_item.child(0)

        # Mock delegate to return specific rects
        mock_delegate = MagicMock()
        mock_delegate.get_checkbox_rect.return_value = QRectF(10, 10, 20, 20)  # Checkbox at (10, 10)
        mock_delegate.get_play_button_rect.return_value = QRectF(40, 10, 20, 20)  # Play at (40, 10)
        mock_delegate.get_heart_rect.return_value = QRectF(70, 10, 20, 20)  # Favorite heart at (70, 10)
        mock_delegate.get_info_rect.return_value = QRectF(100, 10, 20, 20)  # Info at (100, 10)
        mock_delegate.get_icon_rect.return_value = QRectF(0, 0, 50, 50)
        
        with patch.object(tree, 'itemDelegate', return_value=mock_delegate), \
             patch.object(tree, 'indexAt') as mock_index_at, \
             patch.object(tree, 'itemFromIndex') as mock_item_from_index, \
             patch.object(tree, 'visualRect', return_value=QRect(0, 0, 200, 40)):
            
            mock_index_at.return_value = tree.model().index(0, 0)
            mock_item_from_index.return_value = item_a
            
            # Click A on play button: (50, 20)
            # This should play, NOT toggle selection
            from PyQt6.QtCore import QEvent
            event_play = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(50.0, 20.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            try:
                tree.play_button_clicked.disconnect()
            except TypeError:
                pass

            play_signal_called = []
            def on_play_clicked(path):
                play_signal_called.append(path)
            tree.play_button_clicked.connect(on_play_clicked)
            tree.mousePressEvent(event_play)
            assert "path/BookA" not in tree.selected_audiobook_paths
            assert len(play_signal_called) == 1 and play_signal_called[0] == "path/BookA"
            
            # Click A on row empty space (e.g. at (150, 20))
            # This should toggle selection (regular click)
            event_row = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(150.0, 20.0),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier
            )
            tree.mousePressEvent(event_row)
            assert "path/BookA" in tree.selected_audiobook_paths
            
            # Click A on row empty space again
            # This should untoggle selection
            tree.mousePressEvent(event_row)
            assert "path/BookA" not in tree.selected_audiobook_paths


