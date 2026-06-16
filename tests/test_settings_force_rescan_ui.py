import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from settings_dialog import SettingsDialog
from translations import tr

def test_settings_dialog_force_rescan():
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    dialog = SettingsDialog(None, current_path="C:/DummyLibrary", ffprobe_path=Path("dummy_ffprobe"))
    
    # 1. Verify checkbox exists and is configured correctly
    assert hasattr(dialog, 'force_rescan_checkbox')
    assert dialog.force_rescan_checkbox.objectName() == "forceRescanCheckbox"
    assert dialog.force_rescan_checkbox.text() == tr("settings.force_rescan")
    assert dialog.force_rescan_checkbox.isChecked() is False

    # 2. Verify signal emission when checkbox is unchecked
    emitted_path = None
    emitted_force = None
    
    def on_scan_requested(path, force):
        nonlocal emitted_path, emitted_force
        emitted_path = path
        emitted_force = force

    dialog.scan_requested.connect(on_scan_requested)
    
    # Trigger scan request
    dialog.on_scan_requested()
    assert emitted_path == "C:/DummyLibrary"
    assert emitted_force is False

    # 3. Verify signal emission when checkbox is checked
    dialog.force_rescan_checkbox.setChecked(True)
    dialog.on_scan_requested()
    assert emitted_path == "C:/DummyLibrary"
    assert emitted_force is True
