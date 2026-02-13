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
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QMessageBox,
    QHBoxLayout, QLineEdit, QMenu, QStyle, QPushButton, QButtonGroup, 
    QDialog, QDialogButtonBox, QGroupBox, QLabel, QFileDialog, QSlider, 
    QProgressBar, QListWidget, QListWidgetItem, QFrame, QTextEdit, QSizePolicy,
    QGraphicsBlurEffect
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QRect, QRectF, QPoint, QPointF, QThread, QByteArray, QUrl
from PyQt6.QtGui import (
    QIcon, QAction, QPixmap, QBrush, QColor, QFont, QPen, QPainter, QPolygon,
    QTextCursor, QPainterPath, QFontMetrics, QDesktopServices
)

from bass_player import BassPlayer
from database import DatabaseManager
from styles import DARK_STYLE, DARK_QSS_PATH, StyleManager
from taskbar_progress import TaskbarProgress, TaskbarThumbnailButtons
import ctypes
from hotkeys import HotKeyManager
from player import PlayerWidget, PlaybackController

from bookmarks_dialog import BookmarksListDialog
from settings_dialog import SettingsDialog
from translations import tr, trf, get_available_languages, get_language, set_language, Language
from utils import (
    get_base_path, get_icon, load_icon, resize_icon, 
    format_duration, format_time, format_time_short, OutputCapture
)

# New module imports
from player import PlaybackController, PlayerWidget
from library import (
    ScannerThread, ScanProgressDialog, 
    LibraryTree, MultiLineDelegate, LibraryWidget
)


class AudiobookPlayerWindow(QMainWindow):
    def __init__(self):
        """Initialize the main application window, establishing directory structures, loading configurations, and assembling core components"""
        super().__init__()
        
        # Filesystem path orchestration
        self.script_dir = get_base_path()
        self.config_dir = self.script_dir / 'resources'
        self.data_dir = self.script_dir / 'data'
        
        self.config_file = self.config_dir / 'settings.ini'
        self.db_file = self.data_dir / 'audiobooks.db'
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
        self.deesser_preset = 1 # 0=Light, 1=Medium, 2=Strong
        self.compressor_preset = 1 # 0=Light, 1=Medium, 2=Strong
        self.pitch_enabled = False
        self.pitch_value = 0.0
        self.last_pause_time = None
        
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
            
        self.taskbar_progress = TaskbarProgress()
        
        # UI Presentation Delegate Initialization
        self.delegate = None
        try:
            self.delegate = MultiLineDelegate(self)
            self.delegate.audiobook_row_height = self.audiobook_row_height
            self.delegate.folder_row_height = self.folder_row_height
            self.delegate.audiobook_icon_size = self.audiobook_icon_size
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
            display_restored = self.restoreGeometry(QByteArray.fromHex(self.saved_geometry_hex.encode()))
        
        if not display_restored:
            # Fallback to manual coordinates, but ensure they are sane
            # Fix potential "creeping" issues from previous bugs where coordinates became negative or zero
            safe_x = max(0, self.window_x)
            safe_y = max(30, self.window_y) # Ensure title bar is likely visible
            safe_width = max(450, self.window_width)
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
        
        self.setMinimumSize(450, 450)
        self.statusBar().showMessage(tr("status.load_library"))
        
        # Blur Effect Stacking logic to handle nested modal dialogs
        self._blur_count = 0
        self._blur_effect = None
        
        # Ensure the main window has focus so hotkeys work correctly
        self.setFocus()
    
    def load_language_preference(self):
        """Retrieve and apply the user's preferred application language from the configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        lang_code = config.get('Display', 'language', fallback='ru')
        
        # Verify language code exists in available languages
        available_codes = [lang[0] for lang in get_available_languages()]
        if lang_code in available_codes:
            set_language(lang_code)
        else:
            set_language(Language.RUSSIAN)
    
    def save_language_preference(self):
        """Commit the current language setting to the persistent configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'Display' not in config:
            config['Display'] = {}
        
        config['Display']['language'] = get_language()
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
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
                'audiobook_icon_size': self.audiobook_icon_size,
                'folder_icon_size': self.folder_icon_size,
                'default_cover_file': self.default_cover_file,
                'folder_cover_file': self.folder_cover_file,
                'default_path': self.default_path,
                'ffprobe_path': self.ffprobe_path,
                'tag_filter_active': self.tag_filter_active,
                'tag_filter_ids': self.tag_filter_ids
            },
            self.delegate,
            show_folders=self.show_folders,
            show_filter_labels=self.show_filter_labels
        )
        self.library_widget.setMinimumWidth(200)
        self.splitter.addWidget(self.library_widget)
        
        # Playback Controls Component
        self.player_widget = PlayerWidget()
        self.player_widget.setMinimumWidth(400)
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.on_id3_toggled(self.show_id3)
        
        self.player_widget.id3_toggled_signal.connect(self.on_id3_state_toggled)
        
        self.player_widget.auto_rewind_toggled_signal.connect(self.on_auto_rewind_state_toggled)
        
        self.player_widget.deesser_toggled_signal.connect(self.on_deesser_state_toggled)
        
        self.player_widget.compressor_toggled_signal.connect(self.on_compressor_state_toggled)
        
        self.player_widget.noise_suppression_toggled_signal.connect(self.on_noise_suppression_state_toggled)
        
        self.player_widget.pitch_toggled_signal.connect(self.on_pitch_toggled)
        self.player_widget.pitch_changed_signal.connect(self.on_pitch_changed)
        
        # VAD threshold slider
        self.player_widget.vad_threshold_changed_signal.connect(self.on_vad_threshold_changed)
        
        # VAD grace period sliders
        self.player_widget.vad_grace_period_changed_signal.connect(self.on_vad_grace_period_changed)
        self.player_widget.vad_retroactive_grace_changed_signal.connect(self.on_vad_retro_grace_changed)

        # DeEsser & Compressor Presets
        self.player_widget.deesser_preset_changed_signal.connect(self.on_deesser_preset_changed)
        self.player_widget.compressor_preset_changed_signal.connect(self.on_compressor_preset_changed)
        
        # Set initial states
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.auto_rewind_btn.setChecked(self.auto_rewind)
        self.player_widget.deesser_btn.setChecked(self.deesser_enabled)
        self.player_widget.compressor_btn.setChecked(self.compressor_enabled)
        self.player_widget.noise_suppression_btn.setChecked(self.noise_suppression_enabled)
        self.player_widget.pitch_btn.setChecked(self.pitch_enabled)
        
        # Set initial values for sliders
        self.player_widget.set_vad_threshold_value(self.vad_threshold)
        self.player_widget.set_vad_grace_value(self.vad_grace_period)
        self.player_widget.set_vad_retro_value(self.vad_retroactive_grace)
        self.player_widget.set_deesser_preset_value(self.deesser_preset)
        self.player_widget.set_compressor_preset_value(self.compressor_preset)
        self.player_widget.set_pitch_value(self.pitch_value)
        
        self.splitter.addWidget(self.player_widget)
        
        main_layout.addWidget(self.splitter, 1)
    
    def setup_menu(self):
        """Construct the main application menu bar, including Library, View, and Help menus with localized actions"""
        menubar = self.menuBar()
        

        library_menu = menubar.addMenu(tr("menu.library"))
        
        # Global Settings Context
        settings_action = QAction(tr("menu.settings"), self)
        settings_action.setIcon(get_icon("menu_settings"))
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        library_menu.addAction(settings_action)

        library_menu.addSeparator()
        
        # Directory Synchronization
        scan_action = QAction(tr("menu.scan"), self)
        scan_action.setIcon(get_icon("menu_scan"))
        scan_action.setShortcut("Ctrl+R")
        scan_action.triggered.connect(self.rescan_directory)
        library_menu.addAction(scan_action)
        
        # Open Library Folder
        open_folder_action = QAction(tr("menu.open_library_folder"), self)
        open_folder_action.setIcon(get_icon("context_open_folder"))
        open_folder_action.triggered.connect(self.open_library_folder)
        library_menu.addAction(open_folder_action)
        

        view_menu = menubar.addMenu(tr("menu.view"))
        
        # Language Selection Nested Menu
        language_menu = view_menu.addMenu(tr("menu.language"))
        
        available_langs = get_available_languages()
        self.language_actions = {}
        
        for code, name in available_langs:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(get_language() == code)
            # Use default argument to capture current loop variable
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            language_menu.addAction(action)
            self.language_actions[code] = action
        
        view_menu.addSeparator()
        
        # Theme Selection
        theme_menu = view_menu.addMenu(tr("menu.theme"))
        self.theme_actions = {}
        for theme_id, theme_name in [("dark", "Dark Mint"), ("miku", "Dark Pink")]:
            action = QAction(theme_name, self)
            action.setCheckable(True)
            action.setChecked(self.current_theme == theme_id)
            action.triggered.connect(lambda checked, t=theme_id: self.change_theme(t))
            theme_menu.addAction(action)
            self.theme_actions[theme_id] = action
        
        theme_menu.addSeparator()
        
        # CSS Refresh Action (Nested in Theme menu)
        reload_styles_action = QAction(tr("menu.reload_styles"), self)
        reload_styles_action.setIcon(get_icon("menu_reload"))
        reload_styles_action.setShortcut("Ctrl+Q")
        reload_styles_action.triggered.connect(self.reload_styles)
        theme_menu.addAction(reload_styles_action)
        

        help_menu = menubar.addMenu(tr("menu.help"))
        
        # About Dialog Trigger
        about_action = QAction(tr("menu.about"), self)
        about_action.setIcon(get_icon("menu_about"))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
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
        
    def change_theme(self, theme: str):
        """Update the application's visual theme and immediately refresh all UI components"""
        if self.current_theme == theme:
            return
        
        self.current_theme = theme
        self.save_settings()
        
        # Synchronize checkmarks in the theme menu
        for t, action in self.theme_actions.items():
            action.setChecked(t == theme)
        
        # Apply the new theme
        self.reload_styles()
    
    def update_all_texts(self):
        """Synchronize window titles, menus, and sub-widget labels after a language change event"""
        # Revise window title with localized formatting
        if hasattr(self, 'playback_controller') and self.playback_controller.current_audiobook_path:
            book_title = self.playback_controller.get_audiobook_title()
            self.setWindowTitle(trf("window.title_with_book", title=book_title))
        else:
            self.setWindowTitle(tr("window.title"))
        
        # Reconstruct the menu bar to apply new translations
        self.menuBar().clear()
        self.setup_menu()
        
        # Refresh player controls
        if hasattr(self, 'player_widget'):
            self.player_widget.update_texts()
        
        # Refresh library filters and search fields
        if hasattr(self, 'library_widget'):
            self.library_widget.update_texts()
        
        # Reload the library tree to apply new delegate formatting
        if hasattr(self, 'library_widget'):
            self.library_widget.load_audiobooks()
    
    def open_library_folder(self):
        """Open the current library folder in the system's default file manager"""
        path = self.default_path
        if not path:
             # Try to get from controller if default_path is not set but controller has root
             if hasattr(self, 'playback_controller') and self.playback_controller.library_root:
                 path = str(self.playback_controller.library_root)
        
        if path and os.path.isdir(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.warning(self, tr("error"), tr("status.no_database")) # Using generic error or strictly "Path not found" if we had a key.
            # "status.no_database" says "Database not found...", maybe not perfect but close enough for "Library not set".
            # Better might be just a silent fail or console log if we want to be less obtrusive, 
            # but user clicked a button so they expect something.
            # Let's check if we have a better key. "settings.specify_path" is "Specify path...".
            pass
    
    def connect_signals(self):
        """Map signals from sub-widgets (Library and Player) to their respective handler methods in the main window"""
        # Library Navigation Signals
        self.library_widget.audiobook_selected.connect(self.on_audiobook_selected)
        self.library_widget.tree.play_button_clicked.connect(self.on_library_play_clicked)
        self.library_widget.show_folders_toggled.connect(self.on_show_folders_toggled)
        self.library_widget.delete_requested.connect(self.on_delete_requested)
        self.library_widget.delete_requested.connect(self.on_delete_requested)
        self.library_widget.folder_delete_requested.connect(self.on_folder_delete_requested)
        self.library_widget.folder_delete_requested.connect(self.on_folder_delete_requested)
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

    def show_bookmarks(self):
        """Open the bookmarks manager dialog"""
        if not self.playback_controller.current_audiobook_id:
            QMessageBox.information(self, tr("info"), tr("bookmarks.no_book_playing")) # We might need a key for this or just fail silently/log.
            # Assuming we can just ignore if no book playing.
            return

        # Pause playback while managing bookmarks? iterating on user preference.
        # Let's keep it playing unless user wants to jump.
        # OR: capturing current position requires precision. If playing, it changes.
        # But we capture it at the moment of opening the dialog.
        
        current_pos = self.playback_controller.player.get_position()
        current_idx = self.playback_controller.current_file_index
        current_file = self.playback_controller.files_list[current_idx]['name'] if self.playback_controller.files_list else ""
        
        dlg = BookmarksListDialog(
            self, 
            self.db_manager, 
            self.playback_controller.current_audiobook_id,
            current_idx,
            current_file,
            current_pos
        )
        
        dlg.bookmark_selected.connect(self.playback_controller.jump_to_bookmark)
        dlg.exec()

    def load_settings(self):
        """Retrieve and initialize application state (paths, window geometry, styles) from the 'settings.ini' file"""
        if not self.config_file.exists():
            self.create_default_settings()
        
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        # Window Geometry Persistence
        self.window_x = config.getint('Display', 'window_x', fallback=100)
        self.window_y = config.getint('Display', 'window_y', fallback=100)
        self.window_width = config.getint('Display', 'window_width', fallback=1200)
        self.window_height = config.getint('Display', 'window_height', fallback=800)
        self.saved_geometry_hex = config.get('Display', 'window_geometry', fallback=None)
        self.current_theme = config.get('Display', 'theme', fallback='dark')
        
        # Filesystem Path Configurations
        self.default_path = config.get('Paths', 'default_path', fallback="")
        ff_path_str = config.get('Paths', 'ffprobe_path', fallback=str(self.script_dir / 'resources' / 'bin' / 'ffprobe.exe'))
        self.ffprobe_path = Path(ff_path_str)
        if not self.ffprobe_path.is_absolute():
            self.ffprobe_path = self.script_dir / self.ffprobe_path
            
        covers_dir_str = config.get('Paths', 'covers_dir', fallback='data/extracted_covers')
        self.covers_dir = Path(covers_dir_str)
        if not self.covers_dir.is_absolute():
            self.covers_dir = self.script_dir / self.covers_dir
            
        self.default_cover_file = config.get('Paths', 'default_cover_file', fallback='resources/icons/default_cover.png')
        self.folder_cover_file = config.get('Paths', 'folder_cover_file', fallback='resources/icons/folder_cover.png')
        
        # Visual Style Metrics
        self.audiobook_icon_size = config.getint('Audiobook_Style', 'icon_size', fallback=100)
        self.audiobook_row_height = config.getint('Audiobook_Style', 'row_height', fallback=120)
        self.folder_icon_size = config.getint('Folder_Style', 'icon_size', fallback=35)
        self.folder_row_height = config.getint('Folder_Style', 'row_height', fallback=45)
        
        # Splitter Layout State
        self.splitter_state = config.get('Layout', 'splitter_state', fallback="")
        
        # Player Functional Preferences
        self.show_id3 = config.getboolean('Player', 'show_id3', fallback=False)
        self.auto_rewind = config.getboolean('Player', 'auto_rewind', fallback=False)
        
        # Audio Settings (Unified in [Audio])
        self.deesser_enabled = config.getboolean('Audio', 'deesser', fallback=config.getboolean('Player', 'deesser_enabled', fallback=False))
        self.compressor_enabled = config.getboolean('Audio', 'compressor', fallback=config.getboolean('Player', 'compressor_enabled', fallback=False))
        self.noise_suppression_enabled = config.getboolean('Audio', 'noise_suppression', fallback=config.getboolean('Player', 'noise_suppression_enabled', fallback=False))
        self.vad_threshold = config.getint('Audio', 'vad_threshold', fallback=config.getint('Player', 'vad_threshold', fallback=90))
        self.vad_grace_period = config.getint('Audio', 'vad_grace_period', fallback=config.getint('Player', 'vad_grace_period', fallback=0))
        self.vad_retroactive_grace = config.getint('Audio', 'vad_retroactive_grace', fallback=config.getint('Player', 'vad_retroactive_grace', fallback=0))
        self.deesser_preset = config.getint('Audio', 'deesser_preset', fallback=1)
        self.compressor_preset = config.getint('Audio', 'compressor_preset', fallback=1)
        self.pitch_enabled = config.getboolean('Audio', 'pitch_enabled', fallback=False)
        self.pitch_value = config.getfloat('Audio', 'pitch_value', fallback=0.0)
        
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
        self.show_folders = config.getboolean('Library', 'show_folders', fallback=False)
        self.show_filter_labels = config.getboolean('Library', 'show_filter_labels', fallback=True)
        self.tag_filter_active = config.getboolean('Library', 'tag_filter_active', fallback=False)
        tag_ids_str = config.get('Library', 'tag_filter_ids', fallback="")
        self.tag_filter_ids = set()
        if tag_ids_str:
            try:
                self.tag_filter_ids = {int(x) for x in tag_ids_str.split(',') if x.strip()}
            except ValueError:
                pass
        
        # Synchronize library root with controller if active
        if hasattr(self, 'playback_controller'):
            if self.default_path:
                self.playback_controller.library_root = Path(self.default_path)
            else:
                self.playback_controller.library_root = None

    def create_default_settings(self):
        """Generate a fresh 'settings.ini' file with standard defaults for first-time application launch"""
        config = configparser.ConfigParser()
        config['Paths'] = {
            'default_path': '',
            'ffprobe_path': 'resources/bin/ffprobe.exe',
            'ffmpeg_path': 'resources/bin/ffmpeg.exe',
            'covers_dir': 'data/extracted_covers',
            'temp_dir': 'data/temp',
            'default_cover_file': 'resources/icons/default_cover.png',
            'folder_cover_file': 'resources/icons/folder_cover.png'
        }
        config['Audio'] = {
            'extensions': '.mp3,.m4a,.m4b,.mp4,.ogg,.flac,.wav,.aac,.wma,.opus,.ape'
        }
        config['Display'] = {
            'window_width': '1200',
            'window_height': '800',
            'window_x': '100',
            'window_y': '100',
            'language': 'en'
        }
        config['Audiobook_Style'] = {
            'icon_size': '100',
            'row_height': '120'
        }
        config['Folder_Style'] = {
            'icon_size': '35',
            'row_height': '45'
        }
        config['Layout'] = {
            'splitter_state': ''
        }
        config['Player'] = {
            'show_id3': 'True',
            'auto_rewind': 'True',
            'deesser_enabled': 'False',
            'compressor_enabled': 'False'
        }
        config['Library'] = {
            'show_folders': 'False',
            'show_filter_labels': 'False'
        }
        config['LastSession'] = {
            'last_audiobook_id': '0',
            'last_file_index': '0',
            'last_position': '0.0'
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)

    def save_settings(self):
        """Commit all current application settings (window state, paths, layout, styles) to the 'settings.ini' file"""
        config = configparser.ConfigParser()
        # Read the existing file first to preserve non-managed sections like 'LastSession'
        if self.config_file.exists():
            config.read(self.config_file, encoding='utf-8')
        
        # Serialized Window Geometry
        rect = self.geometry()
        if 'Display' not in config: config['Display'] = {}
        config['Display']['window_x'] = str(rect.x())
        config['Display']['window_y'] = str(rect.y())
        config['Display']['window_width'] = str(rect.width())
        config['Display']['window_height'] = str(rect.height())
        config['Display']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        config['Display']['theme'] = self.current_theme
        
        # Filesystem Path Configs
        if 'Paths' not in config: config['Paths'] = {}
        config['Paths']['default_path'] = self.default_path
        config['Paths']['default_cover_file'] = self.default_cover_file
        config['Paths']['folder_cover_file'] = self.folder_cover_file
        
        # Serialized Layout State
        if 'Layout' not in config: config['Layout'] = {}
        if hasattr(self, 'splitter'):
            config['Layout']['splitter_state'] = self.splitter.saveState().toHex().data().decode()
        
        # Player Functional Preferences
        if 'Player' not in config: config['Player'] = {}
        if hasattr(self, 'player_widget'):
            config['Audio'] = {
            'volume': str(self.player.vol_pos),
            'speed': str(self.player.speed_pos),
            'auto_rewind': str(self.auto_rewind),
            'deesser': str(self.deesser_enabled),
            'compressor': str(self.compressor_enabled),
            'noise_suppression': str(self.noise_suppression_enabled),
            'vad_threshold': str(self.vad_threshold),
            'vad_grace_period': str(self.vad_grace_period),
            'vad_retroactive_grace': str(self.vad_retroactive_grace),
            'deesser_preset': str(self.deesser_preset),
            'vac_grace_period': str(self.vad_grace_period),
            'vad_retroactive_grace': str(self.vad_retroactive_grace),
            'deesser_preset': str(self.deesser_preset),
            'compressor_preset': str(self.compressor_preset),
            'pitch_enabled': str(self.pitch_enabled),
            'pitch_value': str(self.pitch_value)
        }
        if 'Library' not in config: config['Library'] = {}
        config['Library']['show_folders'] = str(self.show_folders)
        config['Library']['show_filter_labels'] = str(self.show_filter_labels)
        if hasattr(self, 'library_widget'):
            config['Library']['tag_filter_active'] = str(self.library_widget.is_tag_filter_active)
            if self.library_widget.tag_filter_ids:
                config['Library']['tag_filter_ids'] = ",".join(map(str, self.library_widget.tag_filter_ids))
            else:
                config['Library']['tag_filter_ids'] = ""
        config['Library']['show_filter_labels'] = str(self.show_filter_labels)
        
        # Visual Style Persistence
        if 'Audiobook_Style' not in config: config['Audiobook_Style'] = {}
        config['Audiobook_Style']['icon_size'] = str(self.audiobook_icon_size)
        config['Audiobook_Style']['row_height'] = str(self.audiobook_row_height)
        
        if 'Folder_Style' not in config: config['Folder_Style'] = {}
        config['Folder_Style']['icon_size'] = str(self.folder_icon_size)
        config['Folder_Style']['row_height'] = str(self.folder_row_height)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def save_last_session(self):
        """Encapsulate the current playback state (active book, file, and position) into the configuration for future restoration"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'LastSession' not in config:
            config['LastSession'] = {}
        
        config['LastSession']['last_audiobook_id'] = str(self.playback_controller.current_audiobook_id or 0)
        config['LastSession']['last_file_index'] = str(self.playback_controller.current_file_index)
        config['LastSession']['last_position'] = str(self.player.get_position())
        
        if 'Display' not in config:
            config['Display'] = {}
        
        config['Display']['window_width'] = str(self.width())
        config['Display']['window_height'] = str(self.height())
        config['Display']['window_x'] = str(self.x())
        config['Display']['window_y'] = str(self.y())
        config['Display']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        
        # Persist the relative sizes of layout panes
        if hasattr(self, 'splitter'):
            sizes = self.splitter.sizes()
            config['Display']['splitter_sizes'] = ",".join(map(str, sizes))
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def restore_last_session(self):
        """Re-establish the application's previous state by reloading playback meta-data and layout preferences"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        audiobook_id = config.getint('LastSession', 'last_audiobook_id', fallback=0)
        file_index = config.getint('LastSession', 'last_file_index', fallback=0)
        position = config.getfloat('LastSession', 'last_position', fallback=0.0)
        
        # Restore layout splitter proportions
        splitter_sizes_str = config.get('Display', 'splitter_sizes', fallback='')
        if splitter_sizes_str and hasattr(self, 'splitter'):
            try:
                sizes = [int(s) for s in splitter_sizes_str.split(',')]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
            except (ValueError, TypeError):
                # Silently ignore malformed layout data
                pass
        
        if audiobook_id <= 0:
            return
        
        # Lookup audiobook relative path by unique identifier
        import sqlite3
        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        cursor.execute('SELECT path FROM audiobooks WHERE id = ?', (audiobook_id,))
        row = cursor.fetchone()
        connection.close()
        
        if row:
            audiobook_path = row[0]
            if self.playback_controller.load_audiobook(audiobook_path):
                # Inform the delegate of the active playback path for visual feedback
                if self.delegate:
                    self.delegate.playing_path = audiobook_path
                
                # Re-establish saved playback progress
                self.playback_controller.current_file_index = file_index
                self.playback_controller.play_file_at_index(file_index, False)
                if position > 0:
                    self.player.set_position(position)
                
                # Synchronize UI states
                self.update_ui_for_audiobook()
                
                # Force library refresh to reflect session state
                self.library_widget.tree.viewport().update()
                self.library_widget.load_audiobooks()
                self.statusBar().showMessage(tr("status.restored_session"))
    
    def on_id3_state_toggled(self, state: bool):
        """Persist the preference for ID3 tag visibility for the currently active audiobook"""
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_id3_state(
                self.playback_controller.current_audiobook_id,
                state
            )

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

    def on_deesser_preset_changed(self, value):
        """Handle DeEsser preset change"""
        self.deesser_preset = value
        self.player.set_deesser_preset(value)
        self.save_settings()

    def on_compressor_preset_changed(self, value):
        """Handle Compressor preset change"""
        self.compressor_preset = value
        self.player.set_compressor_preset(value)
        self.save_settings()

    def on_pitch_toggled(self, state: bool):
        """Update and persist pitch enabled state"""
        self.pitch_enabled = state
        self.player.set_pitch_enabled(state)
        self.save_settings()

    def on_pitch_changed(self, value: float):
        """Update and persist pitch value"""
        self.pitch_value = value
        self.player.set_pitch(value)
        self.save_settings()

    def on_show_folders_toggled(self, checked):
        """Update and persist the folder visibility preference"""
        self.show_folders = checked
        self.save_settings()

    def on_audiobook_selected(self, audiobook_path: str):
        """Handle the user's selection of an audiobook from the library, initiating playback and updating status"""
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
            self.toggle_play()
            
            # Refresh library categories to reflect "Started" status immediately
            self.library_widget.load_audiobooks(use_cache=False)

    
    def update_ui_for_audiobook(self):
        """Synchronize various UI elements to reflect the metadata and state of the currently loaded audiobook"""
        # Revise window title to include the book's title
        title = self.playback_controller.get_audiobook_title()
        self.setWindowTitle(trf("window.title_with_book", title=title))
        
        # Populate the playlist widget with the book's file list
        self.player_widget.load_files(
            self.playback_controller.files_list,
            self.playback_controller.current_file_index
        )
        
        # Restore the persistent ID3 visibility preference
        self.player_widget.id3_btn.setChecked(self.playback_controller.use_id3_tags)
        
        # Apply visual focus to the book in the library tree
        self.library_widget.highlight_audiobook(
            self.playback_controller.current_audiobook_path
        )
        
        # Synchronize speed control slider
        self.player_widget.set_speed(self.player.speed_pos)
    
    def toggle_play(self):
        """Toggle between active playback and paused states, updating UI indicators and background controllers accordingly"""
        if self.player.is_playing():
            self.player.pause()
            self.last_pause_time = __import__('time').time()
            self.taskbar_progress.set_paused()
        else:
            if self.auto_rewind and self.last_pause_time:
                pause_duration = __import__('time').time() - self.last_pause_time
                if pause_duration > 1: # Only rewind if pause was longer than 1 seconds
                    # Rewind logic: base 1s + 1s per 30s of pause, up to 30s total
                    # So: 1min pause -> 5 + 2 = 7s, 10min pause -> 5 + 20 = 25s
                    rewind_amount = min(30, 5 + (pause_duration / 30.0))
                    self.player.rewind(-rewind_amount)
            
            self.player.play()
            self.last_pause_time = None
            self.taskbar_progress.set_normal()
        
        # Sync the session delegate for visual consistency in the library
        if self.delegate:
            self.delegate.is_paused = not self.player.is_playing()
            self.library_widget.tree.viewport().update()
            
        self.player_widget.set_playing(self.player.is_playing())
        
        # Synchronize taskbar thumbnail buttons
        if hasattr(self, 'thumbnail_buttons'):
            self.thumbnail_buttons.update_play_state(self.player.is_playing())
            
        self.playback_controller.save_current_progress()
        self.save_last_session()
    
    def on_next_clicked(self):
        """Transition playback to the subsequent file in the audiobook sequence"""
        if self.playback_controller.next_file():
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
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
        self.save_last_session()
        self.refresh_audiobook_in_tree()
    
    def on_position_changed(self, normalized: float):
        """Seek to a specific temporal position within the active chapter based on normalized slider input"""
        current_file_info = self.playback_controller.files_list[self.playback_controller.current_file_index]
        start_offset = current_file_info.get('start_offset', 0)
        chapter_duration = current_file_info.get('duration', self.player.get_duration())
        
        if chapter_duration > 0:
            target_pos = start_offset + (normalized * chapter_duration)
            self.player.set_position(target_pos)
            self.playback_controller.save_current_progress()
    
    def on_speed_changed(self, value: int):
        """Adjust the audio playback speed and persist the new preference to the database for the active book"""
        self.player.set_speed(value)
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_speed(
                self.playback_controller.current_audiobook_id,
                value / 10.0
            )

    def on_library_play_clicked(self, audiobook_path: str):
        """Initiate or resume playback from the library view via the 'Play' overlay button"""
        if self.playback_controller.current_audiobook_path == audiobook_path:
            self.toggle_play()
        else:
            # If a different book is targeted, load its session and begin playback immediately
            self.on_audiobook_selected(audiobook_path)
            if not self.player.is_playing():
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
                self.taskbar_progress.taskbar,
                hwnd,
                self.icons_dir
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
    
    def update_ui(self):
        """Perform periodic synchronization of all UI components (sliders, labels, taskbar) with the current engine state"""
        if self.player.chan == 0:
            return
        
        pos = self.player.get_position()
        duration = self.player.get_duration()
        
        current_file_info = self.playback_controller.files_list[self.playback_controller.current_file_index]
        start_offset = current_file_info.get('start_offset', 0)
        chapter_duration = current_file_info.get('duration', duration)

        # Synchronize individual track progress indicators
        self.player_widget.update_file_progress(
            pos - start_offset, 
            chapter_duration, 
            self.player.speed_pos / 10.0
        )
        
        # Synchronize aggregate audiobook progress indicators
        total_pos = self.playback_controller.get_current_position()
        self.player_widget.update_total_progress(
            total_pos,
            self.playback_controller.total_duration,
            self.player.speed_pos / 10.0
        )
        
        # Perform low-priority library viewport updates (throttled to 1Hz)
        if not hasattr(self, '_library_update_counter'):
            self._library_update_counter = 0
            
        self._library_update_counter += 1
        if self._library_update_counter >= 10: # 100ms * 10 = 1000ms
            self._library_update_counter = 0
            if self.playback_controller.current_audiobook_path:
                progress_percent = self.playback_controller.get_progress_percent()
                self.library_widget.update_item_progress(
                    self.playback_controller.current_audiobook_path,
                    total_pos,
                    progress_percent
                )
        
        # Synchronize play/pause button aesthetics
        self.player_widget.set_playing(self.player.is_playing())
        
        # Synchronize Windows taskbar progress metrics
        if self.playback_controller.total_duration > 0:
            self.taskbar_progress.update_for_playback(
                is_playing=self.player.is_playing(),
                current=total_pos,
                total=self.playback_controller.total_duration
            )
        
        # Automate track transition upon reaching the end of the current file or chapter
        chapter_end = start_offset + chapter_duration
        # If the file finished or we reached the end of the chapter
        if (duration > 0 and pos >= duration - 0.5 and not self.player.is_playing()) or \
           (pos >= chapter_end - 0.2): # Small buffer for chapter transition
            self.on_next_clicked()
    
    def rescan_directory(self):
        """Initiate a comprehensive scan of the configured media directory with progress feedback via a dialog"""
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
                self.statusBar().showMessage(trf("status.library_count", count=total_count))
                self.remove_blur()
                
            dialog.finished.connect(on_finished)
            dialog.show()
            dialog.start_scan(self.default_path, self.ffprobe_path)

        start_scanning_process()
    
    def reload_styles(self):
        """Immediately re-apply global CSS styles and update presentation delegates to reflect theme changes"""
        try:
            from styles import StyleManager
            StyleManager.apply_style(QApplication.instance(), theme=self.current_theme)
            
            # Synchronize item rendering delegates
            if self.delegate:
                self.delegate.update_styles()
            
            # Force StyleManager to refresh its cache based on the new stylesheet
            StyleManager.refresh_cache()
            
            self.statusBar().showMessage(tr("status.styles_reloaded"))
        except Exception as e:
            self.statusBar().showMessage(trf("status.styles_error", error=str(e)))
    
    def show_settings(self):
        """Display the configuration dialog for managing library paths, system binaries, and data preferences"""
        # Apply blur effect
        self.apply_blur()
        
        dialog = SettingsDialog(self, self.default_path, self.ffprobe_path)
        
        def on_path_saved(new_path):
            """Commit new root path and initiate a library refresh if the configuration has changed"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                # Synchronize root path in the playback controller
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
                
                # Update library widget config
                if hasattr(self, 'library_widget'):
                    self.library_widget.config['default_path'] = new_path
                    self.library_widget.load_audiobooks()
                
                print(f"DEBUG: Path saved in main.py. New path: {new_path}")
                self.statusBar().showMessage(tr("status.path_saved"))
        
        def on_scan_requested(new_path):
            """Apply the new path and immediately trigger a directory scan"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
                
                # Update library widget config
                if hasattr(self, 'library_widget'):
                    self.library_widget.config['default_path'] = new_path
            
            print(f"DEBUG: Scan requested. Updating library config path to: {new_path}")
            self.rescan_directory()
        
        dialog.path_saved.connect(on_path_saved)
        dialog.scan_requested.connect(on_scan_requested)
        dialog.data_reset_requested.connect(self.perform_full_reset)
        
        dialog.exec()
        self.remove_blur()

    def perform_full_reset(self):
        """Execute a comprehensive wipe of all library metadata, database records, and extracted cover assets while the application remains active"""
        try:
            # 1. Stop active playback and unload file to release locks
            self.player.unload()
            
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
            self.update_ui_for_audiobook() # Resets labels and playlist
            
            # Reset player UI components specifically
            self.player_widget.position_slider.setValue(0)
            self.player_widget.total_progress_bar.setValue(0)
            self.player_widget.time_current.setText("0:00")
            self.player_widget.time_duration.setText("0:00")
            self.player_widget.total_time_label.setText("0:00:00")
            self.player_widget.total_duration_label.setText("0:00:00")
            self.player_widget.total_percent_label.setText(trf("formats.percent", value=0))
            self.player_widget.time_left_label.setText(tr("player.time_left_unknown"))

            if self.delegate:
                self.delegate.playing_path = None # Remove tree highlighting
            self.library_widget.load_audiobooks() # Populate empty tree

            
            self.statusBar().showMessage(tr("status.reset_success"))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to completely clear library data: {e}")

    def on_delete_requested(self, audiobook_id: int, rel_path: str):
        """Coordinate the comprehensive removal of an audiobook from the filesystem, database, and UI"""
        if not self.default_path:
             return
             
        abs_path = Path(self.default_path) / rel_path
        
        # 1. Terminate active playback if the target book is currently loaded
        if self.playback_controller.current_audiobook_id == audiobook_id:
            self.player.unload()
            # Clear internal playback state
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = ""
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0
            
            # Reset UI elements to their baseline state
            self.update_ui_for_audiobook()
            if self.delegate:
                self.delegate.playing_path = None
        
        # 2. Finalize data synchronization across database and view
        try:
            self.db_manager.delete_audiobook(audiobook_id)
            self.library_widget.remove_audiobook_from_ui(rel_path)
            self.statusBar().showMessage(tr("status.delete_success"))
        except Exception as e:
             QMessageBox.critical(self, tr("library.confirm_delete_title"), 
                                trf("library.delete_error", error=str(e)))

    def on_folder_delete_requested(self, rel_path: str):
        """Recursively remove a folder and its contents from the player, database, and UI"""
        # 1. Check if currently playing audiobook is inside this folder
        current_book_path = self.playback_controller.current_audiobook_path
        inside_folder = (
            current_book_path == rel_path or 
            current_book_path.startswith(rel_path + os.sep)
        )
        
        if inside_folder:
            self.player.unload()
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = ""
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0
            
            self.update_ui_for_audiobook()
            if self.delegate:
                self.delegate.playing_path = None
        
        # 2. Database and UI synchronization
        try:
            self.db_manager.delete_folder(rel_path)
            self.library_widget.remove_folder_from_ui(rel_path)
            self.statusBar().showMessage(tr("status.delete_success"))
        except Exception as e:
             QMessageBox.critical(self, tr("library.confirm_delete_folder_title"), 
                                trf("library.delete_error", error=str(e)))

    def apply_blur(self):
        """Increment blur request counter and apply graphics effect if necessary"""
        self._blur_count += 1
        if self._blur_count == 1:
            if not self._blur_effect:
                self._blur_effect = QGraphicsBlurEffect()
                self._blur_effect.setBlurRadius(5)
            self.setGraphicsEffect(self._blur_effect)

    def remove_blur(self):
        """Decrement blur request counter and remove graphics effect if it reaches zero"""
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
    
    def save_setting(self, section: str, key: str, value: str):
        """Update a specific configuration entry in 'settings.ini' without overwriting other existing sections"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if section not in config:
            config[section] = {}
        
        config[section][key] = value
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def closeEvent(self, event):
        """Perform cleanup operations upon application termination, including session saving and engine release"""
        self.save_settings()
        if self.auto_rewind:
            self.player.rewind(-30)
            
        self.playback_controller.save_current_progress()
        self.save_last_session()
        self.taskbar_progress.clear()
        
        # Unregister global hotkeys
        if hasattr(self, 'hotkey_manager'):
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
        """Monitor for WM_COMMAND messages originating from taskbar thumbnail clicks to trigger corresponding playback actions"""
        if eventType == b"windows_generic_MSG" and message:
            try:
                msg_ptr = int(message)
                if msg_ptr:
                    msg = wintypes.MSG.from_address(msg_ptr)
                    
                    # Handle multimedia keys and other global hotkeys via HotKeyManager
                    if self.window.hotkey_manager.handle_native_event(msg):
                        return True, 0

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
    try:
        print("Starting SPAudiobookPlayer...")
        app = QApplication(sys.argv)
        print("QApplication created.")
        
        app.setStyle('Fusion')
        # Load theme from settings
        config = configparser.ConfigParser()
        config_dir = get_base_path() / 'resources'
        config_file = config_dir / 'settings.ini'
        current_theme = 'dark'
        if config_file.exists():
            config.read(config_file, encoding='utf-8')
            current_theme = config.get('Display', 'theme', fallback='dark')
            
        # Apply Stylesheet
        StyleManager.apply_style(app, theme=current_theme)
        
        print("Initializing Style Manager...")
        StyleManager.init(app)
        
        print("Initializing Main Window...")
        window = AudiobookPlayerWindow()
        
        # Connect player instance to visualizer button
        if hasattr(window, 'player_widget') and hasattr(window, 'player'):
             if hasattr(window.player_widget, 'play_btn'):
                 window.player_widget.play_btn.set_player(window.player)
        
        # Register the native event filter for taskbar button interaction
        event_filter = TaskbarEventFilter(window)
        app.installNativeEventFilter(event_filter)
        
        print("Showing window.")
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print("\n" + "="*50)
        print("CRITICAL STARTUP ERROR:")
        print("="*50)
        traceback.print_exc()
        print("="*50)
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()
