from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QObject
import ctypes
from ctypes import wintypes

# Windows-specific constants for multimedia keys (WM_APPCOMMAND)
WM_APPCOMMAND = 0x0319
WM_HOTKEY = 0x0312

# Multimedia commands (via WM_APPCOMMAND)
APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14
APPCOMMAND_MEDIA_PLAY = 46
APPCOMMAND_MEDIA_PAUSE = 47

# Virtual key codes (via WM_HOTKEY)
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# Hotkey IDs
HOTKEY_ID_PLAY_PAUSE = 101
HOTKEY_ID_NEXT = 102
HOTKEY_ID_PREV = 103
HOTKEY_ID_STOP = 104

# Load User32 for HotKey functions
user32 = ctypes.windll.user32

class HotKeyManager(QObject):
    """
    Manages application-wide hotkeys and global multimedia keys.
    """
    def __init__(self, window):
        """
        Initialize the hotkey manager.
        
        Args:
            window: The main application window (AudiobookPlayerWindow)
        """
        super().__init__()
        self.window = window
        self.setup_shortcuts()
        self.register_global_hotkeys()

    def register_global_hotkeys(self):
        """Registers multimedia keys as global hotkeys to work even when not in focus."""
        hwnd = int(self.window.winId())
        # We don't check results here to avoid crashing if another app already registered them
        user32.RegisterHotKey(hwnd, HOTKEY_ID_PLAY_PAUSE, 0, VK_MEDIA_PLAY_PAUSE)
        user32.RegisterHotKey(hwnd, HOTKEY_ID_NEXT, 0, VK_MEDIA_NEXT_TRACK)
        user32.RegisterHotKey(hwnd, HOTKEY_ID_PREV, 0, VK_MEDIA_PREV_TRACK)
        user32.RegisterHotKey(hwnd, HOTKEY_ID_STOP, 0, VK_MEDIA_STOP)

    def unregister_all(self):
        """Unregisters all global hotkeys."""
        hwnd = int(self.window.winId())
        user32.UnregisterHotKey(hwnd, HOTKEY_ID_PLAY_PAUSE)
        user32.UnregisterHotKey(hwnd, HOTKEY_ID_NEXT)
        user32.UnregisterHotKey(hwnd, HOTKEY_ID_PREV)
        user32.UnregisterHotKey(hwnd, HOTKEY_ID_STOP)

    def setup_shortcuts(self):
        """
        Configures keyboard shortcuts that work when the application is in focus.
        """
        # Play/Pause: Space
        self.shortcut_play_pause = QShortcut(QKeySequence(Qt.Key.Key_Space), self.window)
        self.shortcut_play_pause.activated.connect(self.window.toggle_play)

        # Skip to Next/Previous File: [ and ]
        self.shortcut_prev_file = QShortcut(QKeySequence(Qt.Key.Key_BracketLeft), self.window)
        self.shortcut_prev_file.activated.connect(self.window.on_prev_clicked)
        
        self.shortcut_next_file = QShortcut(QKeySequence(Qt.Key.Key_BracketRight), self.window)
        self.shortcut_next_file.activated.connect(self.window.on_next_clicked)

        # Seek: Left/Right Arrows (10s), Shift + Left/Right (60s)
        self.shortcut_rewind_10 = QShortcut(QKeySequence(Qt.Key.Key_Left), self.window)
        self.shortcut_rewind_10.activated.connect(lambda: self.window.player.rewind(-10))
        
        self.shortcut_forward_10 = QShortcut(QKeySequence(Qt.Key.Key_Right), self.window)
        self.shortcut_forward_10.activated.connect(lambda: self.window.player.rewind(10))

        self.shortcut_rewind_60 = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Left), self.window)
        self.shortcut_rewind_60.activated.connect(lambda: self.window.player.rewind(-60))
        
        self.shortcut_forward_60 = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Right), self.window)
        self.shortcut_forward_60.activated.connect(lambda: self.window.player.rewind(60))

        # Playback Speed: Up/Down Arrows (0.1x steps)
        self.shortcut_speed_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self.window)
        self.shortcut_speed_up.activated.connect(self.speed_up)
        
        self.shortcut_speed_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self.window)
        self.shortcut_speed_down.activated.connect(self.speed_down)

        # Volume: Shift + Up/Down Arrows (5% steps)
        self.shortcut_volume_up = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Up), self.window)
        self.shortcut_volume_up.activated.connect(self.volume_up)
        
        self.shortcut_volume_down = QShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Down), self.window)
        self.shortcut_volume_down.activated.connect(self.volume_down)

    def speed_up(self):
        """Increments playback speed by 0.1x"""
        current_speed = self.window.player_widget.speed_slider.value()
        self.window.player_widget.speed_slider.setValue(min(30, current_speed + 1))

    def speed_down(self):
        """Decrements playback speed by 0.1x"""
        current_speed = self.window.player_widget.speed_slider.value()
        self.window.player_widget.speed_slider.setValue(max(5, current_speed - 1))

    def volume_up(self):
        """Increments volume by 5%"""
        current_vol = self.window.player_widget.volume_slider.value()
        self.window.player_widget.volume_slider.setValue(min(100, current_vol + 5))

    def volume_down(self):
        """Decrements volume by 5%"""
        current_vol = self.window.player_widget.volume_slider.value()
        self.window.player_widget.volume_slider.setValue(max(0, current_vol - 5))

    def handle_native_event(self, msg):
        """
        Handles Windows-native events for multimedia keys (both in-focus and global).
        
        Args:
            msg: The Windows MSG structure
            
        Returns:
            bool: True if the event was handled, False otherwise
        """
        if msg.message == WM_APPCOMMAND:
            # The command is in the high word of the lParam
            command = (msg.lParam >> 16) & 0xFFFF
            return self.process_command(command)
        
        elif msg.message == WM_HOTKEY:
            # The hotkey ID is in the wParam
            hotkey_id = msg.wParam
            if hotkey_id == HOTKEY_ID_PLAY_PAUSE:
                self.window.toggle_play()
                return True
            elif hotkey_id == HOTKEY_ID_NEXT:
                self.window.player.rewind(10)
                return True
            elif hotkey_id == HOTKEY_ID_PREV:
                self.window.player.rewind(-10)
                return True
            elif hotkey_id == HOTKEY_ID_STOP:
                if self.window.player.is_playing():
                    self.window.toggle_play()
                return True
                
        return False

    def process_command(self, command):
        """Processes an APPCOMMAND value originating from WM_APPCOMMAND."""
        if command == APPCOMMAND_MEDIA_PLAY_PAUSE:
            self.window.toggle_play()
            return True
        elif command == APPCOMMAND_MEDIA_PLAY:
            if not self.window.player.is_playing():
                self.window.toggle_play()
            return True
        elif command == APPCOMMAND_MEDIA_PAUSE:
            if self.window.player.is_playing():
                self.window.toggle_play()
            return True
        elif command == APPCOMMAND_MEDIA_STOP:
            if self.window.player.is_playing():
                self.window.toggle_play()
            return True
        elif command == APPCOMMAND_MEDIA_NEXTTRACK:
            self.window.player.rewind(10)
            return True
        elif command == APPCOMMAND_MEDIA_PREVTRACK:
            self.window.player.rewind(-10)
            return True
        return False
