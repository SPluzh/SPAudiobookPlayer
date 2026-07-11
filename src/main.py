import sys
import os
import io
import subprocess
import sqlite3
import configparser
import update_ffmpeg
import threading
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

ROOT_DIR = Path(__file__).parent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QApplication,
    QMessageBox,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QStyle,
    QPushButton,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QFileDialog,
    QSlider,
    QProgressBar,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QTextEdit,
    QSizePolicy,
    QGraphicsBlurEffect,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QSize,
    pyqtSignal,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    QThread,
    QByteArray,
    QUrl,
)
from PyQt6.QtGui import (
    QIcon,
    QAction,
    QPixmap,
    QBrush,
    QColor,
    QFont,
    QPen,
    QPainter,
    QPolygon,
    QTextCursor,
    QPainterPath,
    QFontMetrics,
    QDesktopServices,
)
from bass_player import BassPlayer
from database import DatabaseManager
from styles import StyleManager
from taskbar_progress import TaskbarProgress, TaskbarThumbnailButtons
import ctypes
from ctypes import wintypes
from hotkeys import HotKeyManager
from player import PlayerWidget, PlaybackController
from bookmarks_dialog import BookmarksListDialog, BookmarkEditorDialog
from settings_dialog import SettingsDialog
from translations import (
    tr,
    trf,
    get_available_languages,
    get_language,
    set_language,
    Language,
)
from utils import (
    get_base_path,
    get_icon,
    load_icon,
    resize_icon,
    format_duration,
    format_time,
    format_time_short,
    format_size,
    OutputCapture,
    set_icon_color,
    set_icon_stroke_width,
)
from player import PlaybackController, PlayerWidget
from listening_tracker import ListeningTracker
from library import (
    ScannerThread,
    ScanProgressDialog,
    LibraryTree,
    MultiLineDelegate,
    LibraryWidget,
    CopyThread,
)
from about_dialog import AboutDialog
from update_dialog import UpdateCheckThread, UpdateDialog
from updater import get_current_version


class AudiobookPlayerWindow(QMainWindow):
    status_requested = pyqtSignal(str)

    def __init__(self):
        """Initialize the main application window, establishing directory structures, loading configurations, and assembling core components"""
        super().__init__()

        # Filesystem path orchestration
        self.script_dir = get_base_path()
        self.config_dir = self.script_dir / "resources"
        self.data_dir = self.script_dir / "data"

        self.config_file = self.config_dir / "settings.ini"
        self.db_file = self.data_dir / "audiobooks.db"
        self.icons_dir = self.config_dir / "icons"

        # Ensure requisite directories exist for persistent storage
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Auto-rewind state tracking
        self.auto_rewind = False
        self.deesser_enabled = False
        self.compressor_enabled = False
        self.noise_suppression_enabled = False
        self.vad_threshold = 90  # Default 90% (0-100)
        self.vad_grace_period = 0  # Default 0 (0-100)
        self.vad_retroactive_grace = 0  # Default 0 (0-100)
        self.deesser_preset = 1  # 0=Light, 1=Medium, 2=Strong
        self.compressor_preset = 1  # 0=Light, 1=Medium, 2=Strong
        self.pitch_enabled = False
        self.pitch_value = 0.0
        self.mono_enabled = False
        self.last_pause_time = None
        self.show_visualizer = True
        self.show_nesting_lines = True
        self.nesting_lines_single_color = False
        self.nesting_lines_color = "#808080"
        self.show_detailed_info = True
        self.show_status_triangle = True
        self.show_statusbar = True
        self.show_subtitles = False
        
        # Book info settings
        self.show_info_progress = True
        self.show_info_file_count = True
        self.show_info_duration = True
        self.show_info_size = True
        self.show_info_technical = True
        self.show_info_year_written = True
        self.show_info_year_recorded = True
        self.show_info_language = True
        self.info_order = "progress,file_count,duration,size,technical,year_written,year_recorded,language"
        self.normal_geometry = None
        self.normal_splitter_state = None
        self.always_on_top = False
        self.remember_filter_folders = True
        self.library_show_folders = {
            "all": False,
            "not_started": False,
            "in_progress": False,
            "completed": False,
        }

        # Load user configurations and localization settings
        self.db_manager = DatabaseManager(self.db_file)
        self.player = BassPlayer()

        self.load_settings()
        self.load_language_preference()

        # Configure window aesthetics
        self.setWindowTitle(tr("window.title"))
        self.setWindowIcon(get_icon("app_icon", self.icons_dir))

        # Dependency Injection and Component Instantiation
        self.playback_controller = PlaybackController(self.player, self.db_manager)
        if self.default_path:
            self.playback_controller.library_root = Path(self.default_path)

        # Initialize listening tracker for statistics
        self.listening_tracker = ListeningTracker(self.db_manager)
        self.playback_controller.listening_tracker = self.listening_tracker
        self.playback_controller.on_load_start = self.on_stream_load_start
        self.playback_controller.on_load_error = self.on_stream_load_error
        self.playback_controller.on_status_update = self._on_playback_status
        self.status_requested.connect(self.statusBar().showMessage)

        self.taskbar_progress = TaskbarProgress()

        # UI Presentation Delegate Initialization
        self.delegate = None
        try:
            self.delegate = MultiLineDelegate(self)
            self.delegate.audiobook_row_height = self.audiobook_row_height
            self.delegate.folder_row_height = self.folder_row_height
            self.delegate.audiobook_icon_size = self.audiobook_icon_size
            self.delegate.show_nesting_lines = self.show_nesting_lines
            self.delegate.nesting_lines_single_color = self.nesting_lines_single_color
            self.delegate.nesting_lines_color = self.nesting_lines_color
            self.delegate.show_detailed_info = self.show_detailed_info
            self.delegate.show_status_triangle = self.show_status_triangle
            self.delegate.show_info_progress = self.show_info_progress
            self.delegate.show_info_file_count = self.show_info_file_count
            self.delegate.show_info_duration = self.show_info_duration
            self.delegate.show_info_size = self.show_info_size
            self.delegate.show_info_technical = self.show_info_technical
            self.delegate.show_info_year_written = self.show_info_year_written
            self.delegate.show_info_year_recorded = self.show_info_year_recorded
            self.delegate.show_info_language = self.show_info_language
            self.delegate.info_order = self.info_order
        except Exception as e:
            print(f"Failed to create delegate: {e}")

        # Interface assembly and event mapping
        self.setup_ui()
        self.setup_menu()
        self.connect_signals()

        # Initialize hotkey manager for keyboard shortcuts and multimedia keys
        self.hotkey_manager = HotKeyManager(self)

        # Data hydration and session recovery
        self.library_widget.load_audiobooks()
        self.restore_last_session()

        # Periodic UI synchronization timer (e.g., for playback position)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)

        # Window geometry restoration
        display_restored = False
        if self.saved_geometry_hex:
            display_restored = self.restoreGeometry(
                QByteArray.fromHex(self.saved_geometry_hex.encode())
            )

        if not display_restored:
            # Fallback to manual coordinates, but ensure they are sane
            # Fix potential "creeping" issues from previous bugs where coordinates became negative or zero
            safe_x = max(0, self.window_x)
            safe_y = max(30, self.window_y)  # Ensure title bar is likely visible
            safe_width = max(550, self.window_width)
            safe_height = max(450, self.window_height)
            self.setGeometry(safe_x, safe_y, safe_width, safe_height)

        # Final Safety Check: Ensure window is actually visible on the screen
        # This catches cases where restored geometry might be on a disconnected monitor
        # or if calculations were still wrong.
        screen_geo = self.screen().availableGeometry()
        frame_geo = self.frameGeometry()

        # If the top-left corner is completely out of bounds or the title bar is cut off
        if not screen_geo.intersects(frame_geo) or frame_geo.top() < screen_geo.top():
            # Reset to center of screen
            center_point = screen_geo.center()
            frame_geo.moveCenter(center_point)
            self.move(frame_geo.topLeft())

        # Apply final size constraints and force minimal dimension if active
        if getattr(self, "minimal_interface", False):
            self.setMinimumSize(self.minimal_width, self.minimal_height)
            self.resize(self.minimal_width, self.minimal_height)
        else:
            self.setMinimumSize(self.normal_min_width, self.normal_min_height)

        if self.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        if not self.playback_controller.current_audiobook_path:
            self.statusBar().showMessage(tr("status.load_library"))

        # Blur Effect Stacking logic to handle nested modal dialogs
        self._blur_count = 0

        # Drop Overlay
        self.drop_overlay = QLabel(
            tr("window.drop_files") + "\n\n" + tr("window.drop_hint"), self
        )
        self.drop_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_overlay.setObjectName("dropOverlay")
        self.drop_overlay.hide()
        self.drop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._blur_effect = None

        # Ensure the main window has focus so hotkeys work correctly
        # Ensure the main window has focus so hotkeys work correctly
        self.setFocus()

        # Enable Drag and Drop
        self.setAcceptDrops(True)

        # Auto-check for updates on startup (delayed)
        QTimer.singleShot(3000, self.check_for_updates_auto)

    def load_language_preference(self):
        """Retrieve and apply the user's preferred application language from the configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        lang_code = config.get("Display", "language", fallback="ru")

        # Verify language code exists in available languages
        available_codes = [lang[0] for lang in get_available_languages()]
        if lang_code in available_codes:
            set_language(lang_code)
        else:
            set_language(Language.RUSSIAN)

    def save_language_preference(self):
        """Commit the current language setting to the persistent configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        if "Display" not in config:
            config["Display"] = {}

        config["Display"]["language"] = get_language()

        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

    def setup_ui(self):
        """Build the top-level interface structure using a splitter to contain the library and player widgets"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Horizontal Splitter for layout flexibility
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(True)

        # Audiobook Library Component
        self.library_widget = LibraryWidget(
            self.db_manager,
            {
                "audiobook_icon_size": self.audiobook_icon_size,
                "folder_icon_size": self.folder_icon_size,
                "default_cover_file": self.default_cover_file,
                "folder_cover_file": self.folder_cover_file,
                "default_path": self.default_path,
                "ffprobe_path": self.ffprobe_path,
                "tag_filter_active": self.tag_filter_active,
                "tag_filter_ids": self.tag_filter_ids,
                "meta_filter_active": self.meta_filter_active,
                "current_meta_filter": self.current_meta_filter,
                "filter_mode": self.library_filter_mode,
                "favorites_active": self.library_favorites_active,
                "sort_orders": self.library_sort_orders,
                "sort_fields": self.library_sort_fields,
                "remember_filter_folders": self.remember_filter_folders,
                "show_folders_by_filter": self.library_show_folders,
                "opus_workers": self.opus_workers,
                "tile_view": self.library_tile_view,
                "show_nesting_lines": self.show_nesting_lines,
                "nesting_lines_single_color": self.nesting_lines_single_color,
                "nesting_lines_color": self.nesting_lines_color,
            },
            self.delegate,
            show_folders=self.show_folders,
            show_filter_labels=self.show_filter_labels,
        )
        self.library_widget.show_status_triangle = self.show_status_triangle
        self.library_widget.nesting_lines_single_color = self.nesting_lines_single_color
        self.library_widget.nesting_lines_color = self.nesting_lines_color
        self.library_widget.setMinimumWidth(200)
        self.splitter.addWidget(self.library_widget)

        # Playback Controls Component
        self.player_widget = PlayerWidget()
        self.player_widget.setMinimumWidth(490)
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.on_id3_toggled(self.show_id3)

        self.player_widget.id3_toggled_signal.connect(self.on_id3_state_toggled)

        self.player_widget.auto_rewind_toggled_signal.connect(
            self.on_auto_rewind_state_toggled
        )

        self.player_widget.deesser_toggled_signal.connect(self.on_deesser_state_toggled)

        self.player_widget.compressor_toggled_signal.connect(
            self.on_compressor_state_toggled
        )

        self.player_widget.noise_suppression_toggled_signal.connect(
            self.on_noise_suppression_state_toggled
        )

        self.player_widget.pitch_toggled_signal.connect(self.on_pitch_toggled)
        self.player_widget.pitch_changed_signal.connect(self.on_pitch_changed)
        self.player_widget.mono_toggled_signal.connect(self.on_mono_toggled)
        self.player_widget.volume_boost_toggled_signal.connect(self.player.set_volume_boost)
        self.player_widget.volume_boost_level_changed_signal.connect(self.player.set_volume_boost_level)

        # VAD threshold slider
        self.player_widget.vad_threshold_changed_signal.connect(
            self.on_vad_threshold_changed
        )

        # VAD grace period sliders
        self.player_widget.vad_grace_period_changed_signal.connect(
            self.on_vad_grace_period_changed
        )
        self.player_widget.vad_retroactive_grace_changed_signal.connect(
            self.on_vad_retro_grace_changed
        )

        # DeEsser & Compressor Presets
        self.player_widget.deesser_preset_changed_signal.connect(
            self.on_deesser_preset_changed
        )
        self.player_widget.compressor_preset_changed_signal.connect(
            self.on_compressor_preset_changed
        )

        # Set initial states
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.auto_rewind_btn.setChecked(self.auto_rewind)
        self.player_widget.deesser_btn.setChecked(self.deesser_enabled)
        self.player_widget.compressor_btn.setChecked(self.compressor_enabled)
        self.player_widget.noise_suppression_btn.setChecked(
            self.noise_suppression_enabled
        )
        self.player_widget.pitch_btn.setChecked(self.pitch_enabled)
        self.player_widget.mono_btn.setChecked(self.mono_enabled)
        self.player_widget.volume_boost_btn.setChecked(self.volume_boost_enabled)
        self.player_widget.set_volume_boost_level_value(self.volume_boost_level)
        self.player_widget.play_btn.visualizer_enabled = self.show_visualizer
        self.player_widget.subtitles_btn.setChecked(self.show_subtitles)
        self.player_widget._on_subtitles_toggled(self.show_subtitles)

        # Set initial values for sliders
        self.player_widget.set_vad_threshold_value(self.vad_threshold)
        self.player_widget.set_vad_grace_value(self.vad_grace_period)
        self.player_widget.set_vad_retro_value(self.vad_retroactive_grace)
        self.player_widget.set_deesser_preset_value(self.deesser_preset)
        self.player_widget.set_compressor_preset_value(self.compressor_preset)
        self.player_widget.set_pitch_value(self.pitch_value)

        self.splitter.addWidget(self.player_widget)

        main_layout.addWidget(self.splitter, 1)

        # Apply Minimal Interface state
        if getattr(self, "minimal_interface", False):
            self.setMinimumSize(self.minimal_width, self.minimal_height)
            self.library_widget.hide()
            self.player_widget.file_list.hide()
        else:
            self.setMinimumSize(self.normal_min_width, self.normal_min_height)

    def setup_menu(self):
        """Construct the main application menu bar, including Library, View, and Help menus with localized actions"""
        menubar = self.menuBar()

        library_menu = menubar.addMenu(tr("menu.library"))

        # Global Settings Context
        self.settings_action = QAction(tr("menu.settings"), self)
        self.settings_action.setIcon(get_icon("menu_settings"))
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.triggered.connect(self.show_settings)
        library_menu.addAction(self.settings_action)

        library_menu.addSeparator()

        # Directory Synchronization
        self.scan_action = QAction(tr("menu.scan"), self)
        self.scan_action.setIcon(get_icon("menu_scan"))
        self.scan_action.setShortcut("Ctrl+R")
        self.scan_action.triggered.connect(self.rescan_directory)
        library_menu.addAction(self.scan_action)

        library_menu.addSeparator()

        # Listening Statistics
        self.statistics_action = QAction(tr("menu.statistics"), self)
        self.statistics_action.setIcon(get_icon("statistics"))
        self.statistics_action.setShortcut("Ctrl+T")
        self.statistics_action.triggered.connect(self.show_statistics)
        library_menu.addAction(self.statistics_action)

        # Open Library Folder
        self.open_folder_action = QAction(tr("menu.open_library_folder"), self)
        self.open_folder_action.setIcon(get_icon("context_open_folder"))
        self.open_folder_action.triggered.connect(self.open_library_folder)

        view_menu = menubar.addMenu(tr("menu.view"))

        # Language Selection Nested Menu
        self.language_menu = view_menu.addMenu(tr("menu.language"))
        self.language_menu.setIcon(get_icon("languages"))

        available_langs = get_available_languages()
        self.language_actions = {}

        for code, name in available_langs:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(get_language() == code)
            # Use default argument to capture current loop variable
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            self.language_menu.addAction(action)
            self.language_actions[code] = action

        view_menu.addSeparator()

        # Library Visibility & Navigation
        self.reveal_action = QAction(tr("menu.reveal_current"), self)
        self.reveal_action.setIcon(get_icon("locate"))
        self.reveal_action.setShortcut("L")
        self.reveal_action.triggered.connect(self.reveal_current_audiobook)
        view_menu.addAction(self.reveal_action)

        self.expand_action = QAction(tr("menu.expand_all"), self)
        self.expand_action.setIcon(get_icon("expand"))
        self.expand_action.setShortcut("E")
        self.expand_action.triggered.connect(self.library_widget.expand_all_folders)
        view_menu.addAction(self.expand_action)

        self.collapse_action = QAction(tr("menu.collapse_all"), self)
        self.collapse_action.setIcon(get_icon("collapse"))
        self.collapse_action.setShortcut("W")
        self.collapse_action.triggered.connect(self.library_widget.collapse_all_folders)
        view_menu.addAction(self.collapse_action)

        view_menu.addSeparator()

        # Minimal Interface Toggle
        self.minimal_interface_action = QAction(tr("menu.minimal_interface"), self)
        self.minimal_interface_action.setCheckable(True)
        self.minimal_interface_action.setChecked(
            getattr(self, "minimal_interface", False)
        )
        self.minimal_interface_action.setShortcut("P")
        self.minimal_interface_action.triggered.connect(self.toggle_minimal_interface)
        view_menu.addAction(self.minimal_interface_action)

        # Always on Top Toggle
        self.always_on_top_action = QAction(tr("menu.always_on_top"), self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(self.always_on_top)
        self.always_on_top_action.setShortcut("T")
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        view_menu.addAction(self.always_on_top_action)

        # Define actions for settings compatibility and tests (not added to View menu)
        self.visualizer_action = QAction(tr("menu.visualizer", "Visualizer"), self)
        self.visualizer_action.setCheckable(True)
        self.visualizer_action.setChecked(self.show_visualizer)
        self.visualizer_action.triggered.connect(self.toggle_visualizer)

        self.nesting_lines_action = QAction(tr("menu.show_nesting_lines"), self)
        self.nesting_lines_action.setCheckable(True)
        self.nesting_lines_action.setChecked(self.show_nesting_lines)
        self.nesting_lines_action.triggered.connect(self.toggle_nesting_lines)

        self.show_status_triangle_action = QAction(tr("menu.show_status_triangle"), self)
        self.show_status_triangle_action.setCheckable(True)
        self.show_status_triangle_action.setChecked(self.show_status_triangle)
        self.show_status_triangle_action.triggered.connect(self.toggle_status_triangle)

        self.statusbar_action = QAction(tr("menu.show_statusbar"), self)
        self.statusbar_action.setCheckable(True)
        self.statusbar_action.setChecked(self.show_statusbar)
        self.statusbar_action.triggered.connect(self.toggle_statusbar)

        self.remember_filter_folders_action = QAction(tr("menu.remember_filter_folders"), self)
        self.remember_filter_folders_action.setCheckable(True)
        self.remember_filter_folders_action.setChecked(self.remember_filter_folders)
        self.remember_filter_folders_action.triggered.connect(self.toggle_remember_filter_folders)

        # Appearance Settings Action
        self.appearance_action = QAction(tr("appearance.title"), self)
        self.appearance_action.setIcon(get_icon("palette"))
        self.appearance_action.triggered.connect(self.show_appearance_settings)
        view_menu.addAction(self.appearance_action)

        help_menu = menubar.addMenu(tr("menu.help"))

        # Check for Updates
        self.check_update_action = QAction(tr("menu.check_updates"), self)
        self.check_update_action.setIcon(get_icon("update"))
        self.check_update_action.triggered.connect(self.check_for_updates_manual)
        help_menu.addAction(self.check_update_action)

        help_menu.addSeparator()

        # About Dialog Trigger
        self.about_action = QAction(tr("menu.about"), self)
        self.about_action.setIcon(get_icon("menu_about"))
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)

    def reload_icons(self):
        """Reload all SVG-based application icons to apply the new icon color"""
        self.setWindowIcon(get_icon("app_icon", self.icons_dir))
        if hasattr(self, "settings_action"):
            self.settings_action.setIcon(get_icon("menu_settings"))
        if hasattr(self, "scan_action"):
            self.scan_action.setIcon(get_icon("menu_scan"))
        if hasattr(self, "statistics_action"):
            self.statistics_action.setIcon(get_icon("statistics"))
        if hasattr(self, "open_folder_action"):
            self.open_folder_action.setIcon(get_icon("context_open_folder"))
        if hasattr(self, "language_menu"):
            self.language_menu.setIcon(get_icon("languages"))
        if hasattr(self, "reveal_action"):
            self.reveal_action.setIcon(get_icon("locate"))
        if hasattr(self, "expand_action"):
            self.expand_action.setIcon(get_icon("expand"))
        if hasattr(self, "collapse_action"):
            self.collapse_action.setIcon(get_icon("collapse"))
        if hasattr(self, "appearance_action"):
            self.appearance_action.setIcon(get_icon("palette"))
        if hasattr(self, "check_update_action"):
            self.check_update_action.setIcon(get_icon("update"))
        if hasattr(self, "about_action"):
            self.about_action.setIcon(get_icon("menu_about"))

        if hasattr(self, "player_widget") and self.player_widget:
            self.player_widget.load_icons()
        if hasattr(self, "library_widget") and self.library_widget:
            self.library_widget.load_icons()

    def change_language(self, language: str):
        """Update the application's language preference and immediately refresh all UI components without requiring a restart"""
        if get_language() == language:
            return

        set_language(language)
        self.save_language_preference()

        # Synchronize checkmarks in the language menu
        for lang, action in self.language_actions.items():
            action.setChecked(lang == language)

        # Propagate translation updates across the entire interface
        self.update_all_texts()

    def toggle_visualizer(self, checked: bool):
        """Toggle the audio spectrum visualization on the play button"""
        self.show_visualizer = checked
        if hasattr(self, "visualizer_action"):
            self.visualizer_action.setChecked(checked)
        if hasattr(self, "player_widget"):
            self.player_widget.play_btn.visualizer_enabled = checked
            self.player_widget.play_btn.update()
        self.save_settings()

    def toggle_nesting_lines(self, checked: bool):
        """Toggle the visibility of nesting lines in the library tree"""
        self.show_nesting_lines = checked
        if hasattr(self, "nesting_lines_action"):
            self.nesting_lines_action.setChecked(checked)
        if hasattr(self, "delegate") and self.delegate:
            self.delegate.show_nesting_lines = checked
            if hasattr(self, "library_widget"):
                self.library_widget.show_nesting_lines = checked
                self.library_widget.tree.viewport().update()
                if hasattr(self.library_widget, "tile_view") and self.library_widget.tile_view:
                    if hasattr(self.library_widget.tile_view, "canvas") and self.library_widget.tile_view.canvas:
                        self.library_widget.tile_view.canvas.update_layout()
                        self.library_widget.tile_view.canvas.update()
                    self.library_widget.tile_view.update()
        self.save_settings()


    def toggle_status_triangle(self, checked: bool):
        """Toggle the visibility of the book status corner triangle in the library tree"""
        self.show_status_triangle = checked
        if hasattr(self, "show_status_triangle_action"):
            self.show_status_triangle_action.setChecked(checked)
        if hasattr(self, "delegate") and self.delegate:
            self.delegate.show_status_triangle = checked
            if hasattr(self, "library_widget"):
                self.library_widget.show_status_triangle = checked
                self.library_widget.tree.viewport().update()
                if hasattr(self.library_widget, "tile_view") and self.library_widget.tile_view:
                    if hasattr(self.library_widget.tile_view, "canvas") and self.library_widget.tile_view.canvas:
                        self.library_widget.tile_view.canvas.update()
        self.save_settings()

    def toggle_minimal_interface(self, enabled: bool):
        """Toggle visibility of library and playlist for a minimized interface, resizing window accordingly"""
        self.minimal_interface = enabled
        if hasattr(self, "minimal_interface_action"):
            self.minimal_interface_action.setChecked(enabled)

        if enabled:
            # Save current geometry and splitter state before minimizing
            self.normal_geometry = self.saveGeometry().toHex().data().decode()
            if hasattr(self, "splitter"):
                self.normal_splitter_state = (
                    self.splitter.saveState().toHex().data().decode()
                )

            mh = 245 if not self.show_statusbar else self.minimal_height
            self.setMinimumSize(self.minimal_width, mh)

            # Hide widgets
            if hasattr(self, "library_widget"):
                self.library_widget.hide()
            if hasattr(self, "player_widget") and hasattr(
                self.player_widget, "file_list"
            ):
                self.player_widget.file_list.hide()

            # Resize window to fit remaining elements
            self.resize(self.minimal_width, mh)
        else:
            # Restore normal UI
            self.setMinimumSize(self.normal_min_width, self.normal_min_height)

            # Show widgets
            if hasattr(self, "library_widget"):
                self.library_widget.show()
            if hasattr(self, "player_widget") and hasattr(
                self.player_widget, "file_list"
            ):
                self.player_widget.file_list.show()

            # Restore saved geometry and splitter state if available
            if self.normal_geometry:
                self.restoreGeometry(QByteArray.fromHex(self.normal_geometry.encode()))
            if self.normal_splitter_state and hasattr(self, "splitter"):
                self.splitter.restoreState(
                    QByteArray.fromHex(self.normal_splitter_state.encode())
                )

        # Update settings
        self.save_settings()
        if hasattr(self, "taskbar_progress"):
            self.taskbar_progress.refresh_state()

    def toggle_always_on_top(self, enabled: bool):
        """Toggle the 'Always on Top' window state using standard Qt methods"""
        self.always_on_top = enabled
        if hasattr(self, "always_on_top_action"):
            self.always_on_top_action.setChecked(enabled)

        # Changing window flags at runtime in Qt usually requires re-showing the window
        # to ensure the desktop environment/window manager applies the change.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()
        if hasattr(self, "taskbar_progress"):
            self.taskbar_progress.refresh_state()

        self.save_settings()

    def toggle_statusbar(self, enabled: bool):
        """Toggle the visibility of the status bar"""
        self.show_statusbar = enabled
        self.statusBar().setVisible(enabled)
        if getattr(self, "minimal_interface", False):
            h = 270 if enabled else 245
            self.setMinimumSize(self.minimal_width, h)
            self.resize(self.minimal_width, h)
        self.save_settings()

    def toggle_remember_filter_folders(self, enabled: bool):
        """Toggle whether folder visibility is remembered per library filter"""
        self.remember_filter_folders = enabled
        if hasattr(self, "remember_filter_folders_action"):
            self.remember_filter_folders_action.setChecked(enabled)
        if hasattr(self, "library_widget"):
            self.library_widget.remember_filter_folders = enabled
            if enabled:
                current_filter = self.library_widget.current_filter
                self.library_widget.show_folders_by_filter[current_filter] = self.library_widget.show_folders
        self.save_settings()

    def update_all_texts(self):
        """Synchronize window titles, menus, and sub-widget labels after a language change event"""
        # Revise window title with localized formatting
        if (
            hasattr(self, "playback_controller")
            and self.playback_controller.current_audiobook_path
        ):
            book_title = self.playback_controller.get_audiobook_title()
            self.setWindowTitle(trf("window.title_with_book", title=book_title))
        else:
            self.setWindowTitle(tr("window.title"))

        # Update Drop Overlay
        self.drop_overlay.setText(
            tr("window.drop_files") + "\n\n" + tr("window.drop_hint")
        )

        # Reconstruct the menu bar to apply new translations
        self.menuBar().clear()
        self.setup_menu()
        if hasattr(self, "statusbar_action"):
            self.statusbar_action.setChecked(self.show_statusbar)

        # Refresh player controls
        if hasattr(self, "player_widget"):
            self.player_widget.update_texts()

        # Refresh library filters and search fields
        if hasattr(self, "library_widget"):
            self.library_widget.update_texts()

        # Reload the library tree to apply new delegate formatting
        if hasattr(self, "library_widget"):
            self.library_widget.load_audiobooks()

    def open_library_folder(self):
        """Open the current library folder in the system's default file manager"""
        path = self.default_path
        if not path:
            # Try to get from controller if default_path is not set but controller has root
            if (
                hasattr(self, "playback_controller")
                and self.playback_controller.library_root
            ):
                path = str(self.playback_controller.library_root)

        if path and os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(
                self, tr("error"), tr("status.no_database")
            )  # Using generic error or strictly "Path not found" if we had a key.
            # "status.no_database" says "Database not found...", maybe not perfect but close enough for "Library not set".
            # Better might be just a silent fail or console log if we want to be less obtrusive,
            # but user clicked a button so they expect something.
            # Let's check if we have a better key. "settings.specify_path" is "Specify path...".
            pass

    def show_statistics(self):
        """Open the listening statistics dialog"""
        from statistics_dialog import StatisticsDialog
        self.apply_blur()
        dialog = StatisticsDialog(self, self.db_manager)
        dialog.exec()
        self.remove_blur()

    def connect_signals(self):
        """Map signals from sub-widgets (Library and Player) to their respective handler methods in the main window"""
        # Library Navigation Signals
        self.library_widget.audiobook_selected.connect(self.on_audiobook_selected)
        self.library_widget.tree.play_button_clicked.connect(
            self.on_library_play_clicked
        )
        self.library_widget.show_folders_toggled.connect(self.on_show_folders_toggled)
        self.library_widget.sort_order_changed.connect(self.on_sort_order_changed)
        self.library_widget.delete_requested.connect(self.on_delete_requested)
        self.library_widget.folder_delete_requested.connect(
            self.on_folder_delete_requested
        )
        self.library_widget.scan_requested.connect(self.rescan_directory)
        self.library_widget.settings_requested.connect(self.show_settings)

        # Playback Control Signals
        # Playback Control Signals
        self.player_widget.play_clicked.connect(self.toggle_play)
        self.player_widget.next_clicked.connect(self.on_next_clicked)
        self.player_widget.prev_clicked.connect(self.on_prev_clicked)
        self.player_widget.rewind_clicked.connect(self.player.rewind)
        self.player_widget.position_changed.connect(self.on_position_changed)
        self.player_widget.volume_changed.connect(self.player.set_volume)
        self.player_widget.speed_changed.connect(self.on_speed_changed)
        self.player_widget.file_selected.connect(self.on_file_selected)
        self.player_widget.bookmarks_clicked.connect(self.show_bookmarks)
        self.player_widget.add_bookmark_clicked.connect(self.add_bookmark)
        self.player_widget.subtitles_toggled_signal.connect(self.on_subtitles_state_toggled)

    def show_bookmarks(self):
        """Open the bookmarks manager dialog"""
        if not self.playback_controller.current_audiobook_id:
            QMessageBox.information(
                self, tr("info"), tr("bookmarks.no_book_playing")
            )  # We might need a key for this or just fail silently/log.
            # Assuming we can just ignore if no book playing.
            return

        # Pause playback while managing bookmarks? iterating on user preference.
        # Let's keep it playing unless user wants to jump.
        # OR: capturing current position requires precision. If playing, it changes.
        # But we capture it at the moment of opening the dialog.

        current_pos = self.playback_controller.player.get_position()
        current_idx = self.playback_controller.current_file_index
        current_file = (
            self.playback_controller.files_list[current_idx]["name"]
            if self.playback_controller.files_list
            else ""
        )

        dlg = BookmarksListDialog(
            self,
            self.db_manager,
            self.playback_controller.current_audiobook_id,
            current_idx,
            current_file,
            current_pos,
        )

        dlg.bookmark_selected.connect(self.on_bookmark_selected)
        dlg.exec()
        self.update_progress_bar_markers()

    def add_bookmark(self):
        """Open the add bookmark dialog directly"""
        if not self.playback_controller.current_audiobook_id:
            QMessageBox.information(
                self, tr("info"), tr("bookmarks.no_book_playing")
            )
            return

        current_pos = self.playback_controller.player.get_position()
        current_idx = self.playback_controller.current_file_index
        current_file = (
            self.playback_controller.files_list[current_idx]["name"]
            if self.playback_controller.files_list
            else ""
        )

        from utils import format_time_short
        timestamp = format_time_short(current_pos)
        default_title = f"{tr('bookmarks.bookmark_at')} {timestamp}"

        dlg = BookmarkEditorDialog(
            self,
            title=default_title,
            description="",
            files_list=self.playback_controller.files_list,
            current_index=current_idx,
            position=current_pos
        )
        dlg.setWindowTitle(tr("bookmarks.add_title"))

        if dlg.exec() == QDialog.DialogCode.Accepted:
            title, desc = dlg.get_data()
            if not title:
                title = default_title

            self.db_manager.add_bookmark(
                self.playback_controller.current_audiobook_id,
                current_file,
                current_pos,
                title,
                desc
            )
            self.update_progress_bar_markers()

    def on_bookmark_selected(self, bookmark_id: int):
        """Handle jump to bookmark, ensuring UI and session state are updated"""
        if self.playback_controller.jump_to_bookmark(bookmark_id):
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
            self.save_last_session()
            self.refresh_audiobook_in_tree()

    def load_settings(self):
        """Retrieve and initialize application state (paths, window geometry, styles) from the 'settings.ini' file"""
        if not self.config_file.exists():
            self.create_default_settings()

        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        # Window Geometry Persistence
        self.window_x = config.getint("Display", "window_x", fallback=100)
        self.window_y = config.getint("Display", "window_y", fallback=100)
        self.window_width = config.getint("Display", "window_width", fallback=1200)
        self.window_height = config.getint("Display", "window_height", fallback=800)
        self.saved_geometry_hex = config.get(
            "Display", "window_geometry", fallback=None
        )
        self.normal_geometry = config.get("Display", "normal_geometry", fallback=None)
        self.normal_splitter_state = config.get(
            "Display", "normal_splitter_state", fallback=None
        )
        self.normal_min_width = max(750, config.getint(
            "Display", "normal_min_width", fallback=750
        ))
        self.normal_min_height = config.getint(
            "Display", "normal_min_height", fallback=450
        )
        self.minimal_width = max(550, config.getint("Display", "minimal_width", fallback=550))
        self.minimal_height = config.getint("Display", "minimal_height", fallback=270)
        self.current_theme = config.get("Display", "theme", fallback="dark")
        self.accent_color = config.get("Appearance", "accent_color", fallback="")
        self.window_color = config.get("Appearance", "window_color", fallback="")
        self.bg_dark_color = config.get("Appearance", "bg_dark_color", fallback="")
        self.text_color = config.get("Appearance", "text_color", fallback="")
        self.border_color = config.get("Appearance", "border_color", fallback="")
        self.status_new_color = config.get("Appearance", "status_new_color", fallback="")
        self.status_started_color = config.get("Appearance", "status_started_color", fallback="")
        self.status_completed_color = config.get("Appearance", "status_completed_color", fallback="")
        self.cover_progress_color = config.get("Appearance", "cover_progress_color", fallback="")
        self.icon_color = config.get("Appearance", "icon_color", fallback="")
        self.icon_thickness = config.getfloat("Appearance", "icon_thickness", fallback=2.0)
        set_icon_color(self.icon_color or "#cccccc")
        set_icon_stroke_width(self.icon_thickness)

        # Filesystem Path Configurations
        self.default_path = config.get("Paths", "default_path", fallback="")
        ff_path_str = config.get(
            "Paths",
            "ffprobe_path",
            fallback=str(self.script_dir / "resources" / "bin" / "ffprobe.exe"),
        )
        self.ffprobe_path = Path(ff_path_str)
        if not self.ffprobe_path.is_absolute():
            self.ffprobe_path = self.script_dir / self.ffprobe_path

        covers_dir_str = config.get(
            "Paths", "covers_dir", fallback="data/extracted_covers"
        )
        self.covers_dir = Path(covers_dir_str)
        if not self.covers_dir.is_absolute():
            self.covers_dir = self.script_dir / self.covers_dir

        self.default_cover_file = config.get(
            "Paths", "default_cover_file", fallback="resources/icons/default_cover.png"
        )
        self.folder_cover_file = config.get(
            "Paths", "folder_cover_file", fallback="resources/icons/folder_cover.png"
        )

        if "Covers" not in config:
            config["Covers"] = {}
        self.inherit_parent_cover = config.getboolean(
            "Covers", "inherit_parent_cover", fallback=False
        )

        # Visual Style Metrics
        self.audiobook_icon_size = config.getint(
            "Audiobook_Style", "icon_size", fallback=100
        )
        self.audiobook_row_height = config.getint(
            "Audiobook_Style", "row_height", fallback=120
        )
        self.folder_icon_size = config.getint("Folder_Style", "icon_size", fallback=35)
        self.folder_row_height = config.getint(
            "Folder_Style", "row_height", fallback=45
        )

        # Splitter Layout State
        self.splitter_state = config.get("Layout", "splitter_state", fallback="")

        # Player Functional Preferences
        self.show_id3 = config.getboolean("Player", "show_id3", fallback=False)
        self.minimal_interface = config.getboolean(
            "Player", "minimal_interface", fallback=False
        )
        self.auto_rewind = config.getboolean("Player", "auto_rewind", fallback=False)
        self.auto_check_updates = config.getboolean(
            "Player", "auto_check_updates", fallback=True
        )
        self.show_visualizer = config.getboolean(
            "Player", "show_visualizer", fallback=True
        )
        self.always_on_top = config.getboolean(
            "Display", "always_on_top", fallback=False
        )
        self.show_statusbar = config.getboolean(
            "Display", "show_statusbar", fallback=True
        )
        self.show_subtitles = config.getboolean(
            "Player", "show_subtitles", fallback=False
        )

        # Audio Settings (Unified in [Audio])
        self.deesser_enabled = config.getboolean(
            "Audio",
            "deesser",
            fallback=config.getboolean("Player", "deesser_enabled", fallback=False),
        )
        self.compressor_enabled = config.getboolean(
            "Audio",
            "compressor",
            fallback=config.getboolean("Player", "compressor_enabled", fallback=False),
        )
        self.noise_suppression_enabled = config.getboolean(
            "Audio",
            "noise_suppression",
            fallback=config.getboolean(
                "Player", "noise_suppression_enabled", fallback=False
            ),
        )
        self.vad_threshold = config.getint(
            "Audio",
            "vad_threshold",
            fallback=config.getint("Player", "vad_threshold", fallback=90),
        )
        self.vad_grace_period = config.getint(
            "Audio",
            "vad_grace_period",
            fallback=config.getint("Player", "vad_grace_period", fallback=0),
        )
        self.vad_retroactive_grace = config.getint(
            "Audio",
            "vad_retroactive_grace",
            fallback=config.getint("Player", "vad_retroactive_grace", fallback=0),
        )
        self.deesser_preset = config.getint("Audio", "deesser_preset", fallback=1)
        self.compressor_preset = config.getint("Audio", "compressor_preset", fallback=1)
        self.pitch_enabled = config.getboolean("Audio", "pitch_enabled", fallback=False)
        self.pitch_value = config.getfloat("Audio", "pitch_value", fallback=0.0)
        self.mono_enabled = config.getboolean("Audio", "mono_enabled", fallback=False)
        
        # Volume Boost
        self.volume_boost_enabled = config.getboolean("Audio", "volume_boost_enabled", fallback=False)
        self.volume_boost_level = config.getfloat("Audio", "volume_boost_level", fallback=4.0)

        # Opus Workers
        self.opus_workers = config.getint("Audio", "opus_workers", fallback=0)

        # Apply settings
        self.player.set_deesser_preset(self.deesser_preset)
        self.player.set_deesser(self.deesser_enabled)

        self.player.set_compressor_preset(self.compressor_preset)
        self.player.set_compressor(self.compressor_enabled)

        self.player.set_vad_threshold(self.vad_threshold)
        self.player.set_vad_grace_period(self.vad_grace_period)
        self.player.set_retroactive_grace(self.vad_retroactive_grace)
        self.player.set_noise_suppression(self.noise_suppression_enabled)
        self.player.set_pitch(self.pitch_value)
        self.player.set_pitch_enabled(self.pitch_enabled)
        self.player.set_mono_enabled(self.mono_enabled)
        self.player.set_volume_boost(self.volume_boost_enabled)
        self.player.set_volume_boost_level(self.volume_boost_level)
        self.show_folders = config.getboolean("Library", "show_folders", fallback=False)
        self.library_tile_view = config.getboolean("Library", "tile_view", fallback=False)
        self.remember_filter_folders = config.getboolean(
            "Library", "remember_filter_folders", fallback=True
        )
        self.library_show_folders = {
            "all": config.getboolean("Library", "show_folders_all", fallback=self.show_folders),
            "not_started": config.getboolean("Library", "show_folders_not_started", fallback=self.show_folders),
            "in_progress": config.getboolean("Library", "show_folders_in_progress", fallback=self.show_folders),
            "completed": config.getboolean("Library", "show_folders_completed", fallback=self.show_folders),
        }
        self.show_filter_labels = config.getboolean(
            "Library", "show_filter_labels", fallback=True
        )
        self.show_nesting_lines = config.getboolean(
            "Library", "show_nesting_lines", fallback=True
        )
        self.nesting_lines_single_color = config.getboolean(
            "Library", "nesting_lines_single_color", fallback=False
        )
        self.nesting_lines_color = config.get(
            "Library", "nesting_lines_color", fallback="#808080"
        )
        self.show_detailed_info = config.getboolean(
            "Library", "show_detailed_info", fallback=True
        )
        self.show_status_triangle = config.getboolean(
            "Library", "show_status_triangle", fallback=True
        )
        self.show_info_progress = config.getboolean("Library", "show_info_progress", fallback=True)
        self.show_info_file_count = config.getboolean("Library", "show_info_file_count", fallback=True)
        self.show_info_duration = config.getboolean("Library", "show_info_duration", fallback=True)
        self.show_info_size = config.getboolean("Library", "show_info_size", fallback=True)
        self.show_info_technical = config.getboolean("Library", "show_info_technical", fallback=True)
        self.show_info_year_written = config.getboolean("Library", "show_info_year_written", fallback=True)
        self.show_info_year_recorded = config.getboolean("Library", "show_info_year_recorded", fallback=True)
        self.show_info_language = config.getboolean("Library", "show_info_language", fallback=True)
        self.info_order = config.get("Library", "info_order", fallback="progress,file_count,duration,size,technical,year_written,year_recorded,language")
        self.library_filter_mode = config.get("Library", "filter_mode", fallback="all")
        self.library_favorites_active = config.getboolean(
            "Library", "favorites_active", fallback=False
        )
        old_sort = config.get("Library", "sort_order", fallback="asc")
        self.library_sort_orders = {
            "all": config.get("Library", "sort_order_all", fallback=old_sort),
            "not_started": config.get("Library", "sort_order_not_started", fallback="desc"),
            "in_progress": config.get("Library", "sort_order_in_progress", fallback="desc"),
            "completed": config.get("Library", "sort_order_completed", fallback="desc"),
        }
        old_field = config.get("Library", "sort_field", fallback="name")
        self.library_sort_fields = {
            "all": config.get("Library", "sort_field_all", fallback=old_field),
            "not_started": config.get("Library", "sort_field_not_started", fallback="time_added"),
            "in_progress": config.get("Library", "sort_field_in_progress", fallback="last_updated"),
            "completed": config.get("Library", "sort_field_completed", fallback="time_finished"),
        }

        self.tag_filter_active = config.getboolean(
            "Library", "tag_filter_active", fallback=False
        )
        self.meta_filter_active = config.getboolean(
            "Library", "meta_filter_active", fallback=False
        )
        self.current_meta_filter = config.get(
            "Library", "current_meta_filter", fallback="no_cover"
        )
        tag_ids_str = config.get("Library", "tag_filter_ids", fallback="")
        self.tag_filter_ids = set()
        if tag_ids_str:
            try:
                self.tag_filter_ids = {
                    int(x) for x in tag_ids_str.split(",") if x.strip()
                }
            except ValueError:
                pass

        # Synchronize library root with controller if active
        if hasattr(self, "playback_controller"):
            if self.default_path:
                self.playback_controller.library_root = Path(self.default_path)
            else:
                self.playback_controller.library_root = None

        self.statusBar().setVisible(self.show_statusbar)

    def create_default_settings(self):
        """Generate a fresh 'settings.ini' file with standard defaults for first-time application launch"""
        config = configparser.ConfigParser()
        config["Paths"] = {
            "default_path": "",
            "ffprobe_path": "resources/bin/ffprobe.exe",
            "ffmpeg_path": "resources/bin/ffmpeg.exe",
            "covers_dir": "data/extracted_covers",
            "temp_dir": "data/temp",
            "default_cover_file": "resources/icons/default_cover.png",
            "folder_cover_file": "resources/icons/folder_cover.png",
        }
        config["Covers"] = {
            "names": "cover.jpg,cover.png,cover.jpeg,cover.webp,folder.jpg,folder.png,folder.webp",
            "inherit_parent_cover": "False",
        }
        config["Audio"] = {
            "extensions": ".mp3,.m4a,.m4b,.mp4,.ogg,.flac,.wav,.aac,.wma,.opus,.ape",
            "opus_workers": "0"
        }
        config["Display"] = {
            "window_width": "1200",
            "window_height": "800",
            "window_x": "100",
            "window_y": "100",
            "normal_min_width": "750",
            "normal_min_height": "450",
            "minimal_width": "550",
            "minimal_height": "270",
            "language": "en",
            "show_statusbar": "False",
        }
        config["Audiobook_Style"] = {"icon_size": "100", "row_height": "120"}
        config["Folder_Style"] = {"icon_size": "35", "row_height": "45"}
        config["Layout"] = {"splitter_state": ""}
        config["Player"] = {
            "show_id3": "True",
            "auto_rewind": "True",
            "auto_check_updates": "True",
            "deesser_enabled": "False",
            "compressor_enabled": "False",
            "show_visualizer": "True",
        }
        config["Library"] = {
            "show_folders": "False",
            "show_filter_labels": "False",
            "filter_mode": "all",
            "favorites_active": "False",
            "show_nesting_lines": "True",
            "nesting_lines_single_color": "False",
            "nesting_lines_color": "#808080",
            "show_detailed_info": "True",
            "show_status_triangle": "True",
            "info_order": "progress,file_count,duration,size,technical,year_written,year_recorded,language",
            "sort_order_all": "asc",
            "sort_order_not_started": "desc",
            "sort_order_in_progress": "desc",
            "sort_order_completed": "desc",
            "sort_field_all": "name",
            "sort_field_not_started": "time_added",
            "sort_field_in_progress": "last_updated",
            "sort_field_completed": "time_finished",
        }
        config["LastSession"] = {
            "last_audiobook_id": "0",
            "last_file_index": "0",
            "last_position": "0.0",
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

    def save_settings(self):
        """Commit all current application settings (window state, paths, layout, styles) to the 'settings.ini' file"""
        config = configparser.ConfigParser()
        # Read the existing file first to preserve non-managed sections like 'LastSession'
        if self.config_file.exists():
            config.read(self.config_file, encoding="utf-8")

        # Serialized Window Geometry
        rect = self.geometry()
        if "Display" not in config:
            config["Display"] = {}
        config["Display"]["window_x"] = str(rect.x())
        config["Display"]["window_y"] = str(rect.y())
        config["Display"]["window_width"] = str(rect.width())
        config["Display"]["window_height"] = str(rect.height())
        config["Display"]["window_geometry"] = (
            self.saveGeometry().toHex().data().decode()
        )
        if self.normal_geometry:
            config["Display"]["normal_geometry"] = self.normal_geometry
        if self.normal_splitter_state:
            config["Display"]["normal_splitter_state"] = self.normal_splitter_state
        config["Display"]["normal_min_width"] = str(self.normal_min_width)
        config["Display"]["normal_min_height"] = str(self.normal_min_height)
        config["Display"]["minimal_width"] = str(self.minimal_width)
        config["Display"]["minimal_height"] = str(self.minimal_height)
        config["Display"]["theme"] = self.current_theme
        config["Display"]["always_on_top"] = str(self.always_on_top)
        config["Display"]["show_statusbar"] = str(self.show_statusbar)

        # Appearance Persistence
        if "Appearance" not in config:
            config["Appearance"] = {}
        if getattr(self, "accent_color", ""):
            config["Appearance"]["accent_color"] = self.accent_color
        else:
            if "Appearance" in config and "accent_color" in config["Appearance"]:
                del config["Appearance"]["accent_color"]
        if getattr(self, "window_color", ""):
            config["Appearance"]["window_color"] = self.window_color
        else:
            if "Appearance" in config and "window_color" in config["Appearance"]:
                del config["Appearance"]["window_color"]
        if getattr(self, "bg_dark_color", ""):
            config["Appearance"]["bg_dark_color"] = self.bg_dark_color
        else:
            if "Appearance" in config and "bg_dark_color" in config["Appearance"]:
                del config["Appearance"]["bg_dark_color"]
        if getattr(self, "text_color", ""):
            config["Appearance"]["text_color"] = self.text_color
        else:
            if "Appearance" in config and "text_color" in config["Appearance"]:
                del config["Appearance"]["text_color"]
        if getattr(self, "border_color", ""):
            config["Appearance"]["border_color"] = self.border_color
        else:
            if "Appearance" in config and "border_color" in config["Appearance"]:
                del config["Appearance"]["border_color"]

        if getattr(self, "status_new_color", ""):
            config["Appearance"]["status_new_color"] = self.status_new_color
        else:
            if "Appearance" in config and "status_new_color" in config["Appearance"]:
                del config["Appearance"]["status_new_color"]
        if getattr(self, "status_started_color", ""):
            config["Appearance"]["status_started_color"] = self.status_started_color
        else:
            if "Appearance" in config and "status_started_color" in config["Appearance"]:
                del config["Appearance"]["status_started_color"]
        if getattr(self, "status_completed_color", ""):
            config["Appearance"]["status_completed_color"] = self.status_completed_color
        else:
            if "Appearance" in config and "status_completed_color" in config["Appearance"]:
                del config["Appearance"]["status_completed_color"]
        if getattr(self, "cover_progress_color", ""):
            config["Appearance"]["cover_progress_color"] = self.cover_progress_color
        else:
            if "Appearance" in config and "cover_progress_color" in config["Appearance"]:
                del config["Appearance"]["cover_progress_color"]
        if getattr(self, "icon_color", ""):
            config["Appearance"]["icon_color"] = self.icon_color
        else:
            if "Appearance" in config and "icon_color" in config["Appearance"]:
                del config["Appearance"]["icon_color"]
        config["Appearance"]["icon_thickness"] = str(getattr(self, "icon_thickness", 2.0))
        if "Appearance" in config and not config["Appearance"]:
            del config["Appearance"]

        # Filesystem Path Configs
        if "Paths" not in config:
            config["Paths"] = {}
        config["Paths"]["default_path"] = self.default_path
        config["Paths"]["default_cover_file"] = self.default_cover_file
        config["Paths"]["folder_cover_file"] = self.folder_cover_file

        if "Covers" not in config:
            config["Covers"] = {}
        config["Covers"]["inherit_parent_cover"] = str(self.inherit_parent_cover)

        # Serialized Layout State
        if "Layout" not in config:
            config["Layout"] = {}
        if hasattr(self, "splitter"):
            config["Layout"]["splitter_state"] = (
                self.splitter.saveState().toHex().data().decode()
            )

        # Player and Audio Functional Preferences
        if "Player" not in config:
            config["Player"] = {}
        config["Player"]["show_id3"] = str(self.show_id3)
        config["Player"]["minimal_interface"] = str(
            getattr(self, "minimal_interface", False)
        )
        config["Player"]["auto_rewind"] = str(self.auto_rewind)
        config["Player"]["auto_check_updates"] = str(self.auto_check_updates)
        config["Player"]["show_visualizer"] = str(self.show_visualizer)
        config["Player"]["show_subtitles"] = str(self.show_subtitles)

        if "Audio" not in config:
            config["Audio"] = {}
        config["Audio"]["volume"] = str(self.player.vol_pos)
        config["Audio"]["speed"] = str(self.player.speed_pos)
        config["Audio"]["deesser"] = str(self.deesser_enabled)
        config["Audio"]["compressor"] = str(self.compressor_enabled)
        config["Audio"]["noise_suppression"] = str(self.noise_suppression_enabled)
        config["Audio"]["vad_threshold"] = str(self.vad_threshold)
        config["Audio"]["vad_grace_period"] = str(self.vad_grace_period)
        config["Audio"]["vad_retroactive_grace"] = str(self.vad_retroactive_grace)
        config["Audio"]["deesser_preset"] = str(self.deesser_preset)
        config["Audio"]["compressor_preset"] = str(self.compressor_preset)
        config["Audio"]["pitch_enabled"] = str(self.pitch_enabled)
        config["Audio"]["pitch_value"] = str(self.pitch_value)
        config["Audio"]["mono_enabled"] = str(self.mono_enabled)
        config["Audio"]["volume_boost_enabled"] = str(self.player.volume_boost_enabled)
        config["Audio"]["volume_boost_level"] = str(self.player.volume_boost_level)
        config["Audio"]["opus_workers"] = str(self.opus_workers)
        if "Library" not in config:
            config["Library"] = {}

        if hasattr(self, "library_widget"):
            self.remember_filter_folders = self.library_widget.remember_filter_folders
            self.library_show_folders = self.library_widget.show_folders_by_filter
            self.show_folders = self.library_widget.show_folders
            self.library_tile_view = self.library_widget.is_tile_view

        config["Library"]["remember_filter_folders"] = str(self.remember_filter_folders)
        config["Library"]["show_folders"] = str(self.show_folders)
        config["Library"]["tile_view"] = str(self.library_tile_view)
        config["Library"]["show_folders_all"] = str(self.library_show_folders.get("all", False))
        config["Library"]["show_folders_not_started"] = str(self.library_show_folders.get("not_started", False))
        config["Library"]["show_folders_in_progress"] = str(self.library_show_folders.get("in_progress", False))
        config["Library"]["show_folders_completed"] = str(self.library_show_folders.get("completed", False))
        config["Library"]["show_filter_labels"] = str(self.show_filter_labels)
        config["Library"]["show_nesting_lines"] = str(self.show_nesting_lines)
        config["Library"]["nesting_lines_single_color"] = str(self.nesting_lines_single_color)
        config["Library"]["nesting_lines_color"] = str(self.nesting_lines_color)
        config["Library"]["show_detailed_info"] = str(self.show_detailed_info)
        config["Library"]["show_status_triangle"] = str(self.show_status_triangle)
        config["Library"]["show_info_progress"] = str(self.show_info_progress)
        config["Library"]["show_info_file_count"] = str(self.show_info_file_count)
        config["Library"]["show_info_duration"] = str(self.show_info_duration)
        config["Library"]["show_info_size"] = str(self.show_info_size)
        config["Library"]["show_info_technical"] = str(self.show_info_technical)
        config["Library"]["show_info_year_written"] = str(self.show_info_year_written)
        config["Library"]["show_info_year_recorded"] = str(self.show_info_year_recorded)
        config["Library"]["show_info_language"] = str(self.show_info_language)
        config["Library"]["info_order"] = self.info_order
        if hasattr(self, "library_widget"):
            config["Library"]["tag_filter_active"] = str(
                self.library_widget.is_tag_filter_active
            )
            config["Library"]["meta_filter_active"] = str(
                self.library_widget.is_meta_filter_active
            )
            config["Library"]["current_meta_filter"] = self.library_widget.current_meta_filter
            if self.library_widget.tag_filter_ids:
                config["Library"]["tag_filter_ids"] = ",".join(
                    map(str, self.library_widget.tag_filter_ids)
                )
            else:
                config["Library"]["tag_filter_ids"] = ""
            config["Library"]["filter_mode"] = self.library_widget.current_filter
            config["Library"]["favorites_active"] = str(
                self.library_widget.is_favorites_filter_active
            )
            config["Library"]["sort_order_all"] = self.library_widget.sort_orders.get("all", "asc")
            config["Library"]["sort_order_not_started"] = self.library_widget.sort_orders.get("not_started", "asc")
            config["Library"]["sort_order_in_progress"] = self.library_widget.sort_orders.get("in_progress", "asc")
            config["Library"]["sort_order_completed"] = self.library_widget.sort_orders.get("completed", "asc")
            config["Library"]["sort_field_all"] = self.library_widget.sort_fields.get("all", "name")
            config["Library"]["sort_field_not_started"] = self.library_widget.sort_fields.get("not_started", "name")
            config["Library"]["sort_field_in_progress"] = self.library_widget.sort_fields.get("in_progress", "name")
            config["Library"]["sort_field_completed"] = self.library_widget.sort_fields.get("completed", "name")

        # Visual Style Persistence
        if "Audiobook_Style" not in config:
            config["Audiobook_Style"] = {}
        config["Audiobook_Style"]["icon_size"] = str(self.audiobook_icon_size)
        config["Audiobook_Style"]["row_height"] = str(self.audiobook_row_height)

        if "Folder_Style" not in config:
            config["Folder_Style"] = {}
        config["Folder_Style"]["icon_size"] = str(self.folder_icon_size)
        config["Folder_Style"]["row_height"] = str(self.folder_row_height)

        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

    def save_last_session(self):
        """Encapsulate the current playback state (active book, file, and position) into the configuration for future restoration"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        if "LastSession" not in config:
            config["LastSession"] = {}

        config["LastSession"]["last_audiobook_id"] = str(
            self.playback_controller.current_audiobook_id or 0
        )
        config["LastSession"]["last_file_index"] = str(
            self.playback_controller.current_file_index
        )
        config["LastSession"]["last_position"] = str(self.player.get_position())

        if "Display" not in config:
            config["Display"] = {}

        config["Display"]["window_width"] = str(self.width())
        config["Display"]["window_height"] = str(self.height())
        config["Display"]["window_x"] = str(self.x())
        config["Display"]["window_y"] = str(self.y())
        config["Display"]["window_geometry"] = (
            self.saveGeometry().toHex().data().decode()
        )

        # Persist the relative sizes of layout panes
        if hasattr(self, "splitter"):
            sizes = self.splitter.sizes()
            config["Display"]["splitter_sizes"] = ",".join(map(str, sizes))

        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

    def restore_last_session(self):
        """Re-establish the application's previous state by reloading playback meta-data and layout preferences"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        audiobook_id = config.getint("LastSession", "last_audiobook_id", fallback=0)
        file_index = config.getint("LastSession", "last_file_index", fallback=0)
        position = config.getfloat("LastSession", "last_position", fallback=0.0)

        # Restore layout splitter proportions
        splitter_sizes_str = config.get("Display", "splitter_sizes", fallback="")
        if splitter_sizes_str and hasattr(self, "splitter"):
            try:
                sizes = [int(s) for s in splitter_sizes_str.split(",")]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
            except (ValueError, TypeError):
                pass

        if audiobook_id <= 0:
            return

        # Lookup audiobook relative path and completion status by unique identifier
        import sqlite3

        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        cursor.execute("SELECT path, is_completed FROM audiobooks WHERE id = ?", (audiobook_id,))
        row = cursor.fetchone()
        connection.close()

        if row:
            audiobook_path = row[0]
            is_completed = row[1]
            if is_completed == 1:
                return

            # Wire up the async-load callback so that UI is updated once the stream is ready
            self.playback_controller.on_load_complete = self._on_url_load_complete

            if self.playback_controller.load_audiobook(audiobook_path):
                # Inform the delegate of the active playback path for visual feedback
                if self.delegate:
                    self.delegate.playing_path = audiobook_path

                if self.playback_controller._url_loading:
                    # URL track: re-inject the saved position and file_index into the context
                    # so _on_url_stream_ready() will seek correctly after connection.
                    ctx = self.playback_controller._url_load_context
                    ctx['saved_position'] = position if position > 0 else ctx.get('saved_position')
                    ctx['restore_paused'] = True
                    # Update the UI for what we know so far (playlist, cover, speed)
                    self.update_ui_for_audiobook()
                    self.library_widget.tree.viewport().update()
                    return  # playback will start in _on_url_load_complete once connected

                # Synchronous path (local file) — same as before
                self.playback_controller.current_file_index = file_index
                self.playback_controller.play_file_at_index(file_index, False)
                if position > 0:
                    self.player.set_position(position)

                self.update_ui_for_audiobook()
                self.library_widget.tree.viewport().update()
                self.library_widget.load_audiobooks()
                self.statusBar().showMessage(tr("status.restored_session"))

    def on_id3_state_toggled(self, state: bool):
        """Persist the preference for ID3 tag visibility for the currently active audiobook"""
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_id3_state(
                self.playback_controller.current_audiobook_id, state
            )

    def on_subtitles_state_toggled(self, checked: bool):
        """Update and persist the subtitles visibility preference"""
        self.show_subtitles = checked
        self.save_settings()
        if checked:
            self._load_subtitles_for_current_file()

    def _load_subtitles_for_current_file(self):
        """Load SRT subtitles for the current file if available, otherwise clear the panel"""
        if not hasattr(self.player_widget, 'subtitle_panel'):
            return

        controller = self.playback_controller
        if not controller.current_audiobook_id or controller.current_file_index < 0 or controller.current_file_index >= len(controller.files_list):
            self.player_widget.subtitle_panel.clear()
            return

        file_info = controller.files_list[controller.current_file_index]
        srt_rel_path = file_info.get('srt_path', '')
        
        # If relative path is empty, try to see if there's any fallback SRT next to the audio file in filesystem
        audio_path_str = file_info.get('path', '')
        
        srt_abs_path = None
        if srt_rel_path:
            # Resolve relative to library root
            if controller.library_root:
                srt_abs_path = controller.library_root / srt_rel_path
            else:
                srt_abs_path = Path(srt_rel_path)
        elif audio_path_str and not file_info.get('is_url', False):
            # Fallback path finding on filesystem
            audio_path = Path(audio_path_str)
            if not audio_path.is_absolute() and controller.library_root:
                audio_path = controller.library_root / audio_path
            # Check same directory .srt
            candidates = [
                audio_path.with_suffix('.srt'),
                audio_path.parent / 'subtitles' / audio_path.with_suffix('.srt').name,
                audio_path.parent / 'subtitles' / f'{audio_path.parent.name}.srt',
            ]
            for c in candidates:
                if c.exists():
                    srt_abs_path = c
                    break

        if srt_abs_path and srt_abs_path.exists():
            self.player_widget.subtitle_panel.load_srt(srt_abs_path)
        else:
            self.player_widget.subtitle_panel.clear()

    def on_auto_rewind_state_toggled(self, state: bool):
        """Update and persist the auto-rewind preference"""
        self.auto_rewind = state
        self.save_settings()

    def on_deesser_state_toggled(self, state: bool):
        """Update and persist the DeEsser preference"""
        self.deesser_enabled = state
        self.player.set_deesser(state)
        self.save_settings()

    def on_compressor_state_toggled(self, state: bool):
        """Update and persist the Compressor preference"""
        self.compressor_enabled = state
        self.player.set_compressor(state)
        self.save_settings()

    def on_noise_suppression_state_toggled(self, state: bool):
        """Update and persist the Noise Suppression preference"""
        self.noise_suppression_enabled = state
        self.player.set_noise_suppression(state)
        self.save_settings()

    def on_vad_threshold_changed(self, value: int):
        """Update VAD threshold when slider changed"""
        self.vad_threshold = value
        self.player.set_vad_threshold(value / 100.0)
        self.save_settings()

    def on_vad_grace_period_changed(self, value: int):
        """Update VAD Grace Period when slider changed"""
        self.vad_grace_period = value
        self.player.set_vad_grace_period(value / 100.0)
        self.save_settings()

    def on_vad_retro_grace_changed(self, value: int):
        """Update Retroactive VAD Grace when slider changed"""
        self.vad_retroactive_grace = value
        self.player.set_retroactive_grace(value / 100.0)
        self.save_settings()

    def on_deesser_preset_changed(self, value: int):
        """Handle DeEsser preset change"""
        self.deesser_preset = value
        self.player.set_deesser_preset(value)
        self.save_settings()

    def on_compressor_preset_changed(self, value: int):
        """Handle Compressor preset change"""
        self.compressor_preset = value
        self.player.set_compressor_preset(value)
        self.save_settings()

    def on_pitch_toggled(self, checked):
        """Update and persist pitch enabled state"""
        self.pitch_enabled = checked
        self.player.set_pitch_enabled(checked)
        self.save_settings()

    def on_pitch_changed(self, value):
        """Update and persist pitch value"""
        self.pitch_value = value
        self.player.set_pitch(value)
        self.save_settings()

    def on_mono_toggled(self, checked):
        """Update and persist mono enabled state"""
        self.mono_enabled = checked
        self.player.set_mono_enabled(checked)
        self.save_settings()

    # Drag and Drop Events
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            # Apply blur
            self.apply_blur()

            # Show overlay
            self.drop_overlay.resize(self.size())
            self.drop_overlay.raise_()
            self.drop_overlay.show()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()
        self.remove_blur()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.drop_overlay.isVisible():
            self.drop_overlay.resize(self.size())

    def dropEvent(self, event):
        self.drop_overlay.hide()
        self.remove_blur()
        if not self.default_path:
            QMessageBox.warning(self, tr("error"), tr("settings.specify_path"))
            return

        urls = event.mimeData().urls()
        if not urls:
            return

        self.statusBar().showMessage(tr("status.starting_copy"))

        # We need to keep a reference to the thread so it doesn't get GC'd
        self.copy_thread = CopyThread(urls, self.default_path)
        self.copy_thread.progress.connect(self.on_copy_progress)
        self.copy_thread.finished_copy.connect(self.on_copy_finished)
        self.copy_thread.start()

    def on_copy_progress(self, message):
        self.statusBar().showMessage(message)

    def on_copy_finished(self, count):
        # Use a localized string or fallback
        msg = trf("status.copy_complete", count=count)
        if msg == "status.copy_complete":
            msg = f"Copied {count} items."

        self.statusBar().showMessage(msg, 5000)
        if count > 0:
            self.rescan_directory()

    def on_show_folders_toggled(self, checked):
        """Update and persist the folder visibility preference"""
        self.show_folders = checked
        if hasattr(self, "library_widget"):
            self.library_show_folders = self.library_widget.show_folders_by_filter
        self.save_settings()

    def on_sort_order_changed(self, filter_mode, sort_order, sort_field):
        """Update and persist the library sort order preference"""
        self.library_sort_orders[filter_mode] = sort_order
        self.library_sort_fields[filter_mode] = sort_field
        self.save_settings()

    def on_audiobook_selected(self, audiobook_path: str):
        """Handle the user's selection of an audiobook from the library, initiating playback and updating status"""
        # Wire up the async-load callback before loading
        self.playback_controller.on_load_complete = self._on_url_load_complete

        # Provide immediate feedback during metadata lookup/playlist loading
        self.statusBar().showMessage(tr("player.loading_playlist"))
        QApplication.processEvents()

        if self.playback_controller.load_audiobook(audiobook_path):
            # Update database status to mark the book as currently reading
            if self.playback_controller.current_audiobook_id:
                self.db_manager.mark_audiobook_started(
                    self.playback_controller.current_audiobook_id
                )

            # Sync the delegate with the newly active track
            if self.delegate:
                self.delegate.playing_path = audiobook_path

            self.update_ui_for_audiobook()

            if self.playback_controller._url_loading:
                # URL track: stream is loading in background — do NOT call toggle_play().
                # Playback will start in _on_url_load_complete() once the stream is ready.
                self.library_widget.load_audiobooks(use_cache=False)
            else:
                # Local file: start playback immediately as before
                self.toggle_play()
                self.library_widget.load_audiobooks(use_cache=False)

    def _on_url_load_complete(self):
        """Called in the main thread once an async URL stream has connected and is ready."""
        ctx = self.playback_controller._url_load_context
        restore_paused = ctx.get('restore_paused', False)

        # If the player is not yet playing (e.g. user selected a book), start now
        if not self.player.is_playing() and not restore_paused:
            self.player.play()

        if self.player.is_playing():
            self.taskbar_progress.set_normal()
        else:
            self.taskbar_progress.set_paused()
        self.player_widget.set_playing(self.player.is_playing())

        # Sync the listening tracker for statistics
        if hasattr(self, 'listening_tracker') and self.playback_controller.current_audiobook_id:
            if not self.listening_tracker.is_active:
                self.listening_tracker.start_session(
                    self.playback_controller.current_audiobook_id,
                    self.player.speed_pos / 10.0
                )

        # Sync taskbar thumbnail play/pause state
        if hasattr(self, 'thumbnail_buttons'):
            self.thumbnail_buttons.update_play_state(self.player.is_playing())

        # Refresh the playlist panel to show updated durations
        self.player_widget.load_files(
            self.playback_controller.files_list,
            self.playback_controller.current_file_index,
        )
        self.update_progress_bar_markers()

        # Update library to reflect started status
        self.library_widget.load_audiobooks(use_cache=False)
        if ctx.get("restore_paused"):
            self.statusBar().showMessage(tr("status.restored_session"))
        else:
            self.statusBar().showMessage(tr("player.stream_ready"))

    def update_ui_for_audiobook(self):
        """Synchronize various UI elements to reflect the metadata and state of the currently loaded audiobook"""
        # Revise window title to include the book's title
        title = self.playback_controller.get_audiobook_title()
        self.setWindowTitle(trf("window.title_with_book", title=title))

        # Populate the playlist widget with the book's file list
        self.player_widget.load_files(
            self.playback_controller.files_list,
            self.playback_controller.current_file_index,
        )

        # Restore the persistent ID3 visibility preference
        self.player_widget.id3_btn.setChecked(self.playback_controller.use_id3_tags)

        # Apply visual focus to the book in the library tree
        self.library_widget.highlight_audiobook(
            self.playback_controller.current_audiobook_path
        )

        # Synchronize speed control slider
        self.player_widget.set_speed(self.player.speed_pos)

        # Update bookmark markers on progress bar
        self.update_progress_bar_markers()
        
        # Load subtitles for current audiobook segment
        self._load_subtitles_for_current_file()

    def unload_active_book(self, save_progress: bool = True):
        """Stop playback, save current progress (optional), and completely unload the active audiobook"""
        if self.playback_controller.current_audiobook_path:
            if save_progress:
                self.playback_controller.save_current_progress()
                self.save_last_session()

            # Stop active playback and unload file to release locks
            self.player.unload()

            # Clear the internal state of the playback controller
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = ""
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0

            # Clear active subtitles
            if hasattr(self.player_widget, 'subtitle_panel'):
                self.player_widget.subtitle_panel.clear()

            # Synchronize UI components to the empty state
            self.update_ui_for_audiobook()

            # Reset player UI components specifically
            self.player_widget.position_slider.setValue(0)
            self.player_widget.total_progress_bar.setValue(0)
            self.player_widget.time_current.setText("0:00")
            self.player_widget.time_duration.setText("0:00")
            self.player_widget.total_time_label.setText("0:00:00")
            self.player_widget.total_duration_label.setText("0:00:00")
            self.player_widget.total_percent_label.setText(
                trf("formats.percent", value=0)
            )
            self.player_widget.time_left_label.setText(tr("player.time_left_unknown"))

            if self.delegate:
                self.delegate.playing_path = None  # Remove tree highlighting

            self.library_widget.tree.viewport().update()
            if hasattr(self.library_widget, "update_tile_playback_state"):
                self.library_widget.update_tile_playback_state()

    def update_progress_bar_markers(self):
        """Update the bookmarks markers on the total progress bar"""
        percentages = self.playback_controller.get_bookmarks_percentages()
        self.player_widget.total_progress_bar.set_markers(percentages)

    def toggle_play(self):
        """Toggle between active playback and paused states, updating UI indicators and background controllers accordingly"""
        # Guard: Ignore play/pause clicks while a network stream is connecting or seeking
        if self.playback_controller._url_loading:
            return

        if self.player.is_playing():
            self.player.pause()
            self.last_pause_time = __import__("time").time()
            self.taskbar_progress.set_paused()
            
            # End listening session on pause
            if hasattr(self, 'listening_tracker'):
                self.listening_tracker.end_session()
        else:
            if self.auto_rewind and self.last_pause_time:
                pause_duration = __import__("time").time() - self.last_pause_time
                if pause_duration > 1:  # Only rewind if pause was longer than 1 seconds
                    # Rewind logic: base 1s + 1s per 30s of pause, up to 30s total
                    # So: 1min pause -> 5 + 2 = 7s, 10min pause -> 5 + 20 = 25s
                    rewind_amount = min(30, 5 + (pause_duration / 30.0))
                    self.player.rewind(-rewind_amount)

            self.player.play()
            self.last_pause_time = None
            self.taskbar_progress.set_normal()

            # Resume/Start listening session when playing
            if hasattr(self, 'listening_tracker') and self.playback_controller.current_audiobook_id:
                if not self.listening_tracker.is_active:
                    self.listening_tracker.start_session(
                        self.playback_controller.current_audiobook_id,
                        self.player.speed_pos / 10.0
                    )

        # Sync the session delegate for visual consistency in the library
        if self.delegate:
            self.delegate.is_paused = not self.player.is_playing()
            self.library_widget.tree.viewport().update()
            if hasattr(self.library_widget, "update_tile_playback_state"):
                self.library_widget.update_tile_playback_state()

        self.player_widget.set_playing(self.player.is_playing())

        # Synchronize taskbar thumbnail buttons
        if hasattr(self, "thumbnail_buttons"):
            self.thumbnail_buttons.update_play_state(self.player.is_playing())

        self.playback_controller.save_current_progress()
        self.save_last_session()

    def on_next_clicked(self):
        """Transition playback to the subsequent file in the audiobook sequence"""
        if self.playback_controller.next_file():
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
            self._load_subtitles_for_current_file()
        else:
            self.statusBar().showMessage(tr("status.audiobook_complete"))
        self.save_last_session()
        self.refresh_audiobook_in_tree()

    def on_prev_clicked(self):
        """Transition playback to the preceding file in the audiobook sequence"""
        if self.playback_controller.prev_file():
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
            self._load_subtitles_for_current_file()
            self.save_last_session()
            self.refresh_audiobook_in_tree()

    def on_rewind_10_clicked(self):
        """Rewind playback by a fixed 10-second interval within the current file"""
        pos = self.player.get_position()
        self.player.set_position(max(0, pos - 10))
        self.playback_controller.save_current_progress()

    def on_forward_10_clicked(self):
        """Advance playback by a fixed 10-second interval within the current file"""
        pos = self.player.get_position()
        duration = self.player.get_duration()
        if duration > 0:
            self.player.set_position(min(duration, pos + 10))
        self.playback_controller.save_current_progress()

    def on_file_selected(self, index: int):
        """Handle manual file selection from the track list, initiating playback for the chosen segment"""
        self.playback_controller.play_file_at_index(index)
        self.player_widget.highlight_current_file(index)
        self._load_subtitles_for_current_file()
        self.save_last_session()
        self.refresh_audiobook_in_tree()

    def on_position_changed(self, normalized: float):
        """Seek to a specific temporal position within the active chapter based on normalized slider input"""
        # Guard: Ignore seek attempts while a network stream is connecting or seeking
        if self.playback_controller._url_loading:
            return

        if not self.playback_controller.files_list or self.playback_controller.current_file_index < 0 or self.playback_controller.current_file_index >= len(self.playback_controller.files_list):
            return
            
        current_file_info = self.playback_controller.files_list[
            self.playback_controller.current_file_index
        ]
        start_offset = current_file_info.get("start_offset", 0)
        chapter_duration = current_file_info.get("duration", self.player.get_duration())

        if chapter_duration > 0:
            target_pos = start_offset + (normalized * chapter_duration)
            self.playback_controller._target_seek_position = None  # Cancel any pending auto-seek retries
            self.player.set_position(target_pos)
            self.playback_controller.save_current_progress()

    def on_speed_changed(self, value: int):
        """Adjust the audio playback speed and persist the new preference to the database for the active book"""
        self.player.set_speed(value)
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_speed(
                self.playback_controller.current_audiobook_id, value / 10.0
            )

    def on_library_play_clicked(self, audiobook_path: str):
        """Initiate or resume playback from the library view via the 'Play' overlay button"""
        if self.playback_controller.current_audiobook_path == audiobook_path:
            self.toggle_play()
        else:
            # If a different book is targeted, load its session and begin playback immediately
            self.on_audiobook_selected(audiobook_path)
            # Guard: for async network books, do not call toggle_play() immediately because it
            # will run while the channel is still 0 and overwrite the saved position with 0.
            # Instead, the playback will automatically start in _on_url_load_complete().
            if not self.playback_controller._url_loading and not self.player.is_playing():
                self.toggle_play()

        # Force a refresh to reflect progress/started status changes immediately
        self.refresh_audiobook_in_tree()

        # Trigger an immediate viewport update to reflect the changed play/pause status in the overlay
        self.library_widget.tree.viewport().update()

    def showEvent(self, event):
        """Integrate with the Windows shell upon window display, configuring taskbar progress and thumbnail control buttons"""
        super().showEvent(event)

        # Link the system window handle to the taskbar progress manager
        hwnd = int(self.winId())
        self.taskbar_progress.set_hwnd(hwnd)

        # Initialize taskbar overlay controls
        if self.taskbar_progress.taskbar:
            self.thumbnail_buttons = TaskbarThumbnailButtons(
                self.taskbar_progress.taskbar, hwnd, self.icons_dir
            )
            # Defer button addition to ensure the window is fully registered with the taskbar
            QTimer.singleShot(1000, self.thumbnail_buttons.add_buttons)

            # Synchronize initial visual state
            self.thumbnail_buttons.update_play_state(self.player.is_playing())

    def refresh_audiobook_in_tree(self):
        """Trigger a metadata refresh for the active audiobook's visual representation in the library tree"""
        self.library_widget.refresh_audiobook_item(
            self.playback_controller.current_audiobook_path
        )

    def reveal_current_audiobook(self):
        """Scroll to the currently playing audiobook in the library tree"""
        if not self.playback_controller.current_audiobook_path:
            self.statusBar().showMessage(tr("status.no_audiobook_playing"), 3000)
            return

        # Clear search filter and scroll to current book
        self.library_widget.reveal_current_audiobook(
            self.playback_controller.current_audiobook_path
        )

    def _on_playback_status(self, message: str):
        """Route status messages from PlaybackController to the status bar via thread-safe signal."""
        self.status_requested.emit(message)

    def on_stream_load_start(self, url: str):
        """Handle network stream load start by showing connecting message"""
        msg = tr("player.connecting", "Connecting...")
        self.statusBar().showMessage(msg)
        # Force a repaint so the user sees the connecting message before BASS connects synchronously
        QApplication.processEvents()

    def on_stream_load_error(self, url: str):
        """Handle network stream load failure by showing network error message"""
        self.statusBar().showMessage(tr("player.network_error", "Network error"), 5000)

    def update_ui(self):
        """Perform periodic synchronization of all UI components (sliders, labels, taskbar) with the current engine state"""
        if self.player.chan == 0:
            return

        pos = self.player.get_position()
        duration = self.player.get_duration()

        current_file_info = self.playback_controller.files_list[
            self.playback_controller.current_file_index
        ]
        start_offset = current_file_info.get("start_offset", 0)
        chapter_duration = current_file_info.get("duration", duration)

        # Synchronize individual track progress indicators
        self.player_widget.update_file_progress(
            pos - start_offset, chapter_duration, self.player.speed_pos / 10.0
        )

        # Synchronize Subtitles position
        if self.show_subtitles and hasattr(self.player_widget, 'subtitle_panel'):
            self.player_widget.subtitle_panel.update_position(pos - start_offset)

        # Synchronize aggregate audiobook progress indicators
        total_pos = self.playback_controller.get_current_position()
        self.player_widget.update_total_progress(
            total_pos,
            self.playback_controller.total_duration,
            self.player.speed_pos / 10.0,
        )

        # Perform low-priority library viewport updates (throttled to 1Hz)
        if not hasattr(self, "_library_update_counter"):
            self._library_update_counter = 0

        self._library_update_counter += 1
        if self._library_update_counter >= 10:  # 100ms * 10 = 1000ms
            self._library_update_counter = 0
            if self.playback_controller.current_audiobook_path:
                progress_percent = self.playback_controller.get_progress_percent()
                self.library_widget.update_item_progress(
                    self.playback_controller.current_audiobook_path,
                    total_pos,
                    progress_percent,
                )

        # Synchronize play/pause button aesthetics
        self.player_widget.set_playing(self.player.is_playing())

        # Update listening statistics tracker
        if hasattr(self, 'listening_tracker'):
            is_playing = self.player.is_playing()
            current_speed = self.player.speed_pos / 10.0
            self.listening_tracker.update_session(is_playing, current_speed)

        # Synchronize Windows taskbar progress metrics
        if self.playback_controller.total_duration > 0:
            self.taskbar_progress.update_for_playback(
                is_playing=self.player.is_playing(),
                current=total_pos,
                total=self.playback_controller.total_duration,
            )

        # Update streaming information in the status bar
        if self.playback_controller._url_loading:
            pass  # Do not touch the status bar while a URL is loading/seeking/connecting asynchronously
        elif getattr(self.player, "is_streaming", False):
            info = self.player.get_stream_info()
            curr_msg = self.statusBar().currentMessage()
            
            is_our_msg = (
                not curr_msg or 
                "Streaming" in curr_msg or 
                "Connecting" in curr_msg or 
                "Buffering" in curr_msg or
                "Буферизация" in curr_msg or
                "Поточное" in curr_msg or
                "Подключение" in curr_msg or
                tr("player.buffering") in curr_msg or
                tr("player.connecting") in curr_msg or
                tr("player.streaming") in curr_msg
            )
            
            if is_our_msg:
                if info.get("is_stalled", False):
                    msg = tr("player.buffering", "Buffering...")
                    if info.get("buffering_percent", -1) >= 0:
                        msg += f" {info['buffering_percent']}%"
                    
                    if info.get("downloaded", 0) > 0:
                        dl_str = format_size(info["downloaded"])
                        if info.get("total_size", 0) > 0:
                            tot_str = format_size(info["total_size"])
                            msg += f" ({dl_str} / {tot_str})"
                        else:
                            msg += f" ({dl_str})"
                    self.statusBar().showMessage(msg)
                else:
                    dl = info.get("downloaded", 0)
                    tot = info.get("total_size", 0)
                    if dl > 0:
                        if tot > 0 and dl >= tot:
                            self.statusBar().clearMessage()
                        else:
                            msg = tr("player.streaming", "Streaming...")
                            dl_str = format_size(dl)
                            if tot > 0:
                                tot_str = format_size(tot)
                                msg += f" ({dl_str} / {tot_str})"
                            else:
                                msg += f" ({dl_str})"
                            self.statusBar().showMessage(msg)
                    else:
                        self.statusBar().showMessage(tr("player.connecting", "Connecting..."))
        else:
            curr_msg = self.statusBar().currentMessage()
            is_our_msg = (
                curr_msg and (
                    "Streaming" in curr_msg or 
                    "Connecting" in curr_msg or 
                    "Buffering" in curr_msg or
                    "Буферизация" in curr_msg or
                    "Поточное" in curr_msg or
                    "Подключение" in curr_msg or
                    tr("player.buffering") in curr_msg or
                    tr("player.connecting") in curr_msg or
                    tr("player.streaming") in curr_msg
                )
            )
            if is_our_msg:
                self.statusBar().clearMessage()

        # Automate track transition upon reaching the end of the current file or chapter
        chapter_end = start_offset + chapter_duration
        
        # 1. Primary: callback-based stream end detection
        if self.playback_controller.check_stream_end():
            self.on_next_clicked()
            return

        # 2. Fallback: position-based detection (safety net if callback fails or file stops early)
        # Only trigger when playback has actually stopped AND we are near the end.
        # This avoids cutting off audio that is still playing.
        if not self.player.is_playing() and duration > 0 and pos >= chapter_end - 1.5:
            self.on_next_clicked()

    def rescan_directory(self, target_path: str = "", force_rescan: bool = False):
        """Initiate a comprehensive scan of the configured media directory with progress feedback via a dialog"""
        if isinstance(target_path, bool):
            target_path = ""
        if not self.default_path:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.specify_path"))
            return

        def start_scanning_process():
            # Apply blur effect to central widget
            self.apply_blur()

            dialog = ScanProgressDialog(self)

            # Refresh the library view and status bar metrics upon scan completion
            def on_finished():
                self.library_widget.refresh_library()
                total_count = self.db_manager.get_audiobook_count()
                self.statusBar().showMessage(
                    trf("status.library_count", count=total_count)
                )
                self.remove_blur()

            dialog.finished.connect(on_finished)
            dialog.show()
            subfolder_path = target_path if target_path else None
            dialog.start_scan(self.default_path, self.ffprobe_path, subfolder_path=subfolder_path, force_rescan=force_rescan)

        start_scanning_process()

    def reload_styles(self):
        """Immediately re-apply global CSS styles and update presentation delegates to reflect theme changes"""
        try:
            from styles import StyleManager

            overrides = {}
            if getattr(self, "accent_color", ""):
                overrides["accent"] = self.accent_color
            if getattr(self, "window_color", ""):
                overrides["bg-main"] = self.window_color
            if getattr(self, "bg_dark_color", ""):
                overrides["bg-dark"] = self.bg_dark_color
            if getattr(self, "text_color", ""):
                overrides["text"] = self.text_color
            if getattr(self, "border_color", ""):
                overrides["border"] = self.border_color
            if getattr(self, "status_new_color", ""):
                overrides["status-error"] = self.status_new_color
            if getattr(self, "status_started_color", ""):
                overrides["status-warning"] = self.status_started_color
            if getattr(self, "status_completed_color", ""):
                overrides["status-ok"] = self.status_completed_color
            if getattr(self, "cover_progress_color", ""):
                overrides["theme-primary"] = self.cover_progress_color

            StyleManager.apply_style(QApplication.instance(), theme=self.current_theme, overrides=overrides)

            # Synchronize item rendering delegates
            if self.delegate:
                self.delegate.update_styles()

            # Force StyleManager to refresh its cache based on the new stylesheet
            StyleManager.refresh_cache()

            self.statusBar().showMessage(tr("status.styles_reloaded"))
        except Exception as e:
            self.statusBar().showMessage(trf("status.styles_error", error=str(e)))

    def show_appearance_settings(self):
        """Display the appearance settings dialog to configure accent color, window background color, and preview changes live"""
        try:
            from appearance_dialog import AppearanceDialog
            from styles import StyleManager
            
            default_accent = StyleManager.get_default_vars(self.current_theme).get("accent", "#018574")
            default_window = StyleManager.get_default_vars(self.current_theme).get("bg-main", "#444444")
            default_bg_dark = StyleManager.get_default_vars(self.current_theme).get("bg-dark", "#373737")
            default_text = StyleManager.get_default_vars(self.current_theme).get("text", "#eaeaea")
            default_border = StyleManager.get_default_vars(self.current_theme).get("border", "#808080")
            default_status_new = StyleManager.get_default_vars(self.current_theme).get("status-error", "#ff6b6b")
            default_status_started = StyleManager.get_default_vars(self.current_theme).get("status-warning", "#f9ca24")
            default_status_completed = StyleManager.get_default_vars(self.current_theme).get("status-ok", "#4ecca3")
            default_cover_progress = StyleManager.get_default_vars(self.current_theme).get("theme-primary", "#2ecc71")
            
            dialog = AppearanceDialog(
                self,
                current_accent=getattr(self, "accent_color", ""),
                default_accent=default_accent,
                current_window=getattr(self, "window_color", ""),
                default_window=default_window,
                current_bg_dark=getattr(self, "bg_dark_color", ""),
                default_bg_dark=default_bg_dark,
                current_text=getattr(self, "text_color", ""),
                default_text=default_text,
                current_border=getattr(self, "border_color", ""),
                default_border=default_border,
                current_status_new=getattr(self, "status_new_color", ""),
                default_status_new=default_status_new,
                current_status_started=getattr(self, "status_started_color", ""),
                default_status_started=default_status_started,
                current_status_completed=getattr(self, "status_completed_color", ""),
                default_status_completed=default_status_completed,
                current_icon_color=getattr(self, "icon_color", ""),
                default_icon_color="#cccccc",
                current_icon_thickness=getattr(self, "icon_thickness", 2.0),
                default_icon_thickness=2.0,
                current_cover_progress=getattr(self, "cover_progress_color", ""),
                default_cover_progress=default_cover_progress,
                show_detailed_info=self.show_detailed_info,
                show_info_progress=self.show_info_progress,
                show_info_file_count=self.show_info_file_count,
                show_info_duration=self.show_info_duration,
                show_info_size=self.show_info_size,
                show_info_technical=self.show_info_technical,
                show_info_year_written=self.show_info_year_written,
                show_info_year_recorded=self.show_info_year_recorded,
                show_info_language=self.show_info_language,
                show_visualizer=self.show_visualizer,
                show_nesting_lines=self.show_nesting_lines,
                show_status_triangle=self.show_status_triangle,
                show_statusbar=self.show_statusbar,
                remember_filter_folders=self.remember_filter_folders,
                info_order=self.info_order,
                nesting_lines_single_color=self.nesting_lines_single_color,
                nesting_lines_color=self.nesting_lines_color,
                default_nesting_lines_color="#808080"
            )
            
            self.appearance_dialog = dialog
            
            dialog.appearance_preview.connect(self.apply_appearance_preview)
            dialog.appearance_saved.connect(self.save_appearance_colors)
            
            # Keep compatibility connects if dialog is ever opened elsewhere using old signals
            dialog.accent_preview.connect(self.apply_accent_preview)
            dialog.accent_saved.connect(self.save_accent_color)
            
            dialog.exec()
            self.appearance_dialog = None
        except Exception as e:
            print(f"Error showing appearance settings: {e}")

    def apply_appearance_preview(self, accent_hex: str, window_hex: str, bg_dark_hex: str, text_hex: str = "", border_hex: str = "",
                                 status_new_hex: str = "", status_started_hex: str = "", status_completed_hex: str = "", icon_hex: str = "",
                                 cover_progress_hex: str = "", icon_thickness: float = 2.0):
        """Apply temporary accent, window background, secondary background, font, border, icon color, and cover progress color overrides for live previewing"""
        try:
            set_icon_color(icon_hex or "#cccccc")
            set_icon_stroke_width(icon_thickness)
            self.reload_icons()
            
            from styles import StyleManager
            overrides = {}
            if accent_hex:
                overrides["accent"] = accent_hex
            if window_hex:
                overrides["bg-main"] = window_hex
            if bg_dark_hex:
                overrides["bg-dark"] = bg_dark_hex
            if text_hex:
                overrides["text"] = text_hex
            if border_hex:
                overrides["border"] = border_hex
            if status_new_hex:
                overrides["status-error"] = status_new_hex
            if status_started_hex:
                overrides["status-warning"] = status_started_hex
            if status_completed_hex:
                overrides["status-ok"] = status_completed_hex
            if cover_progress_hex:
                overrides["theme-primary"] = cover_progress_hex
            StyleManager.apply_style(QApplication.instance(), theme=self.current_theme, overrides=overrides)
            
            # Apply temporary settings if previewing
            if hasattr(self, "appearance_dialog") and self.appearance_dialog:
                settings = self.appearance_dialog.get_info_settings()
                if self.delegate:
                    self.delegate.show_detailed_info = settings["show_detailed_info"]
                    self.delegate.show_info_progress = settings["show_info_progress"]
                    self.delegate.show_info_file_count = settings["show_info_file_count"]
                    self.delegate.show_info_duration = settings["show_info_duration"]
                    self.delegate.show_info_size = settings["show_info_size"]
                    self.delegate.show_info_technical = settings["show_info_technical"]
                    self.delegate.show_info_year_written = settings["show_info_year_written"]
                    self.delegate.show_info_year_recorded = settings["show_info_year_recorded"]
                    self.delegate.show_info_language = settings["show_info_language"]
                    self.delegate.info_order = settings.get("info_order", self.delegate.info_order)
                
                # Interface settings preview
                interface_settings = self.appearance_dialog.get_interface_settings()
                
                # Visualizer
                if hasattr(self, "player_widget") and self.player_widget.play_btn.visualizer_enabled != interface_settings["show_visualizer"]:
                    self.player_widget.play_btn.visualizer_enabled = interface_settings["show_visualizer"]
                    self.player_widget.play_btn.update()
                
                # Nesting lines & status triangle
                if self.delegate:
                    self.delegate.show_nesting_lines = interface_settings["show_nesting_lines"]
                    self.delegate.nesting_lines_single_color = interface_settings["nesting_lines_single_color"]
                    self.delegate.nesting_lines_color = interface_settings["nesting_lines_color"]
                    self.delegate.show_status_triangle = interface_settings["show_status_triangle"]
                if hasattr(self, "library_widget") and self.library_widget:
                    self.library_widget.show_nesting_lines = interface_settings["show_nesting_lines"]
                    self.library_widget.nesting_lines_single_color = interface_settings["nesting_lines_single_color"]
                    self.library_widget.nesting_lines_color = interface_settings["nesting_lines_color"]
                    self.library_widget.show_status_triangle = interface_settings["show_status_triangle"]
                    if hasattr(self.library_widget, "tile_view") and self.library_widget.tile_view:
                        if hasattr(self.library_widget.tile_view, "canvas") and self.library_widget.tile_view.canvas:
                            self.library_widget.tile_view.canvas.update_layout()
                            self.library_widget.tile_view.canvas.update()
                
                # Status bar
                if self.statusBar().isVisible() != interface_settings["show_statusbar"]:
                    self.statusBar().setVisible(interface_settings["show_statusbar"])
                
                # Remember filter folders
                if hasattr(self, "library_widget") and self.library_widget.remember_filter_folders != interface_settings["remember_filter_folders"]:
                    self.library_widget.remember_filter_folders = interface_settings["remember_filter_folders"]
                


            if self.delegate:
                self.delegate.update_styles()
                
            StyleManager.refresh_cache()
            self.update()
            if hasattr(self, "library_widget") and self.library_widget:
                if hasattr(self.library_widget, "tree"):
                    self.library_widget.tree.doItemsLayout()
                    self.library_widget.tree.viewport().update()
        except Exception as e:
            print(f"Error applying appearance preview: {e}")

    def save_appearance_colors(self, accent_hex: str, window_hex: str, bg_dark_hex: str, text_hex: str = "", border_hex: str = "",
                               status_new_hex: str = "", status_started_hex: str = "", status_completed_hex: str = "", icon_hex: str = "",
                               cover_progress_hex: str = "", icon_thickness: float = 2.0):
        """Save the chosen accent, window, secondary background, font, border, icon, and cover progress colors to settings.ini and apply them permanently"""
        self.accent_color = accent_hex
        self.window_color = window_hex
        self.bg_dark_color = bg_dark_hex
        self.text_color = text_hex
        self.border_color = border_hex
        self.status_new_color = status_new_hex
        self.status_started_color = status_started_hex
        self.status_completed_color = status_completed_hex
        self.icon_color = icon_hex
        self.icon_thickness = icon_thickness
        self.cover_progress_color = cover_progress_hex
        self.save_setting("Appearance", "accent_color", accent_hex)
        self.save_setting("Appearance", "window_color", window_hex)
        self.save_setting("Appearance", "bg_dark_color", bg_dark_hex)
        self.save_setting("Appearance", "text_color", text_hex)
        self.save_setting("Appearance", "border_color", border_hex)
        self.save_setting("Appearance", "status_new_color", status_new_hex)
        self.save_setting("Appearance", "status_started_color", status_started_hex)
        self.save_setting("Appearance", "status_completed_color", status_completed_hex)
        self.save_setting("Appearance", "cover_progress_color", cover_progress_hex)
        self.save_setting("Appearance", "icon_color", icon_hex)
        self.save_setting("Appearance", "icon_thickness", str(icon_thickness))
        
        set_icon_color(icon_hex or "#cccccc")
        set_icon_stroke_width(icon_thickness)
        self.reload_icons()
        
        if hasattr(self, "appearance_dialog") and self.appearance_dialog:
            settings = self.appearance_dialog.get_info_settings()
            self.show_detailed_info = settings["show_detailed_info"]
            self.show_info_progress = settings["show_info_progress"]
            self.show_info_file_count = settings["show_info_file_count"]
            self.show_info_duration = settings["show_info_duration"]
            self.show_info_size = settings["show_info_size"]
            self.show_info_technical = settings["show_info_technical"]
            self.show_info_year_written = settings["show_info_year_written"]
            self.show_info_year_recorded = settings["show_info_year_recorded"]
            self.show_info_language = settings["show_info_language"]
            self.info_order = settings.get("info_order", self.info_order)
            
            self.save_setting("Library", "show_detailed_info", str(self.show_detailed_info))
            self.save_setting("Library", "show_info_progress", str(self.show_info_progress))
            self.save_setting("Library", "show_info_file_count", str(self.show_info_file_count))
            self.save_setting("Library", "show_info_duration", str(self.show_info_duration))
            self.save_setting("Library", "show_info_size", str(self.show_info_size))
            self.save_setting("Library", "show_info_technical", str(self.show_info_technical))
            self.save_setting("Library", "show_info_year_written", str(self.show_info_year_written))
            self.save_setting("Library", "show_info_year_recorded", str(self.show_info_year_recorded))
            self.save_setting("Library", "show_info_language", str(self.show_info_language))
            self.save_setting("Library", "info_order", self.info_order)
            
            if self.delegate:
                self.delegate.show_detailed_info = self.show_detailed_info
                self.delegate.show_info_progress = self.show_info_progress
                self.delegate.show_info_file_count = self.show_info_file_count
                self.delegate.show_info_duration = self.show_info_duration
                self.delegate.show_info_size = self.show_info_size
                self.delegate.show_info_technical = self.show_info_technical
                self.delegate.show_info_year_written = self.show_info_year_written
                self.delegate.show_info_year_recorded = self.show_info_year_recorded
                self.delegate.show_info_language = self.show_info_language
                self.delegate.info_order = self.info_order
                
            interface_settings = self.appearance_dialog.get_interface_settings()
            

                
            if interface_settings["show_statusbar"] != self.show_statusbar:
                self.toggle_statusbar(interface_settings["show_statusbar"])
            else:
                self.save_setting("Display", "show_statusbar", str(self.show_statusbar))
                
            if interface_settings["remember_filter_folders"] != self.remember_filter_folders:
                self.toggle_remember_filter_folders(interface_settings["remember_filter_folders"])
            else:
                self.save_setting("Library", "remember_filter_folders", str(self.remember_filter_folders))

            if interface_settings["show_nesting_lines"] != self.show_nesting_lines:
                self.toggle_nesting_lines(interface_settings["show_nesting_lines"])
            else:
                self.save_setting("Library", "show_nesting_lines", str(self.show_nesting_lines))

            self.nesting_lines_single_color = interface_settings["nesting_lines_single_color"]
            self.nesting_lines_color = interface_settings["nesting_lines_color"]
            self.save_setting("Library", "nesting_lines_single_color", str(self.nesting_lines_single_color))
            self.save_setting("Library", "nesting_lines_color", str(self.nesting_lines_color))
            if self.delegate:
                self.delegate.nesting_lines_single_color = self.nesting_lines_single_color
                self.delegate.nesting_lines_color = self.nesting_lines_color
            if hasattr(self, "library_widget") and self.library_widget:
                self.library_widget.nesting_lines_single_color = self.nesting_lines_single_color
                self.library_widget.nesting_lines_color = self.nesting_lines_color

            if interface_settings["show_status_triangle"] != self.show_status_triangle:
                self.toggle_status_triangle(interface_settings["show_status_triangle"])
            else:
                self.save_setting("Library", "show_status_triangle", str(self.show_status_triangle))

            if interface_settings["show_visualizer"] != self.show_visualizer:
                self.toggle_visualizer(interface_settings["show_visualizer"])
            else:
                self.save_setting("Player", "show_visualizer", str(self.show_visualizer))
                
        self.reload_styles()
        if hasattr(self, "library_widget") and self.library_widget:
            if hasattr(self.library_widget, "tree"):
                self.library_widget.tree.doItemsLayout()
                self.library_widget.tree.viewport().update()

    def apply_accent_preview(self, color_hex: str):
        """Apply a temporary accent color override for live previewing (backward compatibility)"""
        try:
            from styles import StyleManager
            overrides = {}
            if color_hex:
                overrides["accent"] = color_hex
            if getattr(self, "window_color", ""):
                overrides["bg-main"] = self.window_color
            if getattr(self, "bg_dark_color", ""):
                overrides["bg-dark"] = self.bg_dark_color
            StyleManager.apply_style(QApplication.instance(), theme=self.current_theme, overrides=overrides)
            
            if self.delegate:
                self.delegate.update_styles()
                
            StyleManager.refresh_cache()
            self.update()
        except Exception as e:
            print(f"Error applying accent preview: {e}")

    def save_accent_color(self, color_hex: str):
        """Save the chosen accent color to settings.ini and apply it permanently (backward compatibility)"""
        self.accent_color = color_hex
        self.save_setting("Appearance", "accent_color", color_hex)
        self.reload_styles()

    def show_settings(self):
        """Display the configuration dialog for managing library paths, system binaries, and data preferences"""
        # Apply blur effect
        self.apply_blur()

        dialog = SettingsDialog(
            self,
            self.default_path,
            self.ffprobe_path,
            db_manager=self.db_manager,
            auto_check=self.auto_check_updates,
            opus_workers=self.opus_workers,
        )

        def on_path_saved(new_path):
            """Commit new root path and initiate a library refresh if the configuration has changed"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                # Synchronize root path in the playback controller
                if hasattr(self, "playback_controller"):
                    self.playback_controller.library_root = Path(new_path)

                # Update library widget config
                if hasattr(self, "library_widget"):
                    self.library_widget.config["default_path"] = new_path
                    self.library_widget.load_audiobooks()

                print(f"DEBUG: Path saved in main.py. New path: {new_path}")
                self.statusBar().showMessage(tr("status.path_saved"))

        def on_scan_requested(new_path, force_rescan):
            """Apply the new path and immediately trigger a directory scan"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                if hasattr(self, "playback_controller"):
                    self.playback_controller.library_root = Path(new_path)

                # Update library widget config
                if hasattr(self, "library_widget"):
                    self.library_widget.config["default_path"] = new_path

            print(f"DEBUG: Scan requested. Updating library config path to: {new_path}, force_rescan: {force_rescan}")
            self.rescan_directory(force_rescan=force_rescan)

        conversion_performed = False

        def on_conversion_complete():
            nonlocal conversion_performed
            conversion_performed = True

        def on_auto_update_toggled(checked):
            self.auto_check_updates = checked
            self.save_settings()

        def on_opus_workers_changed(workers):
            self.opus_workers = workers
            self.save_settings()
            if hasattr(self, "library_widget"):
                self.library_widget.config["opus_workers"] = workers

        # Connect signals
        dialog.path_saved.connect(on_path_saved)
        dialog.scan_requested.connect(on_scan_requested)
        dialog.data_reset_requested.connect(self.perform_full_reset)
        dialog.opus_convert_requested.connect(on_conversion_complete)
        dialog.auto_update_toggled.connect(on_auto_update_toggled)
        dialog.opus_workers_changed.connect(on_opus_workers_changed)

        dialog.exec()
        self.remove_blur()

        if conversion_performed:
            self.on_opus_conversion_complete()

    def on_opus_conversion_complete(self):
        """Rescan library after opus conversion to reflect updated files"""
        self.rescan_directory()
        self.statusBar().showMessage(tr("opus_converter.conversion_done"))

    def perform_full_reset(self):
        """Execute a comprehensive wipe of all library metadata, database records, and extracted cover assets while the application remains active"""
        try:
            # 1. Stop active playback and unload file to release locks
            self.player.unload()

            # End active listening session if any
            if hasattr(self, 'listening_tracker'):
                self.listening_tracker.end_session()

            # 2. Reset the internal state of the playback controller
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = ""
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0

            # 3. Clear the tree and filter state
            self.library_widget.search_edit.clear()
            self.library_widget.cached_library_data = None
            self.library_widget.tree.clear()

            # 4. Wipe all database tables
            self.db_manager.clear_all_data()

            # 5. Delete the extracted covers repository
            if self.covers_dir.exists():
                try:
                    shutil.rmtree(self.covers_dir)
                except Exception as e:
                    print(f"Could not delete covers dir: {e}")

            # 6. Synchronize UI components to the empty state
            self.update_ui_for_audiobook()  # Resets labels and playlist

            # Reset player UI components specifically
            self.player_widget.position_slider.setValue(0)
            self.player_widget.total_progress_bar.setValue(0)
            self.player_widget.time_current.setText("0:00")
            self.player_widget.time_duration.setText("0:00")
            self.player_widget.total_time_label.setText("0:00:00")
            self.player_widget.total_duration_label.setText("0:00:00")
            self.player_widget.total_percent_label.setText(
                trf("formats.percent", value=0)
            )
            self.player_widget.time_left_label.setText(tr("player.time_left_unknown"))

            if self.delegate:
                self.delegate.playing_path = None  # Remove tree highlighting
            self.library_widget.load_audiobooks()  # Populate empty tree
            if hasattr(self.library_widget, "update_tile_playback_state"):
                self.library_widget.update_tile_playback_state()

            self.statusBar().showMessage(tr("status.reset_success"))

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to completely clear library data: {e}"
            )

    def on_delete_requested(self, audiobook_id: int, rel_path: str, delete_from_disk: bool = False):
        """Coordinate the comprehensive removal of an audiobook from the filesystem, database, and UI"""
        if not self.default_path:
            return

        abs_path = Path(self.default_path) / rel_path

        # 1. Terminate active playback if the target book is currently loaded
        if self.playback_controller.current_audiobook_id == audiobook_id:
            self.unload_active_book(save_progress=False)

        # 2. Delete the files from the disk if requested
        if delete_from_disk and abs_path.exists():
            try:
                if abs_path.is_dir():
                    shutil.rmtree(abs_path)
                else:
                    abs_path.unlink()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    tr("library.confirm_delete_title"),
                    trf("library.delete_error", error=str(e)),
                )
                return

        # 3. Finalize data synchronization across database and view
        try:
            self.db_manager.delete_audiobook(audiobook_id)
            self.library_widget.remove_audiobook_from_ui(rel_path)
            self.statusBar().showMessage(tr("status.delete_success"))
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("library.confirm_delete_title"),
                trf("library.delete_error", error=str(e)),
            )

    def on_folder_delete_requested(self, rel_path: str):
        """Recursively remove a folder and its contents from the player, database, and UI"""
        # 1. Check if currently playing audiobook is inside this folder
        current_book_path = self.playback_controller.current_audiobook_path
        inside_folder = current_book_path == rel_path or current_book_path.startswith(
            rel_path + os.sep
        )

        if inside_folder:
            self.unload_active_book(save_progress=False)

        # 2. Database and UI synchronization
        try:
            self.db_manager.delete_folder(rel_path)
            self.library_widget.remove_folder_from_ui(rel_path)
            self.statusBar().showMessage(tr("status.delete_success"))
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("library.confirm_delete_folder_title"),
                trf("library.delete_error", error=str(e)),
            )

    def apply_blur(self):
        """Increment blur request counter and apply graphics effect to the entire window"""
        self._blur_count += 1
        if self._blur_count == 1:
            if not self._blur_effect:
                self._blur_effect = QGraphicsBlurEffect()
                self._blur_effect.setBlurRadius(5)

            # Apply to the entire window (self) instead of centralWidget to include menu bar and status bar
            self.setGraphicsEffect(self._blur_effect)

    def remove_blur(self):
        """Decrement blur request counter and remove graphics effect if zero"""
        self._blur_count = max(0, self._blur_count - 1)
        if self._blur_count == 0:
            self.setGraphicsEffect(None)
            self._blur_effect = None

    def show_about(self):
        """Display the application information dialog, including versioning and credit details"""
        # Apply blur effect
        self.apply_blur()

        dialog = AboutDialog(self)
        dialog.exec()

        # Remove blur effect
        self.remove_blur()

    def check_for_updates_auto(self):
        """Silently check for updates on startup"""
        if not self.auto_check_updates:
            return
        self._update_check_thread = UpdateCheckThread()
        self._update_check_thread.result_ready.connect(self._on_update_check_auto)
        self._update_check_thread.start()

    def _on_update_check_auto(self, result):
        """Handle auto-check result (silent - only show if update available)"""
        if result.update_available:
            self._show_update_dialog(result)

    def check_for_updates_manual(self):
        """Manual check for updates from menu"""
        self._update_check_thread = UpdateCheckThread()
        self._update_check_thread.result_ready.connect(self._on_update_check_manual)
        self._update_check_thread.start()
        self.statusBar().showMessage(tr("updater.checking"))

    def _on_update_check_manual(self, result):
        """Handle manual check result (show message even if up-to-date)"""
        if result.error:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(tr("error"))
            
            error_msg = trf("updater.check_error", error=result.error)
            manual_hint = tr("updater.manual_download_hint")
            
            msg_box.setText(f"{error_msg}<br><br>{manual_hint}")
            msg_box.setTextFormat(Qt.TextFormat.RichText)
            msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            msg_box.exec()
        elif result.update_available:
            self._show_update_dialog(result)
        else:
            QMessageBox.information(
                self,
                tr("info"),
                trf(
                    "updater.up_to_date",
                    version=result.remote_version or get_current_version(),
                ),
            )

    def _show_update_dialog(self, result):
        """Show the update dialog"""
        self.apply_blur()
        dialog = UpdateDialog(result, self)
        dialog.update_accepted.connect(self._on_update_restart)
        dialog.exec()
        self.remove_blur()

    def _on_update_restart(self):
        """Handle restart request from update dialog"""
        # Save current session before closing
        self.save_last_session()
        self.save_settings()
        # Close the application to let the update script take over
        QApplication.quit()

    def save_setting(self, section: str, key: str, value: str):
        """Update a specific configuration entry in 'settings.ini' without overwriting other existing sections"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding="utf-8")

        if not value:
            if section in config and key in config[section]:
                del config[section][key]
                if not config[section]:
                    del config[section]
        else:
            if section not in config:
                config[section] = {}
            config[section][key] = value

        with open(self.config_file, "w", encoding="utf-8") as f:
            config.write(f)

    def closeEvent(self, event):
        """Perform cleanup operations upon application termination, including session saving and engine release"""
        self.save_settings()

        # Check if the current audiobook is completed to skip automatic rewinding
        is_completed = False
        if self.playback_controller.current_audiobook_id:
            try:
                import sqlite3
                connection = sqlite3.connect(self.db_file)
                cursor = connection.cursor()
                cursor.execute("SELECT is_completed FROM audiobooks WHERE id = ?", (self.playback_controller.current_audiobook_id,))
                row = cursor.fetchone()
                connection.close()
                if row and row[0] == 1:
                    is_completed = True
            except Exception as e:
                print(f"Error checking is_completed in closeEvent: {e}")

        if self.auto_rewind and not is_completed:
            self.player.rewind(-30)

        self.playback_controller.save_current_progress()
        self.save_last_session()
        
        # Close active listening session
        if hasattr(self, 'listening_tracker'):
            self.listening_tracker.end_session()
        
        self.taskbar_progress.clear()

        # Unregister global hotkeys
        if hasattr(self, "hotkey_manager"):
            self.hotkey_manager.unregister_all()

        self.player.free()
        event.accept()


from PyQt6.QtCore import QAbstractNativeEventFilter


class TaskbarEventFilter(QAbstractNativeEventFilter):
    """Custom event filter for intercepting Windows-native messages specifically for taskbar thumbnail button interactions"""

    def __init__(self, window):
        super().__init__()
        self.window = window

    def nativeEventFilter(self, eventType, message):
        """Monitor for native Windows messages, including WM_COMMAND and WM_POWERBROADCAST for sleep/wake recovery"""
        if eventType == b"windows_generic_MSG" and message:
            try:
                msg_ptr = int(message)
                if msg_ptr:
                    msg = wintypes.MSG.from_address(msg_ptr)

                    # Handle multimedia keys and other global hotkeys via HotKeyManager
                    if self.window.hotkey_manager.handle_native_event(msg):
                        return True, 0

                    # Handle system resume from sleep to refresh taskbar progress state cache
                    if msg.message == 0x0218:  # WM_POWERBROADCAST
                        # PBT_APMRESUMEAUTOMATIC = 0x0012, PBT_APMRESUMESUSPEND = 0x0007
                        if msg.wParam in (0x0012, 0x0007):
                            if hasattr(self.window, "taskbar_progress"):
                                self.window.taskbar_progress.refresh_state()

                    if msg.message == 0x0111:  # WM_COMMAND
                        if (msg.wParam >> 16) & 0xFFFF == 0x1800:  # THBN_CLICKED
                            button_id = msg.wParam & 0xFFFF
                            if button_id == 0:
                                self.window.on_prev_clicked()
                                return True, 0
                            elif button_id == 1:
                                self.window.toggle_play()
                                return True, 0
                            elif button_id == 2:
                                self.window.on_next_clicked()
                                return True, 0
                            elif button_id == 3:
                                self.window.on_rewind_10_clicked()
                                return True, 0
                            elif button_id == 4:
                                self.window.on_forward_10_clicked()
                                return True, 0
            except Exception:
                # Silently fail on malformed Windows messages
                pass
        return False, 0


def main():
    """Application entry point: initializes the Qt application context, registers native event filters, and launches the main window"""
    import traceback
    import datetime

    def log_uncaught_exception(exctype, value, tb):
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        print("CRITICAL ERROR (Uncaught Exception):", err_msg, file=sys.stderr)
        
        try:
            log_dir = get_base_path() / "data"
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "crash.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now().isoformat()}] Uncaught Exception:\n")
                f.write(err_msg)
                f.write("="*80 + "\n")
        except Exception as log_err:
            print(f"Failed to write crash log: {log_err}", file=sys.stderr)
            
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = log_uncaught_exception

    try:
        print("Starting SPAudiobookPlayer...")
        app = QApplication(sys.argv)
        print("QApplication created.")

        app.setStyle("Fusion")
        # Load theme from settings
        config = configparser.ConfigParser()
        config_dir = get_base_path() / "resources"
        config_file = config_dir / "settings.ini"
        current_theme = "dark"
        accent_color = ""
        window_color = ""
        bg_dark_color = ""
        text_color = ""
        border_color = ""
        status_new_color = ""
        status_started_color = ""
        status_completed_color = ""
        cover_progress_color = ""
        if config_file.exists():
            config.read(config_file, encoding="utf-8")
            current_theme = config.get("Display", "theme", fallback="dark")
            accent_color = config.get("Appearance", "accent_color", fallback="")
            window_color = config.get("Appearance", "window_color", fallback="")
            bg_dark_color = config.get("Appearance", "bg_dark_color", fallback="")
            text_color = config.get("Appearance", "text_color", fallback="")
            border_color = config.get("Appearance", "border_color", fallback="")
            status_new_color = config.get("Appearance", "status_new_color", fallback="")
            status_started_color = config.get("Appearance", "status_started_color", fallback="")
            status_completed_color = config.get("Appearance", "status_completed_color", fallback="")
            cover_progress_color = config.get("Appearance", "cover_progress_color", fallback="")

        # Apply Stylesheet
        overrides = {}
        if accent_color:
            overrides["accent"] = accent_color
        if window_color:
            overrides["bg-main"] = window_color
        if bg_dark_color:
            overrides["bg-dark"] = bg_dark_color
        if text_color:
            overrides["text"] = text_color
        if border_color:
            overrides["border"] = border_color
        if status_new_color:
            overrides["status-error"] = status_new_color
        if status_started_color:
            overrides["status-warning"] = status_started_color
        if status_completed_color:
            overrides["status-ok"] = status_completed_color
        if cover_progress_color:
            overrides["theme-primary"] = cover_progress_color
        StyleManager.apply_style(app, theme=current_theme, overrides=overrides)

        print("Initializing Style Manager...")
        StyleManager.init(app)

        print("Initializing Main Window...")
        window = AudiobookPlayerWindow()

        # Connect player instance to visualizer button
        if hasattr(window, "player_widget") and hasattr(window, "player"):
            if hasattr(window.player_widget, "play_btn"):
                window.player_widget.play_btn.set_player(window.player)

        # Register the native event filter for taskbar button interaction
        event_filter = TaskbarEventFilter(window)
        app.installNativeEventFilter(event_filter)

        print("Showing window.")
        window.show()
        window.activateWindow()
        window.raise_()

        sys.exit(app.exec())
    except Exception as e:
        print("\n" + "=" * 50)
        print("CRITICAL STARTUP ERROR:")
        print("=" * 50)
        traceback.print_exc()
        print("=" * 50)
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
