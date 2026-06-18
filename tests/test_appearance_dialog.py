import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from appearance_dialog import AppearanceDialog, ColorPickerDialog

def test_appearance_dialog_ui_and_signals():
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00"
    )

    # 1. Verify initial states
    assert dialog.original_accent == "#FF0000"
    assert dialog.current_accent == "#FF0000"
    assert dialog.default_accent == "#00FF00"
    assert dialog.hex_input is not None
    assert dialog.hex_input.text() == "#FF0000"
    assert dialog.custom_color_btn is not None

    # 2. Check reset to default button behavior and signals
    preview_emitted = []
    dialog.accent_preview.connect(lambda val: preview_emitted.append(val))

    dialog.default_btn.click()
    assert dialog.current_accent == "#00FF00"
    assert dialog.hex_input.text() == "#00FF00"
    assert preview_emitted == ["#00FF00"]

    # 3. Check save/accept behavior and accent_saved signal
    saved_emitted = []
    dialog.accent_saved.connect(lambda val: saved_emitted.append(val))

    # Accept will save empty string because current_accent is equal to default_accent
    dialog.accept()
    assert saved_emitted == [""]

def test_appearance_dialog_ui_and_signals_with_non_default_saved():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00"
    )

    saved_emitted = []
    dialog.accent_saved.connect(lambda val: saved_emitted.append(val))

    # Accept with non-default current_accent (should emit the current color value)
    dialog.accept()
    assert saved_emitted == ["#FF0000"]

def test_appearance_dialog_reject_reverts_preview():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00"
    )

    dialog.current_accent = "#FFFFFF"
    preview_emitted = []
    dialog.accent_preview.connect(lambda val: preview_emitted.append(val))

    dialog.reject()
    # Reject should emit the original accent color to revert it
    assert preview_emitted == ["#FF0000"]

def test_appearance_dialog_hex_input_changes():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#000000",
        default_accent="#00FF00"
    )

    preview_emitted = []
    dialog.accent_preview.connect(lambda val: preview_emitted.append(val))

    # Change text input to a valid hex color
    dialog.hex_input.setText("#0000FF")
    assert dialog.current_accent == "#0000FF"
    assert preview_emitted == ["#0000FF"]

def test_color_picker_dialog_interaction():
    app = QApplication.instance() or QApplication([])

    picker_dialog = ColorPickerDialog(
        parent=None,
        initial_color=QColor("#FF0000")
    )

    colors_emitted = []
    picker_dialog.colorChanged.connect(lambda c: colors_emitted.append(c.name().upper()))

    # 1. Change Saturation and Value via picker
    picker_dialog.picker.set_sv(128, 128)
    picker_dialog.picker.colorChanged.emit(128, 128)  # Sat=128, Val=128
    assert len(colors_emitted) > 0
    
    # 2. Change Hue via slider
    picker_dialog.hue_slider.setValue(180)
    assert colors_emitted[-1] == QColor.fromHsv(180, 128, 128).name().upper()


def test_appearance_dialog_window_color_ui_and_signals():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00",
        current_window="#111111",
        default_window="#222222",
        current_bg_dark="#333333",
        default_bg_dark="#444444",
        current_text="#555555",
        default_text="#666666",
        current_border="#777777",
        default_border="#888888"
    )

    # 1. Verify initial states
    assert dialog.original_window == "#111111"
    assert dialog.current_window == "#111111"
    assert dialog.default_window == "#222222"
    assert dialog.window_hex_input is not None
    assert dialog.window_hex_input.text() == "#111111"
    assert dialog.window_color_btn is not None

    assert dialog.original_bg_dark == "#333333"
    assert dialog.current_bg_dark == "#333333"
    assert dialog.default_bg_dark == "#444444"
    assert dialog.bg_dark_hex_input is not None
    assert dialog.bg_dark_hex_input.text() == "#333333"
    assert dialog.bg_dark_color_btn is not None

    assert dialog.original_text == "#555555"
    assert dialog.current_text == "#555555"
    assert dialog.default_text == "#666666"
    assert dialog.text_hex_input is not None
    assert dialog.text_hex_input.text() == "#555555"
    assert dialog.text_color_btn is not None

    assert dialog.original_border == "#777777"
    assert dialog.current_border == "#777777"
    assert dialog.default_border == "#888888"
    assert dialog.border_hex_input is not None
    assert dialog.border_hex_input.text() == "#777777"
    assert dialog.border_color_btn is not None

    # 2. Check reset to default button behavior and signals
    preview_emitted = []
    dialog.appearance_preview.connect(lambda acc, win, dark, txt, bord: preview_emitted.append((acc, win, dark, txt, bord)))

    dialog.default_btn.click()
    assert dialog.current_window == "#222222"
    assert dialog.window_hex_input.text() == "#222222"
    assert dialog.current_bg_dark == "#444444"
    assert dialog.bg_dark_hex_input.text() == "#444444"
    assert dialog.current_text == "#666666"
    assert dialog.text_hex_input.text() == "#666666"
    assert dialog.current_border == "#888888"
    assert dialog.border_hex_input.text() == "#888888"
    assert preview_emitted == [("#00FF00", "#222222", "#444444", "#666666", "#888888")]

    # 3. Check save/accept behavior and appearance_saved signal
    saved_emitted = []
    dialog.appearance_saved.connect(lambda acc, win, dark, txt, bord: saved_emitted.append((acc, win, dark, txt, bord)))

    # Since values equal their defaults, they should be cleared (empty strings saved)
    dialog.accept()
    assert saved_emitted == [("", "", "", "", "")]


def test_appearance_dialog_text_color_hex_input_and_reject():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00",
        current_window="#111111",
        default_window="#222222",
        current_bg_dark="#333333",
        default_bg_dark="#444444",
        current_text="#555555",
        default_text="#666666",
        current_border="#777777",
        default_border="#888888"
    )

    preview_emitted = []
    dialog.appearance_preview.connect(lambda acc, win, dark, txt, bord: preview_emitted.append((acc, win, dark, txt, bord)))

    # Change text input to a valid hex color
    dialog.text_hex_input.setText("#999999")
    assert dialog.current_text == "#999999"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#777777")

    # Change border input to a valid hex color
    dialog.border_hex_input.setText("#AAAAAA")
    assert dialog.current_border == "#AAAAAA"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#AAAAAA")

    # Reject reverts the values
    dialog.reject()
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#555555", "#777777")


def test_appearance_dialog_info_checkboxes():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        show_info_progress=True,
        show_info_file_count=False,
        show_info_duration=True,
        show_info_size=False,
        show_info_technical=True,
        show_info_year_written=False,
        show_info_year_recorded=True,
        show_info_language=False
    )

    # 1. Verify initial checkbox states (widgets and internal properties)
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is False
    assert dialog.current_show_info_duration is True
    assert dialog.current_show_info_size is False
    assert dialog.current_show_info_technical is True
    assert dialog.current_show_info_year_written is False
    assert dialog.current_show_info_year_recorded is True
    assert dialog.current_show_info_language is False

    assert dialog.chk_progress.isChecked() is True
    assert dialog.chk_files.isChecked() is False
    assert dialog.chk_duration.isChecked() is True
    assert dialog.chk_size.isChecked() is False
    assert dialog.chk_technical.isChecked() is True
    assert dialog.chk_year_written.isChecked() is False
    assert dialog.chk_year_recorded.isChecked() is True
    assert dialog.chk_language.isChecked() is False

    # 2. Modify checkboxes and check updates
    dialog.chk_progress.setChecked(False)
    dialog.chk_files.setChecked(True)
    
    assert dialog.current_show_info_progress is False
    assert dialog.current_show_info_file_count is True

    # 3. Test reset to default (should make all checkboxes True)
    dialog.reset_to_default()
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is True
    assert dialog.chk_progress.isChecked() is True
    assert dialog.chk_files.isChecked() is True

    # 4. Test reject restores original constructor values
    dialog.reject()
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is False
    assert dialog.current_show_info_duration is True
    assert dialog.current_show_info_size is False
    assert dialog.current_show_info_technical is True
    assert dialog.current_show_info_year_written is False
    assert dialog.current_show_info_year_recorded is True
    assert dialog.current_show_info_language is False
