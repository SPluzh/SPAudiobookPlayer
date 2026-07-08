import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock
from library import LibraryWidget, MultiLineDelegate

def test_tile_view_switch_crash():
    app = QApplication.instance() or QApplication([])
    
    def make_mock_book(id_, path, parent_path, name):
        return {
            "id": id_,
            "path": path,
            "parent_path": parent_path,
            "name": name,
            "title": name,
            "author": "Author",
            "narrator": "Narrator X",
            "time_added": 100.0,
            "is_folder": False,
            "file_count": 1,
            "duration": 1000,
            "listened_duration": 0,
            "progress_percent": 50.0,
            "codec": "mp3",
            "bitrate_min": 128,
            "bitrate_max": 128,
            "bitrate_mode": "cbr",
            "container": "mp3",
            "description": "Some description",
            "total_size": 1000000,
            "is_started": True,
            "is_completed": False,
            "is_favorite": True,
            "cover_path": "",
            "cached_cover_path": "",
        }

    def make_mock_folder(path, parent_path, name):
        return {
            "id": None,
            "path": path,
            "parent_path": parent_path,
            "name": name,
            "title": None,
            "author": None,
            "narrator": None,
            "time_added": None,
            "is_folder": True,
            "file_count": 0,
            "duration": 0,
            "listened_duration": 0,
            "progress_percent": 0.0,
            "codec": None,
            "bitrate_min": 0,
            "bitrate_max": 0,
            "bitrate_mode": None,
            "container": None,
            "description": "",
            "total_size": 0,
            "is_started": False,
            "is_completed": False,
            "is_favorite": False,
            "is_expanded": True,
        }

    db_data = {
        "": [
            make_mock_folder("folder_1", "", "Folder 1"),
        ],
        "folder_1": [
            make_mock_book(1, "folder_1/book_a", "folder_1", "Book A"),
            make_mock_folder("folder_1/folder_2", "folder_1", "Folder 2"),
        ],
        "folder_1/folder_2": [
            make_mock_book(2, "folder_1/folder_2/book_b", "folder_1/folder_2", "Book B"),
        ]
    }
    
    # Add 400 books to simulate large height and trigger the layout height limit logic
    for i in range(400):
        db_data["folder_1/folder_2"].append(
            make_mock_book(i + 10, f"folder_1/folder_2/book_{i}", "folder_1/folder_2", f"Book {i}")
        )
    
    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 402
    db_manager.load_audiobooks_from_db.return_value = db_data

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"},
        "audiobook_icon_size": 100,
        "folder_icon_size": 35,
    }

    # Create real MultiLineDelegate
    delegate = MultiLineDelegate()
    delegate.playing_path = "folder_1/book_a"
    delegate.is_paused = False

    window = QMainWindow()
    widget = LibraryWidget(db_manager=db_manager, config=config, delegate=delegate)
    window.setCentralWidget(widget)
    window.show()
    
    widget.show_folders = True
    
    # Load first
    widget.load_audiobooks(use_cache=False)
    
    # Switch multiple times
    for i in range(25):
        widget.set_tile_view_active(True)
        # Process events to allow deleteLater and paint events to run
        QApplication.processEvents()
        widget.set_tile_view_active(False)
        QApplication.processEvents()
