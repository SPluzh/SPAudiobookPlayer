import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget
from appearance_dialog import AppearanceDialog
from player import PlayerWidget
from main import (
    AudiobookPlayerWindow,
    DEFAULT_PLAYER_BUTTONS_ORDER,
    DEFAULT_PLAYER_BUTTONS_VISIBLE,
    PLAYER_BUTTON_WIDTHS,
    PLAYER_BUTTON_SPACING,
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_appearance_dialog_player_buttons_init(qapp):
    dialog = AppearanceDialog(
        parent=None,
        player_buttons_order="timer,id3,mono",
        default_player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        player_buttons_visible="timer,mono",
        default_player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
    )

    assert hasattr(dialog, "buttons_list_widget")
    assert dialog.buttons_list_widget.count() == len(dialog.player_button_keys)

    # First item should be timer and checked
    first_item = dialog.buttons_list_widget.item(0)
    assert first_item.data(Qt.ItemDataRole.UserRole) == "timer"
    assert first_item.checkState() == Qt.CheckState.Checked

    # Second item should be id3 and unchecked
    second_item = dialog.buttons_list_widget.item(1)
    assert second_item.data(Qt.ItemDataRole.UserRole) == "id3"
    assert second_item.checkState() == Qt.CheckState.Unchecked

    # Third item should be mono and checked
    third_item = dialog.buttons_list_widget.item(2)
    assert third_item.data(Qt.ItemDataRole.UserRole) == "mono"
    assert third_item.checkState() == Qt.CheckState.Checked


def test_appearance_dialog_player_buttons_reorder_and_toggle(qapp):
    dialog = AppearanceDialog(
        parent=None,
        player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        default_player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
        default_player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
    )

    # Check initially timer is at index 0, id3 at index 1
    assert dialog.buttons_list_widget.item(0).data(Qt.ItemDataRole.UserRole) == "timer"
    assert dialog.buttons_list_widget.item(1).data(Qt.ItemDataRole.UserRole) == "id3"

    # Select row 1 (id3) and move up
    dialog.buttons_list_widget.setCurrentRow(1)
    dialog.move_button_up()

    assert dialog.buttons_list_widget.item(0).data(Qt.ItemDataRole.UserRole) == "id3"
    assert dialog.buttons_list_widget.item(1).data(Qt.ItemDataRole.UserRole) == "timer"

    # Move id3 down back to index 1
    dialog.buttons_list_widget.setCurrentRow(0)
    dialog.move_button_down()
    assert dialog.buttons_list_widget.item(0).data(Qt.ItemDataRole.UserRole) == "timer"
    assert dialog.buttons_list_widget.item(1).data(Qt.ItemDataRole.UserRole) == "id3"

    # Toggle off id3
    dialog.buttons_list_widget.item(1).setCheckState(Qt.CheckState.Unchecked)

    settings = dialog.get_buttons_settings()
    visible_list = settings["player_buttons_visible"].split(",")
    assert "id3" not in visible_list
    assert "timer" in visible_list


def test_appearance_dialog_reset_and_reject(qapp):
    dialog = AppearanceDialog(
        parent=None,
        player_buttons_order="id3,timer",
        default_player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        player_buttons_visible="id3",
        default_player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
    )

    # Initial state
    assert dialog.current_player_buttons_visible == "id3"

    # Reset to default
    dialog.reset_to_default()
    assert dialog.current_player_buttons_order == DEFAULT_PLAYER_BUTTONS_ORDER
    assert dialog.current_player_buttons_visible == DEFAULT_PLAYER_BUTTONS_VISIBLE

    # Reject reverts to original
    dialog.reject()
    assert dialog.current_player_buttons_order == "id3,timer"
    assert dialog.current_player_buttons_visible == "id3"


def test_player_widget_update_buttons_layout(qapp):
    player = PlayerWidget()
    assert hasattr(player, "action_buttons")
    assert "timer" in player.action_buttons
    assert "id3" in player.action_buttons
    assert "bookmarks" in player.action_buttons

    # Reorder buttons: mono first, then timer, hide id3
    order = ["mono", "timer", "id3", "subtitles"]
    visibility = {"mono": True, "timer": True, "id3": False, "subtitles": True}

    player.update_buttons_layout(order, visibility)

    # Check widget visibility states (isHidden)
    assert player.action_buttons["mono"].isHidden() is False
    assert player.action_buttons["timer"].isHidden() is False
    assert player.action_buttons["id3"].isHidden() is True
    assert player.action_buttons["subtitles"].isHidden() is False


def test_calculate_player_min_width(qapp):
    class DummyWindow:
        calculate_player_min_width = AudiobookPlayerWindow.calculate_player_min_width

    window = DummyWindow()
    all_keys = set(PLAYER_BUTTON_WIDTHS.keys())

    # 1. All buttons visible -> base sizes (535, 700)
    p_w, n_w = window.calculate_player_min_width(all_keys)
    assert p_w == 535
    assert n_w == 700

    # 2. Disable id3 (40px + 5px spacing = 45px reduction)
    without_id3 = all_keys - {"id3"}
    p_w, n_w = window.calculate_player_min_width(without_id3)
    assert p_w == 535 - 45
    assert n_w == 700 - 45

    # 3. Disable bookmarks (60px + 5px spacing = 65px reduction)
    without_bm = all_keys - {"bookmarks"}
    p_w, n_w = window.calculate_player_min_width(without_bm)
    assert p_w == 535 - 65
    assert n_w == 700 - 65

    # 4. Disable id3 and bookmarks (45 + 65 = 110px reduction)
    without_both = all_keys - {"id3", "bookmarks"}
    p_w, n_w = window.calculate_player_min_width(without_both)
    assert p_w == 535 - 110
    assert n_w == 700 - 110

    # 5. Disable all buttons -> clamped to min floor 280 and 450
    p_w, n_w = window.calculate_player_min_width(set())
    assert p_w == 280
    assert n_w == 450


def test_apply_player_buttons_settings(qapp):
    class DummyWindow:
        calculate_player_min_width = AudiobookPlayerWindow.calculate_player_min_width
        apply_player_buttons_settings = AudiobookPlayerWindow.apply_player_buttons_settings
        get_minimal_height = lambda self: 270
        normal_min_height = 450
        setMinimumSize = lambda self, w, h: None

    window = DummyWindow()
    window.player_widget = PlayerWidget()

    # Apply all buttons visible
    window.apply_player_buttons_settings(DEFAULT_PLAYER_BUTTONS_ORDER, DEFAULT_PLAYER_BUTTONS_VISIBLE)
    assert window.minimal_width == 535
    assert window.normal_min_width == 700
    assert window.player_widget.minimumWidth() == 535
    assert window.player_widget.action_buttons["id3"].isHidden() is False

    # Disable id3: should reduce minimum width by 45px (to 490px)
    without_id3_visible = DEFAULT_PLAYER_BUTTONS_VISIBLE.replace("id3,", "")
    window.apply_player_buttons_settings(DEFAULT_PLAYER_BUTTONS_ORDER, without_id3_visible)
    assert window.minimal_width == 490
    assert window.normal_min_width == 655
    assert window.player_widget.minimumWidth() == 490
    assert window.player_widget.action_buttons["id3"].isHidden() is True


def test_separator_in_dialog_and_layout(qapp):
    assert "separator" in DEFAULT_PLAYER_BUTTONS_ORDER

    dialog = AppearanceDialog(
        parent=None,
        player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        default_player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
        default_player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
    )

    # Find separator item in dialog
    sep_row = -1
    for r in range(dialog.buttons_list_widget.count()):
        item = dialog.buttons_list_widget.item(r)
        if item.data(Qt.ItemDataRole.UserRole) == "separator":
            sep_row = r
            # Separator must not be checkable
            assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            break

    assert sep_row != -1

    # Verify PlayerWidget btns_row has QSpacerItem at separator index
    player = PlayerWidget()
    player.update_buttons_layout(["timer", "id3", "separator", "volume_boost", "mono"], {"timer": True, "id3": True, "volume_boost": True, "mono": True})

    # Indices in btns_row:
    # 0: timer widget
    # 1: id3 widget
    # 2: QSpacerItem (stretch)
    # 3: volume_boost widget
    # 4: mono widget
    assert player.btns_row.itemAt(0).widget() == player.action_buttons["timer"]
    assert player.btns_row.itemAt(1).widget() == player.action_buttons["id3"]
    assert player.btns_row.itemAt(2).spacerItem() is not None
    assert player.btns_row.itemAt(3).widget() == player.action_buttons["volume_boost"]
    assert player.btns_row.itemAt(4).widget() == player.action_buttons["mono"]


def test_buttons_list_widget_styling_and_height(qapp):
    dialog = AppearanceDialog(
        parent=None,
        player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        default_player_buttons_order=DEFAULT_PLAYER_BUTTONS_ORDER,
        player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
        default_player_buttons_visible=DEFAULT_PLAYER_BUTTONS_VISIBLE,
    )
    assert dialog.buttons_list_widget.objectName() == "buttonsListWidget"
    dialog.adjust_buttons_list_height()
    # Ensure height is positive and calculated
    assert dialog.buttons_list_widget.height() >= 150



