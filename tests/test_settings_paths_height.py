from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSizePolicy
from settings_dialog import SettingsDialog


def test_settings_dialog_paths_height():
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(
        None,
        current_path=["C:/DummyLibrary1", "C:/DummyLibrary2"],
        ffprobe_path=Path("dummy_ffprobe"),
    )

    # 1. pathslist should have expanding vertical size policy and no maximum height (or QWIDGETSIZE_MAX)
    assert dialog.pathslist.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert dialog.pathslist.maximumHeight() >= 16777215  # Default QWIDGETSIZE_MAX, not capped at 160

    # 2. When dialog is resized to a larger height, pathslist should grow beyond 160px
    dialog.resize(800, 700)
    dialog.show()
    app.processEvents()

    assert dialog.pathslist.height() > 160

    dialog.close()
