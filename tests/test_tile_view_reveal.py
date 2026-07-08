import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeWidget
from PyQt6.QtCore import Qt, QTimer
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import LibraryWidget, MultiLineDelegate
from styles import StyleManager

def test_reveal_current_audiobook_tile_view():
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

    def make_mock_folder(path, parent_path, name, is_expanded=False):
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
            "is_expanded": is_expanded,
        }

    db_data = {
        "": [
            make_mock_folder("folder_1", "", "Folder 1", is_expanded=False),
        ],
        "folder_1": [
            make_mock_folder("folder_1/folder_2", "folder_1", "Folder 2", is_expanded=False),
        ],
        "folder_1/folder_2": [
            make_mock_book(1, "folder_1/folder_2/book_a", "folder_1/folder_2", "Book A"),
        ]
    }
    
    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 1
    db_manager.load_audiobooks_from_db.return_value = db_data

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"},
        "audiobook_icon_size": 100,
        "folder_icon_size": 35,
    }

    # Create real MultiLineDelegate
    delegate = MultiLineDelegate()
    delegate.playing_path = "folder_1/folder_2/book_a"
    delegate.is_paused = False

    window = None
    widget = None
    try:
        window = QMainWindow()
        widget = LibraryWidget(db_manager=db_manager, config=config, delegate=delegate)
        window.setCentralWidget(widget)
        window.show()
        
        widget.show_folders = True
        widget.load_audiobooks(use_cache=False)
        
        # 1. Test reveal in standard tree view
        widget.set_tile_view_active(False)
        
        # Ensure parents are collapsed initially
        item_f1 = widget.find_item_by_path(widget.tree.invisibleRootItem(), "folder_1")
        item_f2 = widget.find_item_by_path(widget.tree.invisibleRootItem(), "folder_1/folder_2")
        assert item_f1 is not None
        assert item_f2 is not None
        item_f1.setExpanded(False)
        item_f2.setExpanded(False)
        
        # Trigger reveal
        widget.reveal_current_audiobook("folder_1/folder_2/book_a")
        
        # Verify that parents got expanded
        assert item_f1.isExpanded()
        assert item_f2.isExpanded()
        
        # 2. Test reveal in tile view
        widget.set_tile_view_active(True)
        
        # Collapse them again
        item_f1.setExpanded(False)
        item_f2.setExpanded(False)
        widget.tile_view.populate(widget.tree.invisibleRootItem())
        
        # Verify not in blocks when collapsed
        book_found_before = False
        for block in widget.tile_view.canvas.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    if book["path"] == "folder_1/folder_2/book_a":
                        book_found_before = True
        assert not book_found_before
        
        # Mock ensureVisible on tile_view to check it's called
        widget.tile_view.ensureVisible = MagicMock()
        
        # Trigger reveal in tile view
        widget.reveal_current_audiobook("folder_1/folder_2/book_a")
        
        # Verify parents got expanded in tree
        assert item_f1.isExpanded()
        assert item_f2.isExpanded()
        
        # Verify that the tile view blocks now contain the book
        book_found_after = False
        for block in widget.tile_view.canvas.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    if book["path"] == "folder_1/folder_2/book_a":
                        book_found_after = True
        assert book_found_after
        
        # Process events to allow QTimer.singleShot to execute
        QApplication.processEvents()
        
        # Verify ensureVisible was called
        widget.tile_view.ensureVisible.assert_called_once()
        args, kwargs = widget.tile_view.ensureVisible.call_args
        # center x, center y, xmargin, ymargin
        assert len(args) == 4
        assert args[2] > 0  # xmargin
        assert args[3] > 0  # ymargin

        # 3. Test expand all and collapse all folders in tile view
        # Start by collapsing
        widget.collapse_all_folders()
        assert not item_f1.isExpanded()
        assert not item_f2.isExpanded()
        
        # Verify no books in blocks when collapsed
        book_found_collapsed = False
        for block in widget.tile_view.canvas.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    if book["path"] == "folder_1/folder_2/book_a":
                        book_found_collapsed = True
        assert not book_found_collapsed
        
        # Now expand all
        widget.expand_all_folders()
        assert item_f1.isExpanded()
        assert item_f2.isExpanded()
        
        # Verify book is present in blocks when expanded
        book_found_expanded = False
        for block in widget.tile_view.canvas.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    if book["path"] == "folder_1/folder_2/book_a":
                        book_found_expanded = True
        assert book_found_expanded
    finally:
        if widget:
            widget.deleteLater()
        if window:
            window.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()
        del widget
        del window
        del app

if __name__ == "__main__":
    import traceback
    try:
        test_reveal_current_audiobook_tile_view()
        print("Test passed successfully!")
    except Exception as e:
        print("Test failed with exception:")
        traceback.print_exc()
        sys.exit(1)
