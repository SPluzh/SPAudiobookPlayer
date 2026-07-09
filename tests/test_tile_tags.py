import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF

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

class MockTileFlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = {"audiobook_icon_size": 100}
        self.parent_library = None

def test_tile_tags_extraction_and_layout():
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
    test_tags = [
        {"id": 1, "name": "Sci-Fi", "color": "#ff0000"},
        {"id": 2, "name": "Adventure", "color": "#00ff00"},
    ]
    
    item = MockTreeItem("some/path", data_tuple, status_tuple, "cover.jpg", test_tags)
    
    mock_tile_flow = MockTileFlowWidget()
    canvas = VirtualTileCanvas(tile_flow_widget=mock_tile_flow)
    
    try:
        # 1. Test Tag Extraction
        book_data = canvas._extract_book_data(item)
        assert book_data["tags"] == test_tags
        assert len(book_data["tags"]) == 2
        
        # Set dummy book rect
        book_data["rect"] = QRect(10, 10, 166, 281)
        
        # 2. Test tag rectangle layout calculation
        tag_rects = canvas.get_tags_rects(book_data)
        assert len(tag_rects) == 2
        
        # Check first tag properties
        tag1, rect1 = tag_rects[0]
        assert tag1["name"] == "Sci-Fi"
        assert isinstance(rect1, QRectF)
        assert rect1.left() == 18.0  # 10 (book_rect.left()) + 8 (padding)
        
        # Check second tag properties
        tag2, rect2 = tag_rects[1]
        assert tag2["name"] == "Adventure"
        assert rect2.left() > rect1.right()  # Space between tag pills
        
    finally:
        canvas.deleteLater()
        mock_tile_flow.deleteLater()
        StyleManager._proxy_widgets.clear()
        app.processEvents()
