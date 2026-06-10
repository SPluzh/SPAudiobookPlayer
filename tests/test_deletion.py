import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock, patch
from pathlib import Path

from library import LibraryWidget

def test_confirm_delete_emits_correctly():
    # Initialize QApplication if not done already
    app = QApplication.instance() or QApplication([])

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 0
    db_manager.load_audiobooks_from_db.return_value = {}

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    
    # Mock self.apply_blur and self.remove_blur
    widget.apply_blur = MagicMock()
    widget.remove_blur = MagicMock()

    # We mock QMessageBox.exec to return Yes, and mock QCheckBox to be checked
    with patch("library.QMessageBox.exec") as mock_exec, \
         patch("library.QCheckBox.isChecked") as mock_checked:
         
        mock_exec.return_value = QMessageBox.StandardButton.Yes
        mock_checked.return_value = True

        # Watch the delete_requested signal
        signal_spy = MagicMock()
        widget.delete_requested.connect(signal_spy)

        widget.confirm_delete(42, "path/to/book")

        signal_spy.assert_called_once_with(42, "path/to/book", True)

    # Now verify with delete_from_disk as False (checkbox unchecked)
    with patch("library.QMessageBox.exec") as mock_exec, \
         patch("library.QCheckBox.isChecked") as mock_checked:
         
        mock_exec.return_value = QMessageBox.StandardButton.Yes
        mock_checked.return_value = False

        signal_spy = MagicMock()
        widget.delete_requested.connect(signal_spy)

        widget.confirm_delete(42, "path/to/book")

        signal_spy.assert_called_once_with(42, "path/to/book", False)

    # Now verify with cancel/No (should not emit signal)
    with patch("library.QMessageBox.exec") as mock_exec:
        mock_exec.return_value = QMessageBox.StandardButton.No

        signal_spy = MagicMock()
        widget.delete_requested.connect(signal_spy)

        widget.confirm_delete(42, "path/to/book")

        signal_spy.assert_not_called()

def test_on_delete_requested_sends_to_trash():
    from main import AudiobookPlayerWindow
    
    window = MagicMock()
    window.default_path = "C:/mock_library"
    window.playback_controller = MagicMock()
    window.playback_controller.current_audiobook_id = 42
    window.player = MagicMock()
    window.delegate = MagicMock()
    window.db_manager = MagicMock()
    window.library_widget = MagicMock()
    window.statusBar.return_value = MagicMock()
    
    # Bind the method
    on_delete_requested_bound = AudiobookPlayerWindow.on_delete_requested.__get__(window, AudiobookPlayerWindow)
    
    with patch("main.Path.exists") as mock_exists, \
         patch("main.Path.is_dir") as mock_is_dir, \
         patch("shutil.rmtree") as mock_rmtree:
         
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        
        on_delete_requested_bound(42, "rel/path/to/book", delete_from_disk=True)
        
        # Verify rmtree was called with the absolute path
        expected_path = Path("C:/mock_library") / "rel/path/to/book"
        mock_rmtree.assert_called_once_with(expected_path)
        
        # Verify player unloaded
        window.player.unload.assert_called_once()
        # Verify db delete and ui remove
        window.db_manager.delete_audiobook.assert_called_once_with(42)
        window.library_widget.remove_audiobook_from_ui.assert_called_once_with("rel/path/to/book")


def test_recalculate_ancestors_stats():
    from PyQt6.QtWidgets import QTreeWidgetItem
    app = QApplication.instance() or QApplication([])

    db_manager = MagicMock()
    db_manager.get_all_tags.return_value = []
    db_manager.get_all_audiobook_tags.return_value = {}
    db_manager.get_audiobook_count.return_value = 1
    db_manager.load_audiobooks_from_db.return_value = {}

    config = {
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    widget = LibraryWidget(db_manager=db_manager, config=config)
    
    # Create a mock tree structure:
    # Root
    #   Folder (parent)
    #     Audiobook 1
    #     Audiobook 2
    
    parent_item = QTreeWidgetItem(widget.tree)
    parent_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
    parent_item.setData(0, Qt.ItemDataRole.UserRole + 5, "My Folder")
    parent_item.setText(0, "My Folder (2 books, 02:00:00)")
    
    book1 = QTreeWidgetItem(parent_item)
    book1.setData(0, Qt.ItemDataRole.UserRole, "path/to/book1")
    book1.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")
    # audiobook metadata tuple: (author, title, narrator, file_count, duration, listened_duration, progress_percent, codec, ...)
    # Let's set duration to 3600 (1 hour)
    book1.setData(0, Qt.ItemDataRole.UserRole + 2, ("Author", "Title1", "Narrator", 10, 3600.0, 0, 0, "mp3"))
    
    book2 = QTreeWidgetItem(parent_item)
    book2.setData(0, Qt.ItemDataRole.UserRole, "path/to/book2")
    book2.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")
    book2.setData(0, Qt.ItemDataRole.UserRole + 2, ("Author", "Title2", "Narrator", 10, 7200.0, 0, 0, "mp3"))
    
    # Now simulate removing book2 from parent
    parent_item.removeChild(book2)
    
    # Run recalculate
    widget._recalculate_ancestors_stats(parent_item)
    
    # Since only book1 is left, books_count=1, total_seconds=3600.0 (1 hour, which formats to "01:00:00")
    # The text of parent_item should become "My Folder (1 book, 01:00:00)" (or "1 книга" depending on language, let's check translation fallback: for "en" it's "1 book")
    assert "My Folder" in parent_item.text(0)
    assert "1 " in parent_item.text(0)
    
    # Now remove book1, making it empty
    parent_item.removeChild(book1)
    widget._recalculate_ancestors_stats(parent_item)
    
    # It should have been pruned/removed from the tree (since books_count is 0)
    assert parent_item.parent() is None
    assert widget.tree.indexOfTopLevelItem(parent_item) == -1

