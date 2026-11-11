import sys
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from player import PlayerWidget
from translations import set_language


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_timer_button_presence_and_position(qapp):
    set_language("en")
    widget = PlayerWidget()

    # Verify timer_btn exists and is configured
    assert hasattr(widget, "timer_btn")
    assert widget.timer_btn.objectName() == "timerBtn"
    assert widget.timer_btn.isCheckable() is True

    # Check horizontal position: timer_btn is to the left of id3_btn
    assert widget.timer_btn.x() <= widget.id3_btn.x()
    # Alternatively find common parent layout
    parent_layout = None
    for layout in widget.findChildren(QApplication.instance().__class__ if False else object):
        pass
    
    # Check by inspecting the buttons' parent layout directly
    btn_parent = widget.id3_btn.parentWidget()
    found_timer_idx = -1
    found_id3_idx = -1
    def search_layout(l):
        nonlocal found_timer_idx, found_id3_idx
        for i in range(l.count()):
            it = l.itemAt(i)
            if it.widget() is widget.timer_btn:
                found_timer_idx = i
            elif it.widget() is widget.id3_btn:
                found_id3_idx = i
            elif it.layout():
                search_layout(it.layout())

    search_layout(btn_parent.layout())
    assert found_timer_idx != -1
    assert found_id3_idx != -1
    assert found_timer_idx < found_id3_idx, "timer_btn must be to the left of id3_btn"


def test_timer_slider_range_and_popup(qapp):
    widget = PlayerWidget()
    assert hasattr(widget, "timer_popup")
    assert hasattr(widget, "timer_slider")
    assert hasattr(widget, "timer_chapter_btn")

    # Slider range must be 1 to 90 minutes
    assert widget.timer_slider.minimum() == 1
    assert widget.timer_slider.maximum() == 90

    # Changing slider emits signal
    emitted_mins = []
    widget.timer_minutes_changed_signal.connect(lambda val: emitted_mins.append(val))
    widget.timer_slider.setValue(45)
    assert 45 in emitted_mins
    assert widget.timer_minutes == 45
    assert widget.timer_mode == "minutes"
    assert widget.timer_btn.isChecked() is True

    # Chapter button sets mode
    emitted_modes = []
    widget.timer_mode_changed_signal.connect(lambda m: emitted_modes.append(m))
    widget.timer_chapter_btn.click()
    assert "end_of_chapter" in emitted_modes
    assert widget.timer_mode == "end_of_chapter"


def test_timer_button_toggle(qapp):
    widget = PlayerWidget()
    toggled_states = []
    widget.timer_toggled_signal.connect(lambda state: toggled_states.append(state))

    # Click to toggle on - should NOT show popup
    widget.timer_popup.hide()
    widget.timer_btn.setChecked(True)
    widget.timer_btn.clicked.emit()
    assert True in toggled_states
    assert widget.timer_popup.isVisible() is False

    # Right-click context menu - SHOULD show popup
    widget.timer_btn.customContextMenuRequested.emit(widget.timer_btn.rect().center())
    assert widget.timer_popup.isVisible() is True
    widget.timer_popup.hide()

    # Click to toggle off
    widget.timer_btn.setChecked(False)
    widget.timer_btn.clicked.emit()
    assert False in toggled_states
