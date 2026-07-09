import pytest
import sys
import math
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import Qt, QRect

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import VirtualTileCanvas
from styles import StyleManager

class MockTileFlowWidget(QWidget):
    def __init__(self, parent_library):
        super().__init__()
        self.config = {"audiobook_icon_size": 100}
        self.parent_library = parent_library

class MockLibraryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.tree = QTreeWidget()
        self.delegate = None
        self.show_nesting_lines = True
        self.folder_icon = None
        self.current_playing_item = None

    def _get_folder_stats(self, item):
        return 0, 0

    def _format_books_count(self, count):
        return "0 books"

def test_tile_nesting_is_last_child_rebuild():
    app = QApplication.instance() or QApplication([])

    library = MockLibraryWidget()
    tree = library.tree
    
    # Create structure:
    # Root
    #  +- Folder 1 (not last)
    #  |   +- Book A
    #  +- Folder 2 (last)
    #      +- Book B
    #      +- Book C
    
    root_item = tree.invisibleRootItem()
    
    f1 = QTreeWidgetItem(root_item)
    f1.setData(0, Qt.ItemDataRole.UserRole, "folder_1")
    f1.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
    
    f2 = QTreeWidgetItem(root_item)
    f2.setData(0, Qt.ItemDataRole.UserRole, "folder_2")
    f2.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
    
    # In PyQt, child count / parent is tracked.
    book_a = QTreeWidgetItem(f1)
    book_a.setData(0, Qt.ItemDataRole.UserRole, "book_a")
    book_a.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")
    
    book_b = QTreeWidgetItem(f2)
    book_b.setData(0, Qt.ItemDataRole.UserRole, "book_b")
    book_b.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")

    book_c = QTreeWidgetItem(f2)
    book_c.setData(0, Qt.ItemDataRole.UserRole, "book_c")
    book_c.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")

    # Set folders expanded
    f1.setExpanded(True)
    f2.setExpanded(True)
    
    mock_tile_flow = MockTileFlowWidget(library)
    canvas = VirtualTileCanvas(tile_flow_widget=mock_tile_flow)
    
    try:
        canvas.populate(root_item)
        
        # Verify block types and is_last_child setting
        books_blocks = [b for b in canvas.blocks if b["type"] == "books"]
        assert len(books_blocks) == 2
        
        # First books block has Book A, which is the last child of Folder 1.
        # So its is_last_child should be True (since it's the last child of Folder 1).
        assert books_blocks[0]["is_last_child"] is True
        
        # Second books block has Book B and Book C. Book C is the last child of Folder 2.
        # So its is_last_child should be True.
        assert books_blocks[1]["is_last_child"] is True

        # Now let's add a subfolder to Folder 2 after Book C, and test again
        f3 = QTreeWidgetItem(f2)
        f3.setData(0, Qt.ItemDataRole.UserRole, "folder_3")
        f3.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
        
        canvas.rebuild_blocks()
        books_blocks = [b for b in canvas.blocks if b["type"] == "books"]
        # The second books block (which is in Folder 2, but before Folder 3) is no longer the last child!
        # Because Folder 3 is after Book C now in Folder 2.
        assert books_blocks[1]["is_last_child"] is False
        
    finally:
        canvas.deleteLater()
        mock_tile_flow.deleteLater()
        library.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()
