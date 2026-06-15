import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

from opus_dialog import OpusConversionDialog
from main import AudiobookPlayerWindow

class MockMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.playback_controller = MagicMock()
        self.player = MagicMock()
        self.default_path = "C:/library_root"
        self.unload_active_book = MagicMock()

def test_unload_active_book_resets_state_and_ui():
    app = QApplication.instance() or QApplication([])

    window = MagicMock()
    # Let's bind the real unload_active_book method
    unload_bound = AudiobookPlayerWindow.unload_active_book.__get__(window, AudiobookPlayerWindow)

    window.playback_controller = MagicMock()
    window.playback_controller.current_audiobook_path = "some/path"
    window.player = MagicMock()
    window.player_widget = MagicMock()
    window.delegate = MagicMock()
    window.library_widget = MagicMock()
    window.save_last_session = MagicMock()

    # Call the bound method
    unload_bound(save_progress=True)

    # Check that it saves progress and last session
    window.playback_controller.save_current_progress.assert_called_once()
    window.save_last_session.assert_called_once()

    # Check that player was unloaded
    window.player.unload.assert_called_once()

    # Check internal states were reset
    assert window.playback_controller.current_audiobook_id is None
    assert window.playback_controller.current_audiobook_path == ""
    assert window.playback_controller.files_list == []
    assert window.playback_controller.saved_file_index == 0
    assert window.playback_controller.saved_position == 0

    # Check UI reset calls
    window.update_ui_for_audiobook.assert_called_once()
    window.player_widget.position_slider.setValue.assert_called_with(0)
    window.player_widget.total_progress_bar.setValue.assert_called_with(0)
    window.player_widget.time_current.setText.assert_called_with("0:00")
    window.player_widget.time_duration.setText.assert_called_with("0:00")
    assert window.delegate.playing_path is None
    window.library_widget.tree.viewport().update.assert_called_once()


def test_opus_dialog_unloads_active_book():
    app = QApplication.instance() or QApplication([])

    # Create the mock main window
    main_window = MockMainWindow()

    # Case 1: Active book matches conversion path
    main_window.playback_controller.current_audiobook_path = "book_to_convert"
    dialog = OpusConversionDialog(
        parent=main_window,
        library_paths=["C:/library_root/book_to_convert"],
    )

    # Mock QMessageBox warning to return Yes
    with patch("opus_dialog.QMessageBox.warning") as mock_warning, \
         patch("opus_dialog.OpusConversionThread") as mock_thread:
        mock_warning.return_value = QMessageBox.StandardButton.Yes
        # Mock thread to not run
        mock_thread.return_value = MagicMock()

        dialog._on_start()
        main_window.unload_active_book.assert_called_once()

    # Case 2: Active book is inside a folder being converted
    main_window.unload_active_book.reset_mock()
    main_window.playback_controller.current_audiobook_path = "folder_to_convert/some_book"
    dialog2 = OpusConversionDialog(
        parent=main_window,
        library_paths=["C:/library_root/folder_to_convert"],
    )

    with patch("opus_dialog.QMessageBox.warning") as mock_warning, \
         patch("opus_dialog.OpusConversionThread") as mock_thread:
        mock_warning.return_value = QMessageBox.StandardButton.Yes
        mock_thread.return_value = MagicMock()

        dialog2._on_start()
        main_window.unload_active_book.assert_called_once()

    # Case 3: Active book is unrelated to conversion paths
    main_window.unload_active_book.reset_mock()
    main_window.playback_controller.current_audiobook_path = "other_book"
    dialog3 = OpusConversionDialog(
        parent=main_window,
        library_paths=["C:/library_root/folder_to_convert"],
    )

    with patch("opus_dialog.QMessageBox.warning") as mock_warning, \
         patch("opus_dialog.OpusConversionThread") as mock_thread:
        mock_warning.return_value = QMessageBox.StandardButton.Yes
        mock_thread.return_value = MagicMock()

        dialog3._on_start()
        main_window.unload_active_book.assert_not_called()
