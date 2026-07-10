import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import QMouseEvent

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import VirtualTileCanvas
from styles import StyleManager

class MockTreeItem:
    def __init__(self, path, data_tuple, status_tuple, cover_path, tags):
        self._path = path
        self._data = data_tuple
        self._status = status_tuple
        self._cover_path = cover_path
        self._tags = tags

    def data(self, column, role):
        if role == Qt.ItemDataRole.UserRole:
            return self._path
        elif role == Qt.ItemDataRole.UserRole + 2:
            return self._data
        elif role == Qt.ItemDataRole.UserRole + 3:
            return self._status
        elif role == Qt.ItemDataRole.UserRole + 4:
            return self._tags
        elif role == Qt.ItemDataRole.UserRole + 5:
            return self._cover_path
        return None

class MockLibraryTree:
    def __init__(self):
        from PyQt6.QtCore import pyqtSignal, QObject
        class MockSignal(QObject):
            search_requested = pyqtSignal(str)
        self._signal_obj = MockSignal()
        self.search_requested = self._signal_obj.search_requested
        self.mass_selection_mode = False

class MockLibraryWidget:
    def __init__(self):
        self.tree = MockLibraryTree()

class MockTileFlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = {"audiobook_icon_size": 100}
        self.parent_library = MockLibraryWidget()

def test_tile_author_narrator_layout_and_hover():
    app = QApplication.instance() or QApplication([])

    data_tuple = (
        "Test Author",
        "Test Title",
        "Test Narrator",
        10,
        7200.0,
        3600.0,
        50.0,
    )
    status_tuple = (True, False, False)
    
    item = MockTreeItem("some/path", data_tuple, status_tuple, "cover.jpg", [])
    
    mock_tile_flow = MockTileFlowWidget()
    canvas = VirtualTileCanvas(tile_flow_widget=mock_tile_flow)
    
    try:
        book_data = canvas._extract_book_data(item)
        book_data["rect"] = QRect(10, 10, 166, 281)
        
        # Test author rect calculation
        author_rect = canvas.get_author_rect(book_data)
        assert isinstance(author_rect, QRect)
        assert author_rect.left() == 18 # 10 + 8
        assert author_rect.width() > 0
        assert author_rect.height() > 0

        # Test narrator rect calculation
        narrator_rect = canvas.get_narrator_rect(book_data)
        assert isinstance(narrator_rect, QRect)
        assert narrator_rect.left() == 18 # 10 + 8
        assert narrator_rect.top() > author_rect.bottom()
        assert narrator_rect.width() > 0
        assert narrator_rect.height() > 0

        # Setup mock blocks inside canvas
        canvas.blocks = [{
            "type": "books",
            "y": 0,
            "height": 300,
            "books": [book_data]
        }]

        # Test mouseMoveEvent for Author Hover
        author_center = author_rect.center()
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(author_center),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mouseMoveEvent(move_event)
        assert canvas.hovered_field == "author"
        assert canvas.cursor().shape() == Qt.CursorShape.PointingHandCursor

        # Test mousePressEvent for Author Click (should emit search_requested)
        searches = []
        mock_tile_flow.parent_library.tree.search_requested.connect(searches.append)
        
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(author_center),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mousePressEvent(press_event)
        assert len(searches) == 1
        assert searches[0] == "Test Author"

        # Test mouseMoveEvent for Narrator Hover
        narrator_center = narrator_rect.center()
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(narrator_center),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mouseMoveEvent(move_event)
        assert canvas.hovered_field == "narrator"
        assert canvas.cursor().shape() == Qt.CursorShape.PointingHandCursor

        # Test mousePressEvent for Narrator Click (should emit search_requested)
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(narrator_center),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mousePressEvent(press_event)
        assert len(searches) == 2
        assert searches[1] == "Test Narrator"
        
    finally:
        canvas.deleteLater()
        mock_tile_flow.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()
