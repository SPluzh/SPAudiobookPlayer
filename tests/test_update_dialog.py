import pytest
from PyQt6.QtWidgets import QApplication
from update_dialog import UpdateDialog
from updater import UpdateCheckResult

def test_update_dialog_markdown():
    app = QApplication.instance() or QApplication([])
    
    # Create mock update info
    info = UpdateCheckResult()
    info.remote_version = "1.8.0"
    info.download_url = "https://example.com/update.zip"
    info.download_size = 1024
    info.release_notes = "## [1.8.0]\n- **UI**: Added a grid/tile view mode\n- **Library**: Optimized rendering"
    
    dialog = UpdateDialog(info)
    
    # Verify widget exists and is configured correctly
    assert hasattr(dialog, 'notes_text')
    assert dialog.notes_text.objectName() == "updateNotes"
    assert dialog.notes_text.isReadOnly() is True
    
    # Verify HTML representation contains parsed markdown elements
    html = dialog.notes_text.toHtml()
    assert "Added a grid/tile view mode" in html
    # Check if UI and Library list items are rendered
    assert "UI" in html
    assert "Library" in html
