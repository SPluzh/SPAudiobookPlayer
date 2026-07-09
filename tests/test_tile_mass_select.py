import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, QPointF, QPoint, QRect, QRectF
from PyQt6.QtGui import QMouseEvent
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import LibraryWidget, MultiLineDelegate, VirtualTileCanvas
from styles import StyleManager

def test_tile_mass_select_behavior():
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
            "progress_percent": 0.0,
            "codec": "mp3",
            "bitrate_min": 128,
            "bitrate_max": 128,
            "bitrate_mode": "cbr",
            "container": "mp3",
            "description": "Some description",
            "total_size": 1000000,
            "is_started": False,
            "is_completed": False,
            "is_favorite": False,
            "cover_path": "",
            "cached_cover_path": "",
        }

    def make_mock_folder(path, parent_path, name, is_expanded=True):
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
            make_mock_folder("folder_1", "", "Folder 1", is_expanded=True),
        ],
        "folder_1": [
            make_mock_book(1, "folder_1/book_a", "folder_1", "Book A"),
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

    delegate = MultiLineDelegate()
    window = None
    widget = None
    try:
        window = QMainWindow()
        widget = LibraryWidget(db_manager=db_manager, config=config, delegate=delegate)
        window.setCentralWidget(widget)
        window.show()
        
        widget.show_folders = True
        widget.load_audiobooks(use_cache=False)
        
        # Switch to tile view
        widget.set_tile_view_active(True)
        canvas = widget.tile_view.canvas
        
        # Force a resize and layout update to compute block and book rects
        canvas.setGeometry(0, 0, 800, 600)
        canvas.update_layout()
        
        # 1. Enable mass selection mode
        widget.on_mass_select_toggled(True)
        assert widget.tree.mass_selection_mode is True
        assert canvas.selected_paths == widget.tree.selected_audiobook_paths
        
        # Find book and folder block rects
        book_block = None
        folder_block = None
        for block in canvas.blocks:
            if block["type"] == "books":
                book_block = block
            elif block["type"] == "folder":
                folder_block = block
                
        assert book_block is not None
        assert folder_block is not None
        
        # Let's test checkbox geometry calculations
        icon_rect = QRect(10, 10, 150, 150)
        tile_cb_rect = canvas.get_tile_checkbox_rect(icon_rect)
        assert tile_cb_rect.width() == 20.0
        assert tile_cb_rect.height() == 20.0
        assert tile_cb_rect.left() == 133.0  # 10 + (150 - 1) - 20 - 6 = 133 (bottom-right)
        
        folder_cb_rect = canvas.get_folder_checkbox_rect(icon_rect)
        assert folder_cb_rect.width() == 18.0
        assert folder_cb_rect.height() == 18.0
        
        # 2. Test mouse hover and press on book tile checkbox
        book_item = book_block["books"][0]
        tile_rect = book_item["rect"]
        book_icon_size = int(widget.tile_view.config.get("audiobook_icon_size", 100) * 1.5)
        book_icon_rect = QRect(tile_rect.left() + 8, tile_rect.top() + 8, book_icon_size, book_icon_size)
        book_cb_rect = canvas.get_tile_checkbox_rect(tile_rect)
        
        # Simulate hover on checkbox
        cb_center = book_cb_rect.center().toPoint()
        hover_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(cb_center),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mouseMoveEvent(hover_event)
        assert canvas.hovered_field == "checkbox"
        
        # Simulate click on checkbox
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(cb_center),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mousePressEvent(press_event)
        assert "folder_1/book_a" in widget.tree.selected_audiobook_paths
        assert "folder_1/book_a" in canvas.selected_paths
        
        # Click again to deselect
        canvas.mousePressEvent(press_event)
        assert "folder_1/book_a" not in widget.tree.selected_audiobook_paths
        
        # 3. Test select_all / deselect_all synchronization
        widget.select_all_audiobooks()
        assert "folder_1/book_a" in canvas.selected_paths
        
        widget.deselect_all_audiobooks()
        assert "folder_1/book_a" not in canvas.selected_paths
        
        # 4. Test mouse hover and press on folder checkbox
        folder_icon_rect = QRect(folder_block["depth"] * 12 + 12 + 15, folder_block["y"] + (folder_block["height"] - 20) // 2, 20, 20)
        f_cb_rect = canvas.get_folder_checkbox_rect(folder_icon_rect)
        fcb_center = f_cb_rect.center().toPoint()
        
        # Simulate hover on folder checkbox
        f_hover_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(fcb_center),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.hovered_block = folder_block
        canvas.mouseMoveEvent(f_hover_event)
        assert canvas.hovered_field == "checkbox"
        
        # Simulate click on folder checkbox
        f_press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(fcb_center),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        canvas.mousePressEvent(f_press_event)
        assert "folder_1" in widget.tree.selected_audiobook_paths
        assert "folder_1/book_a" in widget.tree.selected_audiobook_paths
        
        # Click again to deselect folder recursively
        canvas.mousePressEvent(f_press_event)
        assert "folder_1" not in widget.tree.selected_audiobook_paths
        assert "folder_1/book_a" not in widget.tree.selected_audiobook_paths
        
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
        test_tile_mass_select_behavior()
        print("Tile mass select test passed successfully!")
    except Exception as e:
        print("Tile mass select test failed:")
        traceback.print_exc()
        sys.exit(1)
