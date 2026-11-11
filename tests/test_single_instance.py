import os
import sys
import ctypes
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QWidget
import pytest

from single_instance import SingleInstanceManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_mutex_name_includes_app_id_and_username(qapp):
    with patch.dict("os.environ", {"USERNAME": "test_user"}):
        mgr = SingleInstanceManager(app_id="TestApp")
        assert "TestApp" in mgr.mutex_name
        assert "test_user" in mgr.mutex_name


def test_is_already_running_lifecycle(qapp):
    app_id = "TestLifecycle_AppUnique"
    mgr1 = SingleInstanceManager(app_id=app_id)
    assert mgr1.is_already_running() is False

    mgr2 = SingleInstanceManager(app_id=app_id)
    assert mgr2.is_already_running() is True

    # After cleanup of mgr1, a new manager should be able to run
    mgr1.cleanup()

    mgr3 = SingleInstanceManager(app_id=app_id)
    assert mgr3.is_already_running() is False
    mgr3.cleanup()


def test_activate_window_calls_qt_methods(qapp):
    mock_window = MagicMock(spec=QWidget)
    mock_window.isMinimized.return_value = True

    with patch("sys.platform", "other_os"):
        SingleInstanceManager.activate_window(mock_window)

    mock_window.showNormal.assert_called_once()
    mock_window.raise_.assert_called_once()
    mock_window.activateWindow.assert_called_once()


def test_activate_window_not_minimized(qapp):
    mock_window = MagicMock(spec=QWidget)
    mock_window.isMinimized.return_value = False

    with patch("sys.platform", "other_os"):
        SingleInstanceManager.activate_window(mock_window)

    mock_window.showNormal.assert_not_called()
    mock_window.show.assert_called_once()
    mock_window.raise_.assert_called_once()
    mock_window.activateWindow.assert_called_once()


def test_activate_window_none():
    SingleInstanceManager.activate_window(None)


def test_get_show_message_id_returns_int():
    msg_id = SingleInstanceManager.get_show_message_id("TestApp")
    if sys.platform == "win32":
        assert isinstance(msg_id, int)
        assert msg_id > 0
    else:
        assert msg_id == 0


def test_taskbar_event_filter_handles_single_instance_message(qapp):
    from main import TaskbarEventFilter
    mock_window = MagicMock()
    mock_window.hotkey_manager.handle_native_event.return_value = False

    event_filter = TaskbarEventFilter(mock_window)

    msg_id = SingleInstanceManager.get_show_message_id()
    if sys.platform == "win32" and msg_id:
        msg = ctypes.wintypes.MSG()
        msg.message = msg_id

        with patch.object(SingleInstanceManager, "activate_window") as mock_activate:
            # Pass pointer to MSG
            res, ret = event_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
            assert res is True
            mock_activate.assert_called_once_with(mock_window)

