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


def test_library_sorting_by_title_instead_of_name():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])

    def make_mock_book(id_, path, name, title, author):
        return {
            "id": id_,
            "path": path,
            "name": name,
            "title": title,
            "author": author,
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

    # Books where names and titles are in opposite alphabetical order:
    # Names: "Folder A", "Folder B"
    # Titles: "Z Title", "A Title"
    books = [
        make_mock_book(1, "path/A", "Folder A", "Z Title", "Author X"),
        make_mock_book(2, "path/B", "Folder B", "A Title", "Author Y"),
    ]

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 2
    db_manager.load_audiobooks_from_db.return_value = {"": books}

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    widget.show_folders = False

    # Sort by name (presented as Title in UI) ascending
    widget.sort_field = "name"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)

    items = []
    root = widget.tree.invisibleRootItem()
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    # If it sorts by title (A Title before Z Title), Book B ("path/B") must come first!
    assert items == ["path/B", "path/A"]


def test_library_sorting_by_progress():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])

    def make_mock_book(id_, path, name, progress_percent):
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
            "progress_percent": progress_percent,
            "codec": "mp3",
            "bitrate_min": 128,
            "bitrate_max": 128,
            "bitrate_mode": "cbr",
            "container": "mp3",
            "description": "",
            "total_size": 1000000,
            "is_started": progress_percent > 0,
            "is_completed": progress_percent >= 100,
            "is_favorite": False,
        }

    books = [
        make_mock_book(1, "path/A", "Book A", 25),
        make_mock_book(2, "path/B", "Book B", 75),
        make_mock_book(3, "path/C", "Book C", 0),
        make_mock_book(4, "path/D", "Book D", 100),
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
    widget.show_folders = False

    # --- Test 1: Sort by progress_percent ascending ---
    # Expected order: 0 (C), 25 (A), 75 (B), 100 (D)
    widget.sort_field = "progress_percent"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)

    items = []
    root = widget.tree.invisibleRootItem()
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    assert items == ["path/C", "path/A", "path/B", "path/D"]

    # --- Test 2: Sort by progress_percent descending ---
    # Expected order: 100 (D), 75 (B), 25 (A), 0 (C)
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)

    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    assert items == ["path/D", "path/B", "path/A", "path/C"]


def test_library_sorting_new_fields():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])

    def make_mock_book(id_, path, name, year_written, year_recorded, language):
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
            "year_written": year_written,
            "year_recorded": year_recorded,
            "language": language,
        }

    books = [
        make_mock_book(1, "path/A", "Book A", "1954", "2010", "English"),
        make_mock_book(2, "path/B", "Book B", "1869", "2020", "Russian"),
        make_mock_book(3, "path/C", "Book C", "2005", "2005", "french"),
    ]

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 3
    db_manager.load_audiobooks_from_db.return_value = {"": books}

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    widget.show_folders = False

    # --- Test 1: Sort by year_written ascending ---
    # Expected: 1869 (B), 1954 (A), 2005 (C)
    widget.sort_field = "year_written"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)

    items = []
    root = widget.tree.invisibleRootItem()
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    assert items == ["path/B", "path/A", "path/C"]

    # --- Test 2: Sort by year_recorded descending ---
    # Expected: 2020 (B), 2010 (A), 2005 (C)
    widget.sort_field = "year_recorded"
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)

    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    assert items == ["path/B", "path/A", "path/C"]

    # --- Test 3: Sort by language ascending (case-insensitive) ---
    # Expected: English (A), french (C), Russian (B)
    widget.sort_field = "language"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=True)

    items = []
    for i in range(root.childCount()):
        child = root.child(i)
        items.append(child.data(0, Qt.ItemDataRole.UserRole))

    assert items == ["path/A", "path/C", "path/B"]


def test_library_sorting_folders_enabled():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])

    def make_mock_book(id_, path, parent_path, name, language):
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
            "language": language,
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
            "language": None,
        }

    db_data = {
        "": [
            make_mock_folder("folder_ru", "", "Folder Russian"),
            make_mock_folder("folder_en", "", "Folder English"),
        ],
        "folder_ru": [
            make_mock_book(1, "folder_ru/book_ru", "folder_ru", "Book RU", "Russian"),
        ],
        "folder_en": [
            make_mock_book(2, "folder_en/book_en", "folder_en", "Book EN", "English"),
        ]
    }

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 2
    db_manager.load_audiobooks_from_db.return_value = db_data

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    widget.show_folders = True

    # --- Test 1: Sort by name ascending ---
    # Expected folder order: Folder English ("folder_en") then Folder Russian ("folder_ru")
    widget.sort_field = "name"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)

    root = widget.tree.invisibleRootItem()
    items = [root.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(root.childCount())]
    assert items == ["folder_en", "folder_ru"]

    # --- Test 2: Sort by language ascending ---
    # Folder English contains English, Folder Russian contains Russian
    # So Folder English should still be first
    widget.sort_field = "language"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=True)

    root = widget.tree.invisibleRootItem()
    items = [root.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(root.childCount())]
    assert items == ["folder_en", "folder_ru"]

    # --- Test 3: Sort by language descending ---
    # If sort order is descending, folders themselves must be alphabetical descending
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)

    root = widget.tree.invisibleRootItem()
    items = [root.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(root.childCount())]
    assert items == ["folder_ru", "folder_en"]


def test_library_sorting_books_inside_folders():
    # Ensure QApplication is initialized
    app = QApplication.instance() or QApplication([])

    def make_mock_book(id_, path, parent_path, name, year_recorded):
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
            "language": "English",
            "year_written": None,
            "year_recorded": year_recorded,
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
            "language": None,
            "year_written": None,
            "year_recorded": None,
        }

    # Hierarchy:
    # - Folder: "folder_parent", contains two books:
    #   - "book_2020" (year_recorded = "2020")
    #   - "book_2010" (year_recorded = "2010")
    db_data = {
        "": [
            make_mock_folder("folder_parent", "", "Folder Parent"),
        ],
        "folder_parent": [
            make_mock_book(1, "folder_parent/book_2020", "folder_parent", "Book 2020", "2020"),
            make_mock_book(2, "folder_parent/book_2010", "folder_parent", "Book 2010", "2010"),
        ]
    }

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 2
    db_manager.load_audiobooks_from_db.return_value = db_data

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    widget.show_folders = True

    # --- Test 1: Sort by year_recorded ascending ---
    # Expected: "Book 2010" then "Book 2020"
    widget.sort_field = "year_recorded"
    widget.sort_order = "asc"
    widget.load_audiobooks(use_cache=False)

    root = widget.tree.invisibleRootItem()
    assert root.childCount() == 1
    folder_item = root.child(0)
    assert folder_item.data(0, Qt.ItemDataRole.UserRole) == "folder_parent"
    
    # Check children of folder_parent
    assert folder_item.childCount() == 2
    child_paths = [folder_item.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(folder_item.childCount())]
    assert child_paths == ["folder_parent/book_2010", "folder_parent/book_2020"]

    # --- Test 2: Sort by year_recorded descending ---
    # Expected: "Book 2020" then "Book 2010"
    widget.sort_order = "desc"
    widget.load_audiobooks(use_cache=True)

    root = widget.tree.invisibleRootItem()
    folder_item = root.child(0)
    child_paths = [folder_item.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(folder_item.childCount())]
    assert child_paths == ["folder_parent/book_2020", "folder_parent/book_2010"]





