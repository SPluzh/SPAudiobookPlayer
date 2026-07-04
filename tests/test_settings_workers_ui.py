import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
# pyrefly: ignore [missing-import]
from settings_dialog import SettingsDialog
# pyrefly: ignore [missing-import]
from translations import tr

def test_settings_dialog_workers():
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    # Create dialog with a custom opus_workers count of 4
    dialog = SettingsDialog(None, current_path="C:/DummyLibrary", ffprobe_path=Path("dummy_ffprobe"), opus_workers=4)
    
    # 1. Verify combobox exists and is configured correctly
    assert hasattr(dialog, 'workers_combo')
    # Default presets: Auto(0), 1, 2, 4, 6, 8, 10, 12, 16, 20, 32
    assert dialog.workers_combo.count() == 11
    assert dialog.workers_combo.currentData() == 4
    assert dialog.workers_combo.itemText(0) == tr("settings.opus_workers_auto")
    assert dialog.workers_combo.toolTip() == tr("settings.opus_workers_tooltip")

    # 2. Verify signal emission when saving settings
    emitted_workers = None
    
    def on_workers_changed(workers):
        nonlocal emitted_workers
        emitted_workers = workers

    dialog.opus_workers_changed.connect(on_workers_changed)
    
    # Set to a new value (8)
    idx = dialog.workers_combo.findData(8)
    assert idx != -1
    dialog.workers_combo.setCurrentIndex(idx)
    
    # Trigger save action
    dialog.on_save()
    assert emitted_workers == 8
