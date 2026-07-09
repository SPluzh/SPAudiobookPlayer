import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QRect, QRectF, QPoint, QPointF

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import BookTileWidget, VirtualTileCanvas
from styles import StyleManager

class MockTileFlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = {"audiobook_icon_size": 100}
        self.parent_library = None

def test_tile_view_info_button_position_and_hover():
    app = QApplication.instance() or QApplication([])

    icon_rect = QRect(8, 8, 150, 150)
    
    tile = None
    canvas = None
    mock_tile_flow = None
    try:
        # 1. Test BookTileWidget info button rect
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
        )
        
        info_rect = tile.get_info_rect(icon_rect)
        # The info button must be positioned at the top-left of the icon, mirrored from heart (which is top-right)
        # i.e., around (icon_rect.left() - 4, icon_rect.top() - 4)
        assert info_rect.left() == icon_rect.left() - 4
        assert info_rect.top() == icon_rect.top() - 4
        assert info_rect.width() == 20.0
        assert info_rect.height() == 20.0

        # 2. Test VirtualTileCanvas info button rect
        mock_tile_flow = MockTileFlowWidget()
        canvas = VirtualTileCanvas(tile_flow_widget=mock_tile_flow)
        canvas_info_rect = canvas.get_info_rect(icon_rect)
        assert canvas_info_rect.left() == icon_rect.left() - 4
        assert canvas_info_rect.top() == icon_rect.top() - 4
        assert canvas_info_rect.width() == 20.0
        assert canvas_info_rect.height() == 20.0
        print("Success!")
    finally:
        if tile:
            tile.deleteLater()
        if canvas:
            # stop background thread in cover_loader
            if hasattr(canvas, "cover_loader") and canvas.cover_loader:
                canvas.cover_loader.stop()
                canvas.cover_loader.wait()
            canvas.deleteLater()
        if mock_tile_flow:
            mock_tile_flow.deleteLater()
        
        StyleManager._proxy_widgets.clear()
        app.processEvents()

if __name__ == "__main__":
    test_tile_view_info_button_position_and_hover()
