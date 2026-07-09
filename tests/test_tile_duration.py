import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QRect

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import BookTileWidget, VirtualTileCanvas
from styles import StyleManager

class MockTreeItem:
    def __init__(self, path, data_tuple, status_tuple, cover_path):
        self._path = path
        self._data = data_tuple
        self._status = status_tuple
        self._cover_path = cover_path

    def data(self, column, role):
        if role == Qt.ItemDataRole.UserRole:
            return self._path
        elif role == Qt.ItemDataRole.UserRole + 2:
            return self._data
        elif role == Qt.ItemDataRole.UserRole + 3:
            return self._status
        elif role == Qt.ItemDataRole.UserRole + 5:
            return self._cover_path
        return None

class MockTileFlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = {"audiobook_icon_size": 100}
        self.parent_library = None

def test_tile_duration_extraction():
    app = QApplication.instance() or QApplication([])

    # Tuple inside tree item UserRole+2:
    # 0: author, 1: title, 2: narrator, 3: file_count, 4: duration, 5: listened_duration, 6: progress_percent
    data_tuple = (
        "Test Author",
        "Test Title",
        "Test Narrator",
        10,
        7200.0, # duration (2 hours)
        3600.0,
        50.0,
    )
    status_tuple = (True, False, False)
    
    item = MockTreeItem("some/path", data_tuple, status_tuple, "cover.jpg")
    
    mock_tile_flow = MockTileFlowWidget()
    canvas = VirtualTileCanvas(tile_flow_widget=mock_tile_flow)
    
    try:
        book_data = canvas._extract_book_data(item)
        assert book_data["duration"] == 7200.0
        assert book_data["title"] == "Test Title"
        assert book_data["author"] == "Test Author"
        assert book_data["progress_percent"] == 50.0
    finally:
        canvas.deleteLater()
        mock_tile_flow.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()

def test_book_tile_widget_duration():
    app = QApplication.instance() or QApplication([])
    
    tile = BookTileWidget(
        path="test_path",
        title="Test Book",
        author="Author",
        narrator="Narrator",
        progress_percent=50.0,
        is_started=True,
        is_completed=False,
        is_favorite=True,
        description="Book Description",
        pixmap=None,
        icon_size=150,
        duration=3600.0,
    )
    
    try:
        assert tile.duration == 3600.0
    finally:
        tile.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()
