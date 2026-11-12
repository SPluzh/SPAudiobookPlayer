import sys
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library_tile import VirtualTileCanvas


class MockTree:
    selected_audiobook_paths = set()
    mass_selection_mode = False


class MockLibrary:
    delegate = None
    current_playing_item = None
    tree = MockTree()
    show_nesting_lines = True
    nesting_lines_single_color = False
    nesting_lines_color = None


class MockTileFlowWidget(QWidget):
    def __init__(self, icon_size=100, with_library=False):
        super().__init__()
        self.config = {"audiobook_icon_size": icon_size}
        self.parent_library = MockLibrary() if with_library else None


def _make_book(
    path="book",
    title="",
    author="",
    narrator="",
    tags=None,
):
    return {
        "path": path,
        "title": title,
        "author": author,
        "narrator": narrator,
        "progress_percent": 0.0,
        "duration": 0.0,
        "language": None,
        "is_started": False,
        "is_completed": False,
        "is_favorite": False,
        "description": "",
        "cover_path": None,
        "tags": tags or [],
        "rect": QRect(),
        "tree_item": None,
    }


def test_book_content_height_scales_with_populated_fields():
    QApplication.instance() or QApplication([])
    canvas = VirtualTileCanvas(tile_flow_widget=MockTileFlowWidget(100))
    icon_size = 150
    tile_w = icon_size + 16

    h_empty = canvas._get_book_content_height(_make_book(), icon_size, tile_w)
    h_title_1 = canvas._get_book_content_height(
        _make_book(title="Short"), icon_size, tile_w
    )
    h_title_2 = canvas._get_book_content_height(
        _make_book(title="Very Long Book Title That Definitely Wraps Onto Two Lines"),
        icon_size,
        tile_w,
    )
    h_author = canvas._get_book_content_height(
        _make_book(title="Short", author="Author Name"), icon_size, tile_w
    )
    h_narrator = canvas._get_book_content_height(
        _make_book(title="Short", author="Author Name", narrator="Narrator Name"),
        icon_size,
        tile_w,
    )
    h_tags = canvas._get_book_content_height(
        _make_book(
            title="Short",
            author="Author Name",
            narrator="Narrator Name",
            tags=[{"id": 1, "name": "Sci-Fi", "color": "#ff0000"}],
        ),
        icon_size,
        tile_w,
    )

    assert h_empty == icon_size + 16
    assert h_empty < h_title_1 < h_title_2
    assert h_title_1 < h_author < h_narrator < h_tags
    # Compact cards must be noticeably shorter than the old fixed icon_size + 16 + 100
    assert h_title_1 < icon_size + 16 + 60


def test_update_layout_uses_per_row_max_height_and_paints():
    QApplication.instance() or QApplication([])
    canvas = VirtualTileCanvas(
        tile_flow_widget=MockTileFlowWidget(100, with_library=True)
    )
    # Wide enough for exactly 2 columns: grid_left=14, tile_w=166, hspacing=6 -> 14 + 166*2 + 6 + 12 = 364
    canvas.resize(400, 800)

    b1 = _make_book(path="b1", title="Book 1")
    b2 = _make_book(path="b2", title="Book 2")
    b3 = _make_book(path="b3", title="Book 3")
    b4 = _make_book(
        path="b4",
        title="Very Long Book Title That Definitely Wraps Onto Two Lines",
        author="Author Name",
        narrator="Narrator Name",
        tags=[{"id": 1, "name": "Fantasy", "color": "#00aa88"}],
    )

    block = {
        "type": "books",
        "depth": 1,
        "chain": [("root", False)],
        "is_last_child": True,
        "books": [b1, b2, b3, b4],
        "y": 0,
        "height": 0,
    }
    canvas.blocks = [block]
    canvas.update_layout()

    assert block["cols"] == 2
    assert len(block["row_heights"]) == 2
    assert len(block["row_ys"]) == 2

    row0_h, row1_h = block["row_heights"]
    assert row0_h < row1_h
    assert b1["rect"].height() == row0_h
    assert b2["rect"].height() == row0_h
    assert b3["rect"].height() == row1_h
    assert b4["rect"].height() == row1_h
    assert block["row_ys"][1] == block["row_ys"][0] + row0_h + 6
    assert block["height"] == row0_h + row1_h + 6 + 8

    # Verify paintEvent runs cleanly with dynamic row_heights / row_ys
    img = QImage(400, 800, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    canvas.render(painter)
    painter.end()


class MockTreeItem:
    def __init__(self, path, title, author="", narrator="", tags=None):
        self._path = path
        self._title = title
        self._author = author
        self._narrator = narrator
        self._tags = tags or []

    def data(self, column, role):
        if role == Qt.ItemDataRole.UserRole:
            return self._path
        if role == Qt.ItemDataRole.UserRole + 2:
            return (self._author, self._title, self._narrator, 1, 100.0, 0.0, 0.0)
        if role == Qt.ItemDataRole.UserRole + 3:
            return (False, False, False)
        if role == Qt.ItemDataRole.UserRole + 4:
            return self._tags
        if role == Qt.ItemDataRole.UserRole + 5:
            return None
        if role == Qt.ItemDataRole.UserRole + 6:
            return ""
        return None


def test_refresh_tile_recalculates_height_on_tag_and_metadata_change():
    QApplication.instance() or QApplication([])
    canvas = VirtualTileCanvas(
        tile_flow_widget=MockTileFlowWidget(100, with_library=True)
    )
    canvas.resize(400, 800)

    item = MockTreeItem("book_1", title="Short Title")
    book = canvas._extract_book_data(item)
    block = {
        "type": "books",
        "depth": 0,
        "chain": [],
        "is_last_child": True,
        "books": [book],
        "y": 0,
        "height": 0,
    }
    canvas.blocks = [block]
    canvas.update_layout()

    initial_tile_h = book["rect"].height()
    initial_total_h = canvas.calculated_height

    # Add tag -> height must increase
    item._tags = [{"id": 1, "name": "Sci-Fi", "color": "#ff0000"}]
    canvas.refresh_tile("book_1")
    with_tag_h = book["rect"].height()
    assert with_tag_h > initial_tile_h
    assert canvas.calculated_height > initial_total_h

    # Add author & narrator -> height must increase further
    item._author = "New Author"
    item._narrator = "New Narrator"
    canvas.refresh_tile("book_1")
    with_meta_h = book["rect"].height()
    assert with_meta_h > with_tag_h

    # Remove tags and metadata -> height must shrink back
    item._tags = []
    item._author = ""
    item._narrator = ""
    canvas.refresh_tile("book_1")
    assert book["rect"].height() == initial_tile_h
    assert canvas.calculated_height == initial_total_h

