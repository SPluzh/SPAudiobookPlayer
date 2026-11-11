import os
import sys
import ctypes
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

ERROR_ALREADY_EXISTS = 183
HWND_BROADCAST = 0xFFFF
MSGFLT_ADD = 1


class SingleInstanceManager(QObject):
    """
    Manages single-instance application lifecycle using native Windows Mutex and Messages.
    Ensures only one instance of the player runs per Windows user session without depending
    on external Qt network modules.
    """

    message_received = pyqtSignal(str)
    _show_message_id: Optional[int] = None

    def __init__(self, app_id: str = "SPAudiobookPlayer", parent: Optional[QObject] = None):
        super().__init__(parent)
        username = os.environ.get("USERNAME", "default_user")
        self.app_id = app_id
        self.mutex_name = f"Local\\{app_id}_{username}_Mutex"
        self.message_name = f"{app_id}_{username}_ShowMessage"
        self.mutex_handle = None

    @classmethod
    def get_show_message_id(cls, app_id: str = "SPAudiobookPlayer") -> int:
        """Returns the registered Windows message ID used to notify the running instance."""
        if cls._show_message_id is None:
            if sys.platform == "win32":
                try:
                    username = os.environ.get("USERNAME", "default_user")
                    message_name = f"{app_id}_{username}_ShowMessage"
                    msg_id = ctypes.windll.user32.RegisterWindowMessageW(message_name)
                    # Allow this message to pass through UIPI (User Interface Privilege Isolation)
                    try:
                        ctypes.windll.user32.ChangeWindowMessageFilter(msg_id, MSGFLT_ADD)
                    except Exception:
                        pass
                    cls._show_message_id = msg_id
                except Exception:
                    cls._show_message_id = 0
            else:
                cls._show_message_id = 0
        return cls._show_message_id

    def is_already_running(self) -> bool:
        """
        Attempts to create a named mutex.
        If the mutex already exists, broadcasts the show message and returns True.
        If it's the first instance, holds the mutex handle and returns False.
        """
        if sys.platform != "win32":
            return False

        try:
            self.mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.mutex_name)
            last_error = ctypes.windll.kernel32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                # Another instance is already running
                self._allow_set_foreground_window()
                self._notify_running_instance()
                if self.mutex_handle:
                    ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
                    self.mutex_handle = None
                return True

            return False
        except Exception as e:
            print(f"Error checking single instance: {e}")
            return False

    def _notify_running_instance(self):
        """Broadcasts registered window message to activate the running instance."""
        try:
            msg_id = self.get_show_message_id(self.app_id)
            if msg_id:
                ctypes.windll.user32.PostMessageW(HWND_BROADCAST, msg_id, 0, 0)
        except Exception as e:
            print(f"Error notifying running instance: {e}")

    def cleanup(self):
        """Releases the mutex handle upon application termination."""
        if self.mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            except Exception:
                pass
            self.mutex_handle = None

    @staticmethod
    def _allow_set_foreground_window():
        """
        Grants permission to any process to bring their window to the foreground.
        This allows the already running instance to reliably take focus in Windows 10/11.
        """
        if sys.platform == "win32":
            try:
                # ASFW_ANY = -1 (0xFFFFFFFF)
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass

    @staticmethod
    def activate_window(window):
        """
        Brings the specified QWidget/QMainWindow to the foreground and focuses it,
        restoring it from minimized/hidden state if necessary.
        """
        if not window:
            return

        # Restore Qt window states
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()

        window.raise_()
        window.activateWindow()

        # Native Windows foreground restoration
        if sys.platform == "win32":
            try:
                hwnd = int(window.winId())
                if hwnd:
                    user32 = ctypes.windll.user32
                    # SW_RESTORE = 9, SW_SHOW = 5
                    if user32.IsIconic(hwnd):
                        user32.ShowWindow(hwnd, 9)
                    else:
                        user32.ShowWindow(hwnd, 5)

                    user32.SetForegroundWindow(hwnd)
            except Exception as e:
                print(f"Error bringing window to foreground: {e}")
