import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock
from library import LibraryWidget

def test_library_sorting_properties():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])
    
    # Mock database manager and its return values
    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 0
    db_manager.load_audiobooks_from_db.return_value = {}

    config = {
        "sort_orders": {
            "all": "asc",
            "not_started": "asc",
            "in_progress": "asc",
            "completed": "asc"
        },
        "sort_fields": {
            "all": "name",
            "not_started": "name",
            "in_progress": "name",
            "completed": "name"
        }
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    
    # Verify default values
    assert widget.sort_field == "name"
    assert widget.sort_order == "asc"
    
    # Change sort field and verify that sort order is not overwritten
    widget.sort_field = "time_added"
    assert widget.sort_field == "time_added"
    assert widget.sort_order == "asc"  # Should remain "asc"!
    
    # Change sort order and verify it updates correctly
    widget.sort_order = "desc"
    assert widget.sort_order == "desc"
    assert widget.sort_field == "time_added"  # Should remain "time_added"!
    
    # Change sort field to name again and check order is preserved
    widget.sort_field = "name"
    assert widget.sort_field == "name"
    assert widget.sort_order == "desc"  # Should remain "desc"!


def test_library_sorting_logic():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])
    
    # Mock data to return from load_audiobooks_from_db
    # It returns a dict of parent_path -> list of items.
    def make_mock_book(id_, path, name, author, time_added):
        return {
            "id": id_,
            "path": path,
            "name": name,
            "title": name,
            "author": author,
            "narrator": "Narrator X",
            "time_added": time_added,
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
        make_mock_book(1, "path/A", "Book A", "Author Z", 100.0),
        make_mock_book(2, "path/B", "Book B", "Author Y", 200.0),
        make_mock_book(3, "path/C", "Book C", "Author X", None),  # Empty time_added
        make_mock_book(4, "path/D", "Book D", "Author W", 150.0),
    ]
    
    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 4
    db_manager.load_audiobooks_from_db.return_value = {"": books}

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    widget.show_folders = False  # Use flat list view for easy validation
    
    # --- Test 1: Sort by name ascending ---
    widget.sort_field = "name"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)
    
    # Get items added to tree
    items = []
    root = widget.tree.invisibleRootItem()
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))  # path
        
    assert items == ["path/A", "path/B", "path/C", "path/D"]  # alphabetical Book A, B, C, D
    
    # --- Test 2: Sort by name descending ---
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)
    
    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))
        
    assert items == ["path/D", "path/C", "path/B", "path/A"]  # reverse alphabetical Book D, C, B, A

    # --- Test 3: Sort by time_added ascending ---
    # Expected order: 100.0 (A), 150.0 (D), 200.0 (B), and empty (C) at the end!
    widget.sort_field = "time_added"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=True)
    
    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))
        
    assert items == ["path/A", "path/D", "path/B", "path/C"]

    # --- Test 4: Sort by time_added descending ---
    # Expected order: 200.0 (B), 150.0 (D), 100.0 (A), and empty (C) at the end!
    widget.sort_field = "time_added"
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)
    
    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))
        
    assert items == ["path/B", "path/D", "path/A", "path/C"]
