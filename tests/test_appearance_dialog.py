import pytest
from PyQt6.QtCore import Qt
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
        default_border="#888888",
        current_status_new="#AA0000",
        default_status_new="#BB0000",
        current_status_started="#CC0000",
        default_status_started="#DD0000",
        current_status_completed="#EE0000",
        default_status_completed="#FF0000",
        current_icon_color="#CCCCCC",
        default_icon_color="#DDDDDD"
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

    assert dialog.original_icon_color == "#CCCCCC"
    assert dialog.current_icon_color == "#CCCCCC"
    assert dialog.default_icon_color == "#DDDDDD"
    assert dialog.icon_hex_input is not None
    assert dialog.icon_hex_input.text() == "#CCCCCC"
    assert dialog.icon_color_btn is not None

    assert dialog.original_status_new == "#AA0000"
    assert dialog.current_status_new == "#AA0000"
    assert dialog.default_status_new == "#BB0000"
    assert dialog.status_new_hex_input is not None
    assert dialog.status_new_hex_input.text() == "#AA0000"
    assert dialog.status_new_color_btn is not None

    # 2. Check reset to default button behavior and signals
    preview_emitted = []
    dialog.appearance_preview.connect(lambda acc, win, dark, txt, bord, s_new, s_started, s_completed, icon: preview_emitted.append((acc, win, dark, txt, bord, s_new, s_started, s_completed, icon)))

    dialog.default_btn.click()
    assert dialog.current_window == "#222222"
    assert dialog.window_hex_input.text() == "#222222"
    assert dialog.current_bg_dark == "#444444"
    assert dialog.bg_dark_hex_input.text() == "#444444"
    assert dialog.current_text == "#666666"
    assert dialog.text_hex_input.text() == "#666666"
    assert dialog.current_border == "#888888"
    assert dialog.border_hex_input.text() == "#888888"
    assert dialog.current_icon_color == "#DDDDDD"
    assert dialog.icon_hex_input.text() == "#DDDDDD"
    assert dialog.current_status_new == "#BB0000"
    assert dialog.status_new_hex_input.text() == "#BB0000"
    assert dialog.current_status_started == "#DD0000"
    assert dialog.status_started_hex_input.text() == "#DD0000"
    assert dialog.current_status_completed == "#FF0000"
    assert dialog.status_completed_hex_input.text() == "#FF0000"
    assert preview_emitted == [("#00FF00", "#222222", "#444444", "#666666", "#888888", "#BB0000", "#DD0000", "#FF0000", "#DDDDDD")]

    # 3. Check save/accept behavior and appearance_saved signal
    saved_emitted = []
    dialog.appearance_saved.connect(lambda acc, win, dark, txt, bord, s_new, s_started, s_completed, icon: saved_emitted.append((acc, win, dark, txt, bord, s_new, s_started, s_completed, icon)))

    # Since values equal their defaults, they should be cleared (empty strings saved)
    dialog.accept()
    assert saved_emitted == [("", "", "", "", "", "", "", "", "")]


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
        default_border="#888888",
        current_status_new="#AA0000",
        default_status_new="#BB0000",
        current_status_started="#CC0000",
        default_status_started="#DD0000",
        current_status_completed="#EE0000",
        default_status_completed="#FF0000",
        current_icon_color="#CCCCCC",
        default_icon_color="#DDDDDD"
    )

    preview_emitted = []
    dialog.appearance_preview.connect(lambda acc, win, dark, txt, bord, s_new, s_started, s_completed, icon: preview_emitted.append((acc, win, dark, txt, bord, s_new, s_started, s_completed, icon)))

    # Change text input to a valid hex color
    dialog.text_hex_input.setText("#999999")
    assert dialog.current_text == "#999999"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#777777", "#AA0000", "#CC0000", "#EE0000", "#CCCCCC")

    # Change border input to a valid hex color
    dialog.border_hex_input.setText("#AAAAAA")
    assert dialog.current_border == "#AAAAAA"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#AAAAAA", "#AA0000", "#CC0000", "#EE0000", "#CCCCCC")

    # Change icon input to a valid hex color
    dialog.icon_hex_input.setText("#123456")
    assert dialog.current_icon_color == "#123456"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#AAAAAA", "#AA0000", "#CC0000", "#EE0000", "#123456")

    # Change status_new input to a valid hex color
    dialog.status_new_hex_input.setText("#BBBBBB")
    assert dialog.current_status_new == "#BBBBBB"
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#999999", "#AAAAAA", "#BBBBBB", "#CC0000", "#EE0000", "#123456")

    # Reject reverts the values
    dialog.reject()
    assert preview_emitted[-1] == ("#FF0000", "#111111", "#333333", "#555555", "#777777", "#AA0000", "#CC0000", "#EE0000", "#CCCCCC")


def test_appearance_dialog_info_checkboxes():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        show_detailed_info=True,
        show_info_progress=True,
        show_info_file_count=False,
        show_info_duration=True,
        show_info_size=False,
        show_info_technical=True,
        show_info_year_written=False,
        show_info_year_recorded=True,
        show_info_language=False
    )

    def get_item(key):
        for idx in range(dialog.info_list_widget.count()):
            item = dialog.info_list_widget.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                return item
        return None

    # 1. Verify initial checkbox states (widgets and internal properties)
    assert dialog.current_show_detailed_info is True
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is False
    assert dialog.current_show_info_duration is True
    assert dialog.current_show_info_size is False
    assert dialog.current_show_info_technical is True
    assert dialog.current_show_info_year_written is False
    assert dialog.current_show_info_year_recorded is True
    assert dialog.current_show_info_language is False

    assert dialog.chk_show_detailed_info.isChecked() is True
    assert get_item("progress").checkState() == Qt.CheckState.Checked
    assert get_item("file_count").checkState() == Qt.CheckState.Unchecked
    assert get_item("duration").checkState() == Qt.CheckState.Checked
    assert get_item("size").checkState() == Qt.CheckState.Unchecked
    assert get_item("technical").checkState() == Qt.CheckState.Checked
    assert get_item("year_written").checkState() == Qt.CheckState.Unchecked
    assert get_item("year_recorded").checkState() == Qt.CheckState.Checked
    assert get_item("language").checkState() == Qt.CheckState.Unchecked

    # Child widgets should be enabled
    assert dialog.info_list_widget.isEnabled() is True

    # 2. Modify checkboxes and check updates
    get_item("progress").setCheckState(Qt.CheckState.Unchecked)
    get_item("file_count").setCheckState(Qt.CheckState.Checked)
    
    assert dialog.current_show_info_progress is False
    assert dialog.current_show_info_file_count is True

    # Toggle master checkbox off and verify child widgets become disabled
    dialog.chk_show_detailed_info.setChecked(False)
    assert dialog.current_show_detailed_info is False
    assert dialog.info_list_widget.isEnabled() is False

    # 3. Test reset to default (should make all checkboxes True and enabled)
    dialog.reset_to_default()
    assert dialog.current_show_detailed_info is True
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is True
    assert dialog.chk_show_detailed_info.isChecked() is True
    assert get_item("progress").checkState() == Qt.CheckState.Checked
    assert get_item("file_count").checkState() == Qt.CheckState.Checked
    assert dialog.info_list_widget.isEnabled() is True

    # 4. Test reject restores original constructor values
    dialog.reject()
    assert dialog.current_show_detailed_info is True
    assert dialog.current_show_info_progress is True
    assert dialog.current_show_info_file_count is False
    assert dialog.current_show_info_duration is True
    assert dialog.current_show_info_size is False
    assert dialog.current_show_info_technical is True
    assert dialog.current_show_info_year_written is False
    assert dialog.current_show_info_year_recorded is True
    assert dialog.current_show_info_language is False
    assert dialog.chk_show_detailed_info.isChecked() is True
    assert dialog.info_list_widget.isEnabled() is True


def test_appearance_dialog_interface_checkboxes():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        show_visualizer=True,
        show_nesting_lines=False,
        show_status_triangle=True,
        show_statusbar=False,
        remember_filter_folders=True
    )

    # 1. Verify initial checkbox states
    assert dialog.current_show_visualizer is True
    assert dialog.current_show_nesting_lines is False
    assert dialog.current_show_status_triangle is True
    assert dialog.current_show_statusbar is False
    assert dialog.current_remember_filter_folders is True

    assert dialog.chk_visualizer.isChecked() is True
    assert dialog.chk_nesting_lines.isChecked() is False
    assert dialog.chk_status_triangle.isChecked() is True
    assert dialog.chk_statusbar.isChecked() is False
    assert dialog.chk_remember_filter_folders.isChecked() is True

    # 2. Modify checkboxes and check updates
    dialog.chk_visualizer.setChecked(False)
    dialog.chk_nesting_lines.setChecked(True)
    
    assert dialog.current_show_visualizer is False
    assert dialog.current_show_nesting_lines is True

    # 3. Test reset to default
    dialog.reset_to_default()
    assert dialog.current_show_visualizer is True
    assert dialog.current_show_nesting_lines is True
    assert dialog.current_show_status_triangle is True
    assert dialog.current_show_statusbar is True
    assert dialog.current_remember_filter_folders is True

    # 4. Test reject restores original constructor values
    dialog.chk_visualizer.setChecked(False)
    dialog.reject()
    assert dialog.current_show_visualizer is True
    assert dialog.current_show_nesting_lines is False
    assert dialog.current_show_status_triangle is True
    assert dialog.current_show_statusbar is False
    assert dialog.current_remember_filter_folders is True


def test_appearance_dialog_info_order():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        info_order="duration,progress,size"
    )

    # 1. Verify initial order in list widget
    assert dialog.info_list_widget.count() == 8
    
    order = [dialog.info_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(8)]
    assert order[:3] == ["duration", "progress", "size"]

    # 2. Select the second item ("progress" at index 1) and move it up
    dialog.info_list_widget.setCurrentRow(1)
    dialog.btn_up.click()
    
    order = [dialog.info_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(8)]
    assert order[:3] == ["progress", "duration", "size"]
    assert dialog.get_info_settings()["info_order"].startswith("progress,duration,size")

    # 3. Select the third item ("size" at index 2) and move it down
    dialog.info_list_widget.setCurrentRow(2)
    dialog.btn_down.click()
    
    order = [dialog.info_list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(8)]
    assert order[:4] == ["progress", "duration", "file_count", "size"]
    assert dialog.get_info_settings()["info_order"].startswith("progress,duration,file_count,size")

    # 4. Reject reverts to original order
    dialog.reject()
    assert dialog.current_info_order == "duration,progress,size"


def test_appearance_dialog_tooltips():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_accent="#FF0000",
        default_accent="#00FF00"
    )

    # Verify tooltips are set on color inputs, buttons and checkboxes
    assert dialog.accent_color_btn.toolTip() != ""
    assert dialog.accent_hex_input.toolTip() != ""
    
    assert dialog.window_color_btn.toolTip() != ""
    assert dialog.window_hex_input.toolTip() != ""

    assert dialog.bg_dark_color_btn.toolTip() != ""
    assert dialog.bg_dark_hex_input.toolTip() != ""

    assert dialog.text_color_btn.toolTip() != ""
    assert dialog.text_hex_input.toolTip() != ""

    assert dialog.border_color_btn.toolTip() != ""
    assert dialog.border_hex_input.toolTip() != ""

    assert dialog.chk_statusbar.toolTip() != ""
    assert dialog.chk_status_triangle.toolTip() != ""

    assert dialog.status_new_color_btn.toolTip() != ""
    assert dialog.status_new_hex_input.toolTip() != ""
    assert dialog.status_started_color_btn.toolTip() != ""
    assert dialog.status_started_hex_input.toolTip() != ""
    assert dialog.status_completed_color_btn.toolTip() != ""
    assert dialog.status_completed_hex_input.toolTip() != ""

    assert dialog.chk_show_detailed_info.toolTip() != ""
    assert dialog.info_list_widget.toolTip() != ""
    
    assert dialog.chk_nesting_lines.toolTip() != ""
    assert dialog.chk_remember_filter_folders.toolTip() != ""
    assert dialog.chk_visualizer.toolTip() != ""

    # Verify tooltips are set on list widget items
    assert dialog.info_list_widget.count() > 0
    for idx in range(dialog.info_list_widget.count()):
        item = dialog.info_list_widget.item(idx)
        assert item.toolTip() != ""


def test_appearance_dialog_icon_thickness():
    app = QApplication.instance() or QApplication([])

    dialog = AppearanceDialog(
        parent=None,
        current_icon_thickness=2.5,
        default_icon_thickness=2.0
    )

    # 1. Verify initial states
    assert dialog.original_icon_thickness == 2.5
    assert dialog.current_icon_thickness == 2.5
    assert dialog.default_icon_thickness == 2.0
    assert dialog.thickness_slider.value() == 25
    assert "2.5 px" in dialog.thickness_value_label.text()

    # 2. Check value changes
    preview_emitted = []
    dialog.appearance_preview.connect(lambda *args: preview_emitted.append(args))
    
    dialog.thickness_slider.setValue(35)
    assert dialog.current_icon_thickness == 3.5
    assert "3.5 px" in dialog.thickness_value_label.text()
    assert len(preview_emitted) > 0
    assert preview_emitted[-1][-1] == 3.5  # Last argument is icon thickness

    # 3. Check reset to default
    dialog.default_btn.click()
    assert dialog.current_icon_thickness == 2.0
    assert dialog.thickness_slider.value() == 20
    assert "2.0 px" in dialog.thickness_value_label.text()

    # 4. Check save / accept
    saved_emitted = []
    dialog.appearance_saved.connect(lambda *args: saved_emitted.append(args))
    dialog.accept()
    assert len(saved_emitted) == 1
    assert saved_emitted[0][-1] == 2.0  # Saved thickness should be 2.0

    # 5. Check reject reverts changes
    dialog2 = AppearanceDialog(
        parent=None,
        current_icon_thickness=2.5,
        default_icon_thickness=2.0
    )
    dialog2.thickness_slider.setValue(15)
    assert dialog2.current_icon_thickness == 1.5
    dialog2.reject()
    # It should revert to original (2.5)
    assert dialog2.current_icon_thickness == 2.5


def test_library_widget_load_icons_updates_icons(monkeypatch):
    from library import LibraryWidget, MultiLineDelegate
    import utils

    app = QApplication.instance() or QApplication([])

    # Mock DB manager
    class DummyDB:
        def get_all_tags(self):
            return {}
        def load_audiobooks_from_db(self, *args, **kwargs):
            return {}
        def get_audiobook_count(self):
            return 0
        def get_all_audiobook_tags(self):
            return {}

    # Track icons loaded
    loaded_icons = []
    original_get_icon = utils.get_icon
    def mock_get_icon(name, *args, **kwargs):
        loaded_icons.append(name)
        return original_get_icon(name, *args, **kwargs)
    monkeypatch.setattr(utils, "get_icon", mock_get_icon)
    import library
    monkeypatch.setattr(library, "get_icon", mock_get_icon)

    config = {
        "audiobook_icon_size": 100,
        "folder_icon_size": 35,
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"}
    }

    delegate = MultiLineDelegate()
    widget = LibraryWidget(db_manager=DummyDB(), config=config, delegate=delegate)

    # Clear loaded_icons list to only record what is loaded in the reload call
    loaded_icons.clear()

    # Call reload
    widget.load_icons()

    # Verify that get_icon was called for buttons and for the delegate icons
    assert "narrator" in loaded_icons
    assert "author" in loaded_icons
    assert "info_bitrate" in loaded_icons
    assert "info_file_count" in loaded_icons
    assert "info_duration" in loaded_icons
    assert "info_size" in loaded_icons
    assert "languages" in loaded_icons
    assert "square-check" in loaded_icons
    assert "chevron-down" in loaded_icons
    assert "favorites" in loaded_icons
    assert "context_tags" in loaded_icons


