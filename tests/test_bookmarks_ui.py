import pytest
from PyQt6.QtWidgets import QApplication, QPushButton
from player import PlayerWidget
from translations import tr

def test_add_bookmark_button_exists():
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])
    widget = PlayerWidget()
    
    # Check that add_bookmark_btn exists and is configured correctly
    assert hasattr(widget, 'add_bookmark_btn')
    assert isinstance(widget.add_bookmark_btn, QPushButton)
    assert widget.add_bookmark_btn.objectName() == "addBookmarkBtn"
    assert widget.add_bookmark_btn.text() == "+"
    assert widget.add_bookmark_btn.maximumWidth() == 20
    assert widget.add_bookmark_btn.minimumWidth() == 20
    assert widget.add_bookmark_btn.toolTip() == tr("bookmarks.add")

    # Check container exists and is configured correctly
    assert hasattr(widget, 'bookmarks_container')
    assert widget.bookmarks_container.maximumWidth() == 60
    assert widget.bookmarks_container.minimumWidth() == 60
    
    # Check signal emission
    emitted = False
    def on_clicked():
        nonlocal emitted
        emitted = True
        
    widget.add_bookmark_clicked.connect(on_clicked)
    widget.add_bookmark_btn.click()
    assert emitted is True
