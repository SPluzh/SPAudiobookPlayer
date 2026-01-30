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
    QTreeWidget, QTreeWidgetItem, QHBoxLayout, QLineEdit, QMenu, QStyle,
    QPushButton, QButtonGroup, QDialog, QDialogButtonBox, QGroupBox,
    QLabel, QFileDialog, QSlider, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QStyledItemDelegate, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QRect, QRectF, QPoint, QPointF, QThread
from PyQt6.QtGui import (
    QIcon, QAction, QPixmap, QBrush, QColor, QFont, QPen, QPainter, QPolygon,
    QTextCursor, QPainterPath, QFontMetrics
)

from bass_player import BassPlayer
from database import DatabaseManager
from styles import DARK_STYLE
from taskbar_progress import TaskbarProgress, TaskbarThumbnailButtons
import ctypes
from ctypes import wintypes
from translations import tr, trf, set_language, get_language, Language
from hotkeys import HotKeyManager


def format_duration(seconds):
    """Format duration in seconds to a human readable string for tree display"""
    if not seconds:
        return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return trf("formats.duration_hours", hours=hours, minutes=minutes)
    return trf("formats.duration_minutes", minutes=minutes) if minutes else trf("formats.duration_seconds", seconds=secs)

def format_time(seconds):
    """Format time in seconds to HH:MM:SS string"""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return trf("formats.time_hms", hours=hours, minutes=minutes, seconds=secs)

def format_time_short(seconds):
    """Format time in seconds to MM:SS string"""
    if seconds < 0:
        seconds = 0
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return trf("formats.time_ms", minutes=minutes, seconds=secs)

def load_icon(file_path: Path, target_size: int) -> QIcon:
    """Load, scale and return a QIcon from a file path"""
    if file_path.exists() and file_path.is_file():
        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                int(target_size * 1.5), 
                int(target_size * 1.5),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    return None

def resize_icon(icon: QIcon, size: int) -> QIcon:
    """Resize an existing QIcon to the specified size"""
    return QIcon(icon.pixmap(QSize(size, size)))

def get_base_path():
    """Return the base path for application resources (handles frozen exe and dev modes)"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            # One-file mode
            return Path(sys._MEIPASS)
        # One-dir mode
        return Path(sys.executable).parent
    # Dev mode
    return Path(__file__).parent

def get_icon(name: str, icons_dir: Path = None) -> QIcon:
    """
    Load an icon by name from the specified or default icons directory
    
    Args:
        name: Icon name (without extension)
        icons_dir: Path to the icons folder (defaults to ./resources/icons)
    
    Returns:
        QIcon or an empty icon if not found
    """
    if icons_dir is None:
        icons_dir = get_base_path() / "resources" / "icons"
    
    # Try different formats
    for ext in ['.png', '.svg', '.ico']:
        path = icons_dir / f"{name}{ext}"
        if path.exists():
            return QIcon(str(path))
    
    return QIcon()
    
class OutputCapture(io.StringIO):
    """Intercepts print output and sends it via signals"""
    def __init__(self, signal):
        """Initialize the capture with a Qt signal"""
        super().__init__()
        self.signal = signal
        self._real_stdout = sys.__stdout__
    
    def write(self, text):
        """Write text to the signal and original stdout"""
        if text:
            # Send to signal
            self.signal.emit(text)
            # Duplicate to real stdout for debugging
            if self._real_stdout:
                try:
                    self._real_stdout.write(text)
                except UnicodeEncodeError:
                    # Handle cases where console doesn't support the encoding
                    try:
                        safe_text = text.encode(self._real_stdout.encoding or 'utf-8', errors='replace').decode(self._real_stdout.encoding or 'utf-8')
                        self._real_stdout.write(safe_text)
                    except Exception:
                        pass
    
    def flush(self):
        """Flush the original stdout"""
        if self._real_stdout:
            self._real_stdout.flush()


class ScannerThread(QThread):
    """Background thread for scanning a directory for audiobooks"""
    progress = pyqtSignal(str)          # Log message signal
    finished_scan = pyqtSignal(int)     # Number of audiobooks found signal
    
    def __init__(self, root_path, ffprobe_path=None):
        """Initialize the scanner thread with target path and optional ffprobe path"""
        super().__init__()
        self.root_path = root_path
        self.ffprobe_path = ffprobe_path
    
    def run(self):
        """Execute the scan process"""
        try:
            # Redirect stdout to capture logs
            old_stdout = sys.stdout
            sys.stdout = OutputCapture(self.progress)
            
            # Check for ffprobe before scanning
            ffprobe_path = self.ffprobe_path
            
            # Fallback if ffprobe_path was not passed
            if not ffprobe_path:
                import configparser
                script_dir = Path(__file__).parent
                config_file = script_dir / 'resources' / 'settings.ini'
                config = configparser.ConfigParser()
                if config_file.exists():
                    config.read(config_file, encoding='utf-8')
                ffprobe_path_str = config.get('Paths', 'ffprobe_path', fallback='resources/bin/ffprobe.exe')
                ffprobe_path = Path(ffprobe_path_str)
                if not ffprobe_path.is_absolute():
                    ffprobe_path = script_dir / ffprobe_path
            
            # Download ffprobe if missing
            if not ffprobe_path.exists():
                print("\n" + "=" * 70)
                print(tr("ffmpeg_updater.missing_ffprobe_scanning"))
                print("=" * 70 + "\n")
                
                import update_ffmpeg
                update_ffmpeg.download_ffmpeg()
            
            from scanner import AudiobookScanner
            scanner = AudiobookScanner('settings.ini') # AudiobookScanner handles resources/ internally
            count = scanner.scan_directory(self.root_path)
            
            # Restore stdout
            sys.stdout = old_stdout
            self.finished_scan.emit(count)
        except Exception as e:
            print(f"Scanner error: {e}")
            self.finished_scan.emit(0)


class ScanProgressDialog(QDialog):
    """Dialog showing scan progress with console output"""
    def __init__(self, parent=None):
        """Initialize the scan progress dialog components"""
        super().__init__(parent)
        self.setWindowTitle(tr("scan_dialog.title"))
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Status Label
        self.status_label = QLabel(tr("scan_dialog.scanning"))
        self.status_label.setObjectName("scanStatusLabel")
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("scanProgressBar")
        self.progress_bar.setRange(0, 0) # Indeterminate state
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Console Output
        self.console = QTextEdit()
        self.console.setObjectName("scanConsole")
        self.console.setReadOnly(True)
        # Use monospaced font for console
        font = QFont("Consolas", 10)
        if font.exactMatch():
            self.console.setFont(font)
        layout.addWidget(self.console, 1)
        
        # Close Button
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
        self.thread = None
    
    def start_scan(self, root_path, ffprobe_path=None):
        """Start the background scanning thread"""
        self.thread = ScannerThread(root_path, ffprobe_path)
        self.thread.progress.connect(self.append_log)
        self.thread.finished_scan.connect(self.on_finished)
        self.thread.start()
    
    def append_log(self, text):
        """Append log text to the console, handling carriage returns for in-place updates"""
        from PyQt6.QtGui import QTextCursor
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Handle \r (carriage return) by overwriting the current line
        if '\r' in text:
            parts = text.split('\r')
            for i, part in enumerate(parts):
                if i > 0: # Part after \r
                    # Select current block/line and remove it
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                
                cursor.insertText(part)
        else:
            cursor.insertText(text)
            
        self.console.setTextCursor(cursor)
        # Auto-scroll to bottom
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )
    
    def on_finished(self, count):
        """Update UI when scanning is finished"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("100%")
        self.status_label.setText(trf("scan_dialog.complete", count=count))
        self.close_btn.setEnabled(True)

    def closeEvent(self, event):
        """Prevent closing the dialog while the scan thread is running"""
        if self.thread and self.thread.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)



class UpdateThread(QThread):
    """Background thread for downloading FFmpeg/ffprobe updates"""
    progress = pyqtSignal(str)
    finished_update = pyqtSignal(bool)

    def run(self):
        """Execute the update process"""
        capture = OutputCapture(self.progress)
        original_stdout = sys.stdout
        sys.stdout = capture
        
        success = False
        try:
            # Force update to ensure latest version
            success = update_ffmpeg.download_ffmpeg(force=True)
        except Exception as e:
            print(f"UpdateThread Error: {e}")
        finally:
            sys.stdout = original_stdout
            self.finished_update.emit(success)

class UpdateProgressDialog(QDialog):
    """Dialog showing FFmpeg update progress with console output"""
    def __init__(self, parent=None):
        """Initialize update dialog UI components"""
        super().__init__(parent)
        self.setWindowTitle(tr("ffmpeg_updater.dialog_title"))
        self.setMinimumSize(600, 400)
        self.setup_ui()
        self.thread = None
        
    def setup_ui(self):
        """Setup layout and widgets for the update dialog"""
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel(tr("ffmpeg_updater.check_dir"))
        self.status_label.setObjectName("scanStatusLabel")
        layout.addWidget(self.status_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("scanConsole")
        # Reuse monospaced font
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.console.setFont(font)
        layout.addWidget(self.console)
        
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
    def start_update(self):
        """Start the background update thread"""
        self.thread = UpdateThread()
        self.thread.progress.connect(self.update_console)
        self.thread.finished_update.connect(self.on_finished)
        self.thread.start()
        
    def update_console(self, text):
        """Handle console output updates including carriage returns"""
        from PyQt6.QtGui import QTextCursor
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if '\r' in text:
            parts = text.split('\r')
            
            for i, part in enumerate(parts):
                if i > 0: # Part after \r
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                
                cursor.insertText(part)
        else:
            cursor.insertText(text)
            
        self.console.setTextCursor(cursor)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )
        
    def on_finished(self, success):
        """Update status when update is complete"""
        self.status_label.setText(tr("ffmpeg_updater.success") if success else tr("ffmpeg_updater.error"))
        self.close_btn.setEnabled(True)

    def closeEvent(self, event):
        """Prevent closing while update is in progress"""
        if self.thread and self.thread.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)

class AboutDialog(QDialog):
    """Custom themed About Dialog for the application"""
    def __init__(self, parent=None):
        """Initialize the frameless about dialog"""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def showEvent(self, event):
        """Ensure window is centered and sized correctly on show"""
        self.adjustSize()
        self.center_window()
        super().showEvent(event)

    def get_app_version(self):
        """Load application version from version.txt"""
        try:
            version_file = get_base_path() / "resources" / "version.txt"
            if version_file.exists():
                return version_file.read_text("utf-8").strip()
        except Exception:
            pass
        return "1.0.0"

    def setup_ui(self):
        """Build the about dialog interface"""
        # Main layout with dark background
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame
        self.container = QFrame()
        self.container.setObjectName("aboutContainer")
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(30, 40, 30, 30)
        container_layout.setSpacing(15)
        
        # Title
        title = QLabel(tr('window.title'))
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)
        
        # Version
        version_text = self.get_app_version()
        version = QLabel(trf('about.version', version=version_text))
        version.setObjectName("aboutVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(version)
        
        # Separator
        line = QFrame()
        line.setObjectName("aboutLine")
        line.setFrameShape(QFrame.Shape.HLine)
        container_layout.addWidget(line)
        
        # Description
        desc = QLabel(tr('about.description'))
        desc.setObjectName("aboutDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        container_layout.addWidget(desc)
        
        container_layout.addSpacing(10)
        
        # Close Button
        close_btn = QPushButton(tr('about.close'))
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        container_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.container)

    def center_window(self):
        """Center the dialog relative to its parent or screen"""
        if self.parent():
            parent_geo = self.parent().frameGeometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(parent_geo.center())
            self.move(self_geo.topLeft())
        else:
            # Center on primary screen if no parent
            screen = QApplication.primaryScreen().geometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(screen.center())
            self.move(self_geo.topLeft())

class SettingsDialog(QDialog):
    """Dialogue for configuring application settings"""
    
    # Signals
    path_saved = pyqtSignal(str)       # Library path was updated
    scan_requested = pyqtSignal(str)   # Scan process triggered with specific path
    data_reset_requested = pyqtSignal()# Request to wipe all local database and covers
    closed = pyqtSignal()              # Dialog closed
    
    def __init__(self, parent=None, current_path="", ffprobe_path=None):
        """Initialize settings dialog with current configuration values"""
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(720, 300)
        self.current_path = current_path
        self.ffprobe_path = ffprobe_path
        self.settings_path_edit = None
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        # Library Path Configuration
        path_group = QGroupBox(tr("settings.library_path_group"))
        path_layout = QVBoxLayout(path_group)
        
        path_edit_layout = QHBoxLayout()
        self.settings_path_edit = QLineEdit(self.current_path)
        self.settings_path_edit.setPlaceholderText(tr("settings.library_path_placeholder"))
        path_edit_layout.addWidget(self.settings_path_edit, 1)
        
        browse_btn = QPushButton(tr("settings.browse"))
        browse_btn.setObjectName("browseBtn")
        browse_btn.clicked.connect(self.browse_directory)
        path_edit_layout.addWidget(browse_btn)
        
        path_layout.addLayout(path_edit_layout)
        left_layout.addWidget(path_group)

        # Library Scan Group
        scan_group = QGroupBox(tr("settings.scan_group"))
        scan_layout = QVBoxLayout(scan_group)
        
        rescan_btn = QPushButton(tr("settings.scan_button"))
        rescan_btn.setObjectName("scanBtn")
        rescan_btn.clicked.connect(self.on_scan_requested)
        scan_layout.addWidget(rescan_btn)
        
        scan_info = QLabel(tr("settings.scan_info"))
        scan_info.setWordWrap(True)
        scan_layout.addWidget(scan_info)
        
        left_layout.addWidget(scan_group)
        left_layout.addStretch()
        
        content_layout.addLayout(left_layout, 3)

        # Utilities and Tools
        tools_group = QGroupBox(tr("settings.tools_group"))
        tools_layout = QVBoxLayout(tools_group)
        
        self.update_btn = QPushButton(tr("ffmpeg_updater.settings_btn"))
        self.update_btn.clicked.connect(self.on_update_ffmpeg)
        tools_layout.addWidget(self.update_btn)
        
        tools_info = QLabel(tr("ffmpeg_updater.settings_info"))
        tools_info.setWordWrap(True)
        tools_info.setStyleSheet("color: #888; font-size: 11px;")
        tools_layout.addWidget(tools_info)
        
        # Data Reset Configuration
        reset_btn = QPushButton(tr("settings.reset_data_btn"))
        reset_btn.setObjectName("resetBtn")
        reset_btn.clicked.connect(self.on_reset_data)
        tools_layout.addWidget(reset_btn)
        
        reset_info = QLabel(tr("settings.reset_data_info"))
        reset_info.setWordWrap(True)
        reset_info.setStyleSheet("color: #888; font-size: 11px;")
        tools_layout.addWidget(reset_info)
        
        tools_layout.addStretch()
        
        content_layout.addWidget(tools_group, 1)
        
        main_layout.addLayout(content_layout)

        self.update_ffprobe_status()

        # Save Action
        save_button = QPushButton(tr("settings.save"))
        save_button.setObjectName("saveBtn")
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.on_save)
        save_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        main_layout.addWidget(save_button)
    
    def get_path(self):
        """Return the trimmed current library path from the input field"""
        return self.settings_path_edit.text().strip()
    
    def browse_directory(self):
        """Open a directory browser and update the path input if a directory is selected"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            tr("settings.choose_directory"), 
            self.settings_path_edit.text()
        )
        if directory:
            self.settings_path_edit.setText(directory)
    
    def on_save(self):
        """Emit save signal with the current path and accept the dialog"""
        new_path = self.get_path()
        if new_path:
            self.path_saved.emit(new_path)
        self.accept()
    
    def on_scan_requested(self):
        """Emit scan requested signal with the current path"""
        new_path = self.get_path()
        if new_path:
            self.scan_requested.emit(new_path)
 
    def update_ffprobe_status(self):
        """Check for ffprobe presence and update the button label accordingly"""
        ffprobe_exe = self.ffprobe_path
        
        if ffprobe_exe.exists():
            self.update_btn.setText(tr("ffmpeg_updater.settings_btn_installed"))
        else:
            self.update_btn.setText(tr("ffmpeg_updater.settings_btn"))

    def on_update_ffmpeg(self):
        """Open the update dialog and refresh ffprobe status after closure"""
        dialog = UpdateProgressDialog(self)
        dialog.start_update()
        dialog.exec()
        self.update_ffprobe_status()

    def on_reset_data(self):
        """Handle library data reset with user confirmation"""
        reply = QMessageBox.question(
            self,
            tr("settings.reset_confirm_title"),
            tr("settings.reset_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.data_reset_requested.emit()
            self.accept()

class StyleLabel(QLabel):
    """Helper widget to extract styles from QSS for custom painting"""
    def __init__(self, object_name: str, parent: QWidget = None):
        """Initialize the style label with an object name, ensuring it is hidden"""
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setVisible(False)

class MultiLineDelegate(QStyledItemDelegate):
    """Custom item delegate for library tree items with styling and localization support"""
    
    # QSS object names for various item components
    STYLE_NAMES = [
        'delegate_author',
        'delegate_title', 
        'delegate_narrator',
        'delegate_info',
        'delegate_folder',
        'delegate_progress',
        'delegate_duration',
        'delegate_file_count'
    ]
    
    def __init__(self, parent: QWidget = None):
        """Initialize the delegate and setup internal style properties"""
        super().__init__(parent)
        
        self.audiobook_row_height = 120
        self.folder_row_height = 30
        self.audiobook_icon_size = 100
        self.horizontal_padding = 10
        self.vertical_padding = 8
        self.line_spacing = 4
        
        # Playback state
        self.playing_path = None
        self.is_paused = True
        
        # UI state for interaction
        self.hovered_index = None
        self.mouse_pos = None
        
        self._style_labels: dict[str, StyleLabel] = {}
        self._create_style_widgets(parent)
        
        self.format_duration = self._default_format_duration

    def _create_style_widgets(self, parent: QWidget):
        """Initialize hidden widgets used to read formatting from the stylesheet"""
        for name in self.STYLE_NAMES:
            label = StyleLabel(name, parent)
            self._style_labels[name] = label
    
    def _get_style(self, style_name: str) -> tuple[QFont, QColor]:
        """Fetch font and color settings from a style label mapped to the given name"""
        label = self._style_labels.get(style_name)
        if label:
            label.ensurePolished()
            font = label.font()
            color = label.palette().color(label.foregroundRole())
            return font, color
        return QFont(), QColor(Qt.GlobalColor.white)
    
    def _default_format_duration(self, seconds: int) -> str:
        """Fallback 시간 formatting when no specific formatter is provided"""
        return format_time(seconds)
    
    def update_styles(self):
        """Force a refresh of style properties from the loaded QSS"""
        for label in self._style_labels.values():
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()
    
    def sizeHint(self, option, index) -> QSize:
        """Determine item size based on type (folder vs audiobook)"""
        size = super().sizeHint(option, index)
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        
        if item_type == 'folder':
            size.setHeight(self.folder_row_height)
        elif item_type == 'audiobook':
            size.setHeight(self.audiobook_row_height)
            
        return size
    
    def paint(self, painter, option, index):
        """Orchestrate custom painting logic for different tree item types"""
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        
        if item_type == 'folder':
            self._paint_folder(painter, option, index)
        elif item_type == 'audiobook':
            self._paint_audiobook(painter, option, index)
        else:
            super().paint(painter, option, index)
    
    def _paint_folder(self, painter, option, index):
        """Draw a folder item with icon and display name"""
        painter.save()
        
        font, color = self._get_style('delegate_folder')
        painter.setFont(font)
        painter.setPen(color)
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_size = 20
        icon_rect = QRect(
            option.rect.left() + self.horizontal_padding,
            option.rect.top() + (option.rect.height() - icon_size) // 2,
            icon_size, icon_size
        )
        if icon:
            icon.paint(painter, icon_rect)
        
        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_rect = QRect(
            icon_rect.right() + 8,
            option.rect.top(),
            option.rect.right() - icon_rect.right() - 18,
            option.rect.height()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text or "")
        
        painter.restore()
    
    def get_play_button_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the play button overlay in high precision"""
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(
            center.x() - btn_size / 2.0,
            center.y() - btn_size / 2.0,
            btn_size,
            btn_size
        )

    def _paint_audiobook(self, painter, option, index):
        """Render detailed audiobook item with cover, progress, and metadata"""
        painter.save()
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_rect = QRect(
            option.rect.left() + self.horizontal_padding,
            option.rect.top() + self.vertical_padding,
            self.audiobook_icon_size,
            self.audiobook_icon_size
        )
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            painter.restore()
            return
            
        author, title, narrator, file_count, duration, listened_duration, progress_percent = data
        
        if icon:
            painter.save()
            path = QPainterPath()
            path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipPath(path)
            
            # 1. Main Cover
            icon.paint(painter, icon_rect)
            
            # 2. In-cover Progress Indicator
            if progress_percent > 0:
                pb_h = 5
                pb_margin = 0
                pb_rect = QRect(icon_rect.left() + pb_margin, 
                                icon_rect.bottom() - pb_h - pb_margin,
                                icon_rect.width() - pb_margin * 2, 
                                pb_h)
                
                # Background
                painter.fillRect(pb_rect, QColor(0, 0, 0, 150))
                
                # Fill
                fill_w = int(pb_rect.width() * progress_percent / 100)
                if fill_w > 0:
                    fill_rect = QRect(pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height())
                    painter.fillRect(fill_rect, QColor("#018574")) # Theme primary
            
            # 3. Hover Background
            playing_file = index.data(Qt.ItemDataRole.UserRole)
            is_playing_this = (self.playing_path and playing_file == self.playing_path)
            
            if self.hovered_index == index:
                painter.fillRect(icon_rect, QColor(0, 0, 0, 100))
            
            painter.restore()
            
            # 4. Currently Playing Highlight Border
            if is_playing_this:
                # Dense green border for active book
                pen = QPen(QColor("#018574"), 8)
                painter.setPen(pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawRoundedRect(QRectF(icon_rect).adjusted(-4, -4, 4, 4), 7, 7)
 
            # 5. Play/Pause Button Overlay Logic
            if self.hovered_index == index or is_playing_this:
                play_btn_rect = self.get_play_button_rect(QRectF(icon_rect))
                
                # Precise mouse hover check
                is_over_btn = False
                if self.mouse_pos and play_btn_rect.contains(QPointF(self.mouse_pos)):
                    is_over_btn = True
                
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Button circle
                btn_color = QColor(1, 133, 116)
                if not is_over_btn:
                    btn_color.setAlpha(200)
                else:
                    btn_color = btn_color.lighter(110)
                
                painter.setBrush(btn_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(play_btn_rect)
                
                # Play/Pause Icon shapes
                painter.setBrush(Qt.GlobalColor.white)
                if is_playing_this and not self.is_paused:
                    # Draw Pause bars
                    w = play_btn_rect.width() // 5
                    h = play_btn_rect.height() // 2
                    gap = w // 2
                    
                    total_w = w * 2 + gap
                    start_x = play_btn_rect.left() + (play_btn_rect.width() - total_w) // 2
                    start_y = play_btn_rect.top() + (play_btn_rect.height() - h) // 2
                    
                    painter.drawRect(QRectF(start_x, start_y, w, h))
                    painter.drawRect(QRectF(start_x + w + gap, start_y, w, h))
                else:
                    # Draw Play triangle
                    side = play_btn_rect.width() // 2
                    center_f = QPointF(play_btn_rect.center())
                    
                    # Optical balancing adjustment
                    h_offset = play_btn_rect.width() / 20.0
                    
                    tri_path = QPainterPath()
                    tri_path.moveTo(center_f.x() - side / 3.0 + h_offset, center_f.y() - side / 2.0)
                    tri_path.lineTo(center_f.x() - side / 3.0 + h_offset, center_f.y() + side / 2.0)
                    tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                    tri_path.closeSubpath()
                    
                    painter.fillPath(tri_path, Qt.GlobalColor.white)
                
                painter.restore()
        
        text_x = icon_rect.right() + 15
        text_y = option.rect.top() + self.vertical_padding
        available_width = option.rect.right() - text_x - self.horizontal_padding
        
        # Author field
        if author:
            font, color = self._get_style('delegate_author')
            painter.setFont(font)
            painter.setPen(color)
            
            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, author)
            text_y += line_height + self.line_spacing
        
        # Title field
        font, color = self._get_style('delegate_title')
        painter.setFont(font)
        painter.setPen(color)
        
        line_height = painter.fontMetrics().height()
        rect = QRect(text_x, text_y, available_width, line_height)
        
        elided_title = painter.fontMetrics().elidedText(
            title or tr("delegate.no_title"), 
            Qt.TextElideMode.ElideRight, 
            available_width
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)
        text_y += line_height + self.line_spacing
        
        # NARRATOR Metadata
        if narrator:
            font, color = self._get_style('delegate_narrator')
            painter.setFont(font)
            painter.setPen(color)
            
            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            narrator_text = f"{tr('delegate.narrator_prefix')} {narrator}"
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, narrator_text)
            text_y += line_height + self.line_spacing
        
        # STATUS INFO LINE (Files, Duration, Progress)
        info_parts = []
        
        # File list count
        if file_count:
            font_fc, color_fc = self._get_style('delegate_file_count')
            files_text = f"{tr('delegate.files_prefix')} {file_count}"
            info_parts.append((files_text, font_fc, color_fc))
        
        # Overall duration
        if duration:
            font_dur, color_dur = self._get_style('delegate_duration')
            duration_text = f"{tr('delegate.duration_prefix')} {self.format_duration(duration)}"
            info_parts.append((duration_text, font_dur, color_dur))
        
        # Listening progress percentage
        font_prog, color_prog = self._get_style('delegate_progress')
        progress_text = trf("delegate.progress", percent=int(progress_percent))
        info_parts.append((progress_text, font_prog, color_prog))
        
        # Draw consolidated info line with custom formatting/spacing
        if info_parts:
            current_x = text_x
            for i, (text, font, color) in enumerate(info_parts):
                painter.setFont(font)
                painter.setPen(color)
                
                text_width = painter.fontMetrics().horizontalAdvance(text)
                line_height = painter.fontMetrics().height()
                
                rect = QRect(current_x, text_y, text_width + 10, line_height)
                painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
                
                current_x += text_width + 15
                
                # Inline separator dot
                if i < len(info_parts) - 1:
                    painter.setPen(QColor(100, 100, 100))
                    painter.drawText(QRect(current_x - 10, text_y, 10, line_height),
                                   Qt.AlignmentFlag.AlignCenter, tr("delegate.separator"))
        
        painter.restore()
class PlaybackController:
    """Manages playback logic, including file switching, progress tracking, and session persistence"""
    def __init__(self, player: BassPlayer, db_manager: DatabaseManager):
        """Initialize the controller with audio player and database manager"""
        self.player = player
        self.db = db_manager
        self.library_root: Optional[Path] = None
        
        # Playback state
        self.current_audiobook_id: Optional[int] = None
        self.current_audiobook_path: str = "" # Relative path as stored in database
        self.current_file_index: int = 0
        self.files_list: List[Dict] = []
        self.global_position: float = 0.0
        self.total_duration: float = 0.0
        self.use_id3_tags: bool = True
        
        # Saved state for session restoration
        self.saved_file_index: Optional[int] = None
        self.saved_position: Optional[float] = None
    
    def load_audiobook(self, audiobook_path: str) -> bool:
        """Load audiobook data from the database and prepare the player for playback"""
        self.player.pause()
        
        # Always save current progress before switching books
        self.save_current_progress()
        
        # Retrieve audiobook metadata
        audiobook_info = self.db.get_audiobook_info(audiobook_path)
        if not audiobook_info:
            return False
        
        audiobook_id, abook_name, author, title, saved_file_index, \
        saved_position, total_dur, saved_speed, use_id3_tags = audiobook_info
        
        # Update internal state with database values
        self.current_audiobook_id = audiobook_id
        self.current_audiobook_path = audiobook_path
        self.total_duration = total_dur or 0
        self.saved_file_index = saved_file_index
        self.saved_position = saved_position
        self.use_id3_tags = bool(use_id3_tags)
        
        # Load audiobook file list
        files = self.db.get_audiobook_files(audiobook_id)
        self.files_list = []
        
        for file_path, file_name, duration, track_num, tag_title in files:
            self.files_list.append({
                'path': file_path,
                'name': file_name,
                'tag_title': tag_title or '',
                'duration': duration or 0
            })
        
        # Restore saved playback speed
        self.player.set_speed(int(saved_speed * 10))
        
        # Initialize with the last played (or first) file
        if self.files_list:
            self.current_file_index = max(0, min(saved_file_index or 0, len(self.files_list) - 1))
            self.calculate_global_position()
            
            # Resolve path relative to library root
            rel_file_path = self.files_list[self.current_file_index]['path']
            if self.library_root:
                abs_file_path = str(self.library_root / rel_file_path)
            else:
                abs_file_path = rel_file_path
                
            if self.player.load(abs_file_path):
                if saved_position and saved_position > 0:
                    self.player.set_position(saved_position)
                return True
        
        return False
    
    def play_file_at_index(self, index: int, start_playing: bool = True) -> bool:
        """Load and optionally start playback of a file at the specified index"""
        if not (0 <= index < len(self.files_list)):
            return False
        
        was_playing = self.player.is_playing()
        self.current_file_index = index
        self.calculate_global_position()
        
        file_info = self.files_list[index]
        # Resolve absolute file path
        if self.library_root:
            abs_file_path = str(self.library_root / file_info['path'])
        else:
            abs_file_path = file_info['path']
            
        if self.player.load(abs_file_path):
            if start_playing or was_playing:
                self.player.play()
            return True
        return False
    
    def next_file(self, auto_next: bool = True) -> bool:
        """Switch to the next sequential file in the collection"""
        if self.current_file_index < len(self.files_list) - 1:
            self.play_file_at_index(
                self.current_file_index + 1, 
                self.player.is_playing() or auto_next
            )
            self.save_current_progress()
            return True
        else:
            # End of collection reached
            self.player.stop()
            
            if self.current_audiobook_id and self.total_duration > 0:
                self.db.mark_audiobook_completed(
                    self.current_audiobook_id, 
                    self.total_duration
                )
            return False
    
    def prev_file(self) -> bool:
        """Switch to the previous file or restart the current one based on position"""
        if self.player.get_position() > 3:
            # If more than 3 seconds in, just restart the current file
            self.player.set_position(0)
            return True
        elif self.current_file_index > 0:
            # Otherwise, go back to the previous file
            self.play_file_at_index(
                self.current_file_index - 1, 
                self.player.is_playing()
            )
            self.save_current_progress()
            return True
        return False
    
    def calculate_global_position(self):
        """Update the aggregate duration of all files preceding the current one"""
        self.global_position = sum(
            f['duration'] for f in self.files_list[:self.current_file_index]
        )
    
    def get_current_position(self) -> float:
        """Calculate the total elapsed time across the entire audiobook"""
        return self.global_position + self.player.get_position()
    
    def get_progress_percent(self) -> int:
        """Calculate the current playback progress as a percentage (0-100)"""
        if self.total_duration <= 0:
            return 0
            
        current = self.get_current_position()
        
        # Consider finished if within 1 second of total duration
        if current >= self.total_duration - 1:
            return 100
        
        return int((current / self.total_duration) * 100)
    
    def save_current_progress(self):
        """Commit current playback state and accumulated metrics to the database"""
        if not self.current_audiobook_id:
            return
        
        position = self.player.get_position()
        speed = self.player.speed_pos / 10.0
        listened_duration = self.get_current_position()
        progress_percent = self.get_progress_percent()
        
        self.db.save_progress(
            self.current_audiobook_id,
            self.current_file_index,
            position,
            speed,
            listened_duration,
            progress_percent
        )
    
    def get_audiobook_title(self) -> str:
        """Fetch the displayable name for the currently playing audiobook"""
        if not self.current_audiobook_path:
            return "Audiobook Player"
            
        info = self.db.get_audiobook_info(self.current_audiobook_path)
        if info:
            # info contains 9 fields (including use_id3_tags)
            _, name, author, title, _, _, _, _, _ = info
            return name
        return "Audiobook Player"
class PlayerWidget(QWidget):
    """UI widget containing playback controls, progress sliders, and the file list"""
    
    # Navigation and setting update signals
    play_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal(int)
    position_changed = pyqtSignal(float)
    volume_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(int)
    file_selected = pyqtSignal(int)
    id3_toggled_signal = pyqtSignal(bool)
    auto_rewind_toggled_signal = pyqtSignal(bool)
    
    def __init__(self):
        """Initialize widget state and prepare basic icon properties"""
        super().__init__()
        self.show_id3 = False
        self.slider_dragging = False
        
        # Icon resources
        self.play_icon = None
        self.pause_icon = None
        
        self.setup_ui()
        self.load_icons()
    
    def setup_ui(self):
        """Build the player user interface using stylized frames and layouts"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(15)
        
        # Primary player container
        player_frame = QFrame()
        player_layout = QVBoxLayout(player_frame)
        
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)
        
        # Volume and ID3 management section
        vol_box = QHBoxLayout()
        vol_box.setSpacing(5)
        
        # ID3 Meta-tag Toggle
        self.id3_btn = QPushButton("ID3")
        self.id3_btn.setCheckable(True)
        self.id3_btn.setFixedWidth(40)
        self.id3_btn.setObjectName("id3Btn")
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.id3_btn.toggled.connect(self.on_id3_toggled)
        vol_box.addWidget(self.id3_btn)
        
        # Auto-rewind Toggle
        self.auto_rewind_btn = QPushButton("AR")
        self.auto_rewind_btn.setCheckable(True)
        self.auto_rewind_btn.setFixedWidth(40)
        self.auto_rewind_btn.setObjectName("autoRewindBtn")
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))
        self.auto_rewind_btn.toggled.connect(self.on_auto_rewind_toggled)
        vol_box.addWidget(self.auto_rewind_btn)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMinimumWidth(80)
        self.volume_slider.setToolTip(tr("player.volume"))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        vol_box.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(trf("formats.percent", value=100))
        self.volume_label.setMinimumWidth(45)
        vol_box.addWidget(self.volume_label)
        
        settings_layout.addLayout(vol_box)
        
        settings_layout.addStretch()
        
        # Playback Speed Control
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(5)
        
        self.speed_label = QLabel(trf("formats.speed", value=1.0))
        self.speed_label.setFixedWidth(35)
        speed_layout.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setMinimumWidth(80)
        self.speed_slider.setToolTip(tr("player.speed"))
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        speed_layout.addWidget(self.speed_slider)
        
        speed_widget.setMinimumWidth(120)
        settings_layout.addWidget(speed_widget)
        
        player_layout.addLayout(settings_layout)
        
        # Main Navigation Controls
        controls = QHBoxLayout()
        controls.setSpacing(5)

        icon_size = QSize(24, 24)
        
        self.btn_prev = self.create_button("navBtn", tr("player.prev_track"), icon_size)
        self.btn_prev.clicked.connect(self.prev_clicked)
        controls.addWidget(self.btn_prev)
        
        self.btn_rw60 = self.create_button("rewindBtn", tr("player.rewind_60"), icon_size)
        self.btn_rw60.clicked.connect(lambda: self.rewind_clicked.emit(-60))
        controls.addWidget(self.btn_rw60)
        
        self.btn_rw10 = self.create_button("rewindBtn", tr("player.rewind_10"), icon_size)
        self.btn_rw10.clicked.connect(lambda: self.rewind_clicked.emit(-10))
        controls.addWidget(self.btn_rw10)
        
        # Core Play/Pause Action
        self.play_btn = self.create_button("playBtn", tr("player.play"), QSize(32, 32))
        self.play_btn.clicked.connect(self.play_clicked)
        self.play_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        controls.addWidget(self.play_btn)
        
        self.btn_ff10 = self.create_button("rewindBtn", tr("player.forward_10"), icon_size)
        self.btn_ff10.clicked.connect(lambda: self.rewind_clicked.emit(10))
        controls.addWidget(self.btn_ff10)
        
        self.btn_ff60 = self.create_button("rewindBtn", tr("player.forward_60"), icon_size)
        self.btn_ff60.clicked.connect(lambda: self.rewind_clicked.emit(60))
        controls.addWidget(self.btn_ff60)
        
        self.btn_next = self.create_button("navBtn", tr("player.next_track"), icon_size)
        self.btn_next.clicked.connect(self.next_clicked)
        controls.addWidget(self.btn_next)
        
        player_layout.addLayout(controls)
        
        # File/Track Progress Section
        file_box = QVBoxLayout()
        
        file_times = QHBoxLayout()
        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("timeLabel")
        self.time_duration = QLabel("0:00")
        self.time_duration.setObjectName("timeLabel")
        file_times.addWidget(self.time_current)
        file_times.addStretch()
        file_times.addWidget(self.time_duration)
        file_box.addLayout(file_times)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderPressed.connect(self.on_position_pressed)
        self.position_slider.sliderReleased.connect(self.on_position_released)
        self.position_slider.sliderMoved.connect(self.on_position_moved)
        file_box.addWidget(self.position_slider)
        
        player_layout.addLayout(file_box)
        

        total_box = QVBoxLayout()
        total_box.setSpacing(8)
        
        total_times = QHBoxLayout()
        self.total_percent_label = QLabel(trf("formats.percent", value=0))
        self.total_percent_label.setObjectName("timeLabel")
        self.total_time_label = QLabel("0:00:00")
        self.total_time_label.setObjectName("timeLabel")
        self.total_duration_label = QLabel("0:00:00")
        self.total_duration_label.setObjectName("timeLabel")
        self.time_left_label = QLabel(tr("player.time_left_unknown"))
        self.time_left_label.setObjectName("timeLabel")
        
        total_times.addWidget(self.total_time_label)
        total_times.addWidget(QLabel(tr("player.of"), objectName="timeLabel"))
        total_times.addWidget(self.total_duration_label)
        total_times.addStretch()
        total_times.addWidget(self.total_percent_label)
        total_times.addStretch()
        total_times.addWidget(self.time_left_label)
        total_box.addLayout(total_times)
        
        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setTextVisible(False)
        total_box.addWidget(self.total_progress_bar)
        
        player_layout.addLayout(total_box)
        layout.addWidget(player_frame)
        

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        layout.addWidget(self.file_list)
    
    def create_button(self, object_name: str, tooltip: str, icon_size: QSize) -> QPushButton:
        """Utility to create a standardized player control button with designated styles and tooltips"""
        btn = QPushButton()
        btn.setObjectName(object_name)
        btn.setToolTip(tooltip)
        btn.setIconSize(icon_size)
        return btn
    
    def load_icons(self):
        """Fetch and apply themed icons to all navigation and control buttons from resources"""
        self.play_icon = get_icon("play")
        self.pause_icon = get_icon("pause")
        
        self.play_btn.setIcon(self.play_icon)
        self.btn_prev.setIcon(get_icon("prev"))
        self.btn_next.setIcon(get_icon("next"))
        self.btn_rw10.setIcon(get_icon("rewind_10"))
        self.btn_rw60.setIcon(get_icon("rewind_60"))
        self.btn_ff10.setIcon(get_icon("forward_10"))
        self.btn_ff60.setIcon(get_icon("forward_60"))
    
    def on_volume_changed(self, value: int):
        """Update volume display label and emit signal for external processing"""
        self.volume_label.setText(trf("formats.percent", value=value))
        self.volume_changed.emit(value)
    
    def on_speed_changed(self, value: int):
        """Update speed display label and emit signal for playback adjustment"""
        self.speed_label.setText(trf("formats.speed", value=value/10))
        self.speed_changed.emit(value)
    
    def on_position_pressed(self):
        """Suspend progress updates while the user is dragging the position slider"""
        self.slider_dragging = True
    
    def on_position_released(self):
        """Seek to the new position upon slider release and resume temporal updates"""
        self.slider_dragging = False
        self.position_changed.emit(self.position_slider.value() / 1000.0)
    
    def on_position_moved(self, value: int):
        """Hook for optional real-time handling of position slider movements"""
        # Could be used to update preview time labels during drag
        pass
    
    def on_file_double_clicked(self, item):
        """Emit file selected signal with the index of the double-clicked list item"""
        index = self.file_list.row(item)
        self.file_selected.emit(index)
    
    def set_playing(self, is_playing: bool):
        self.play_btn.setIcon(self.pause_icon if is_playing else self.play_icon)
        self.play_btn.setToolTip(tr("player.pause") if is_playing else tr("player.play"))
    
    def update_file_progress(self, position: float, duration: float):
        """Update the time labels and slider position for the currently playing track"""
        if not self.slider_dragging:
            if duration >= 3600:
                self.time_current.setText(format_time(position))
            else:
                self.time_current.setText(format_time_short(position))
                
            if duration > 0:
                self.position_slider.setValue(int((position / duration) * 1000))
        
        if duration >= 3600:
            self.time_duration.setText(format_time(duration))
        else:
            self.time_duration.setText(format_time_short(duration))
    
    def update_total_progress(self, current: float, total: float, speed: float = 1.0):
        self.total_time_label.setText(format_time(current))
        self.total_duration_label.setText(format_time(total))
        
        if total > 0:
            percent = int((current / total) * 100)
            self.total_progress_bar.setValue(percent)
            self.total_percent_label.setText(trf("formats.percent", value=percent))
            
            time_left = (total - current) / speed
            self.time_left_label.setText(trf("player.time_left", time=format_time(time_left)))
        else:
            self.time_left_label.setText(tr("player.time_left_unknown"))
    
    def on_id3_toggled(self, checked):
        """Handle the visibility change of ID3 tags in the track list and refresh the display"""
        self.show_id3 = checked
        
        # Reload the file list to apply the new naming scheme
        if hasattr(self, 'last_files_list') and self.last_files_list:
            current_row = self.file_list.currentRow()
            self.load_files(self.last_files_list, current_row)
            
        # Notify the application about the preference change
        self.id3_toggled_signal.emit(checked)
    
    def on_auto_rewind_toggled(self, checked):
        """Handle the toggle of auto-rewind feature"""
        self.auto_rewind_toggled_signal.emit(checked)
    
    def load_files(self, files_list: list, current_index: int = 0):
        """Populate the track list widget with file information and highlight the active track"""
        self.last_files_list = files_list
        self.file_list.clear()
        
        for i, file_info in enumerate(files_list):
            duration = file_info.get('duration', 0)
            if duration >= 3600:
                dur_str = format_time(duration)
            else:
                dur_str = format_time_short(duration)
            display_name = file_info['name']
            
            if self.show_id3 and file_info.get('tag_title'):
                display_name = file_info['tag_title']
            
            list_item = QListWidgetItem(
                trf("formats.file_number", 
                    number=i+1, 
                    name=display_name, 
                    duration=dur_str)
            )
            list_item.setData(Qt.ItemDataRole.UserRole, file_info['path'])
            self.file_list.addItem(list_item)
        
        if 0 <= current_index < len(files_list):
            self.file_list.setCurrentRow(current_index)
            self.highlight_current_file(current_index)
    
    def highlight_current_file(self, index: int):
        """Выделение текущего файла"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            
            # Восстанавливаем оригинальный текст
            original_text = item.data(Qt.ItemDataRole.UserRole + 1)
            if not original_text and i == index:
                original_text = item.text()
                item.setData(Qt.ItemDataRole.UserRole + 1, original_text)
            
            if i == index:
                # Текущий файл
                item.setText(trf("formats.playing_indicator", text=original_text))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                # Остальные файлы
                if original_text:
                    item.setText(original_text)
                    item.setData(Qt.ItemDataRole.UserRole + 1, None)
                
                font = item.font()
                font.setBold(False)
                item.setFont(font)
    
    def set_speed(self, value: int):
        """Programmatically update the speed slider and its corresponding display label"""
        self.speed_slider.setValue(value)
        self.speed_label.setText(trf("formats.speed", value=value/10))
    
    def set_volume(self, value: int):
        """Programmatically update the volume slider and its corresponding display label"""
        self.volume_slider.setValue(value)
        self.volume_label.setText(trf("formats.percent", value=value))
    
    def update_texts(self):
        """Synchronize all UI labels, tooltips, and formatters after a language change event"""
        # Update speed and volume labels with current localized formatters
        speed_value = self.speed_slider.value() / 10
        self.speed_label.setText(trf("formats.speed", value=speed_value))
        self.volume_label.setText(trf("formats.percent", value=self.volume_slider.value()))
        
        # Refresh all control button tooltips
        self.btn_prev.setToolTip(tr("player.prev_track"))
        self.btn_next.setToolTip(tr("player.next_track"))
        self.btn_rw60.setToolTip(tr("player.rewind_60"))
        self.btn_rw10.setToolTip(tr("player.rewind_10"))
        self.btn_ff10.setToolTip(tr("player.forward_10"))
        self.btn_ff60.setToolTip(tr("player.forward_60"))
        self.play_btn.setToolTip(tr("player.play"))
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))


class LibraryTree(QTreeWidget):
    """Customized tree widget that handles hover detection and direct interaction with audiobook 'Play' buttons"""
    play_button_clicked = pyqtSignal(str) # Emits the relative path to the selected audiobook

    def __init__(self, parent=None):
        """Enable mouse tracking for fine-grained hover effects on custom-painted items"""
        super().__init__(parent)
        self.setMouseTracking(True)

    def leaveEvent(self, event):
        """Clear hover state in the delegate when the mouse leaves the widget viewport"""
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, 'hovered_index'):
            delegate.hovered_index = None
            delegate.mouse_pos = None
            self.viewport().update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Track mouse position to detect hover over specialized UI elements like playback buttons"""
        super().mouseMoveEvent(event)
        index = self.indexAt(event.pos())
        
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, 'get_play_button_rect'):
             delegate.hovered_index = index if index.isValid() else None
             delegate.mouse_pos = event.pos()
             self.viewport().update()
             
             if index.isValid():
                 item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                 if item_type == 'audiobook':
                     rect = self.visualRect(index)
                     icon_size = delegate.audiobook_icon_size
                     icon_rect = QRect(
                         rect.left() + delegate.horizontal_padding,
                         rect.top() + delegate.vertical_padding,
                         icon_size, icon_size
                     )
                     play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                     if play_rect.contains(QPointF(event.pos())):
                         self.setCursor(Qt.CursorShape.PointingHandCursor)
                         return
             
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        """Identify clicks on the custom 'Play' button to initiate playback without selecting the item"""
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                if item_type == 'audiobook':
                    delegate = self.itemDelegate()
                    if delegate and hasattr(delegate, 'get_play_button_rect'):
                        rect = self.visualRect(index)
                        icon_size = delegate.audiobook_icon_size
                        icon_rect = QRect(
                            rect.left() + delegate.horizontal_padding,
                            rect.top() + delegate.vertical_padding,
                            icon_size, icon_size
                        )
                        play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                        if play_rect.contains(QPointF(event.pos())):
                            path = index.data(Qt.ItemDataRole.UserRole)
                            self.play_button_clicked.emit(path)
                            return
        super().mousePressEvent(event)


class LibraryWidget(QWidget):
    """Container for the audiobook tree, search filters, and status-based navigation buttons"""
    
    audiobook_selected = pyqtSignal(str) # Emits the relative path of the selected audiobook
    show_folders_toggled = pyqtSignal(bool) # Emits the new state of the folders toggle
    
    # Internal configuration for status filtering
    FILTER_CONFIG = {
        'all': {'label': "library.filter_all", 'icon': "filter_all"},
        'not_started': {'label': "library.filter_not_started", 'icon': "filter_not_started"},
        'in_progress': {'label': "library.filter_in_progress", 'icon': "filter_in_progress"},
        'completed': {'label': "library.filter_completed", 'icon': "filter_completed"},
    }
    
    def __init__(self, db_manager: DatabaseManager, config: dict, delegate=None, show_folders: bool = False):
        """Initialize library managers, styling preferences, and default state"""
        super().__init__()
        self.db = db_manager
        self.config = config
        self.delegate = delegate
        self.default_audiobook_icon = None
        self.folder_icon = None
        self.current_playing_item = None
        self.highlight_color = QColor(1, 133, 116)
        self.highlight_text_color = QColor(255, 255, 255)
        self.current_filter = 'all'
        self.show_folders = show_folders
        self.setup_ui()
        self.load_icons()
    
    def setup_ui(self):
        """Assemble the search bar, filter buttons, and the main library tree widget"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(10)
        
        # Search Entry Area
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))
        self.search_edit.textChanged.connect(self.filter_audiobooks)
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_edit)
        
        layout.addLayout(search_layout)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # Show Folders Toggle
        self.btn_show_folders = QPushButton("")
        self.btn_show_folders.setObjectName("filterBtn")
        self.btn_show_folders.setCheckable(True)
        self.btn_show_folders.setChecked(self.show_folders)
        self.btn_show_folders.setIcon(get_icon("folder_cover"))
        self.btn_show_folders.setFixedWidth(40)
        self.btn_show_folders.setToolTip(tr("library.tooltip_show_folders"))
        self.btn_show_folders.clicked.connect(self.on_show_folders_toggled)
        filter_layout.addWidget(self.btn_show_folders)
        
        filter_layout.addSpacing(5)
        
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        
        self.filter_buttons = {}
        for filter_id, config in self.FILTER_CONFIG.items():
            btn = QPushButton(tr(config['label']))
            btn.setObjectName("filterBtn")
            btn.setCheckable(True)
            btn.setProperty('filter_type', filter_id)
            
            if 'icon' in config:
                btn.setIcon(get_icon(config['icon']))
                
            btn.setToolTip(tr(f"library.tooltip_filter_{filter_id}"))
            btn.clicked.connect(lambda checked, f=filter_id: self.apply_filter(f))
            self.filter_group.addButton(btn)
            self.filter_buttons[filter_id] = btn
            filter_layout.addWidget(btn)
            
        last_btn = self.filter_buttons[self.current_filter]
        if last_btn:
             last_btn.setChecked(True)

        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)
        
        # Дерево аудиокниг
        self.tree = LibraryTree()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(
            self.config.get('audiobook_icon_size', 100),
            self.config.get('audiobook_icon_size', 100)
        ))
        self.tree.setIndentation(20)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.itemCollapsed.connect(self.on_item_collapsed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        if self.delegate:
            self.tree.setItemDelegate(self.delegate)
        
        layout.addWidget(self.tree)

    def resizeEvent(self, event):
        """Update button labels when the widget is resized to avoid layout overflow"""
        super().resizeEvent(event)
        self.update_filter_labels()

    def update_filter_labels(self):
        """Toggle text visibility on filter buttons based on current widget width"""
        if not hasattr(self, 'filter_buttons'):
            return
            
        # Threshold for hiding text (only icons shown below this width)
        show_text = self.width() >= 450
        
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                btn = self.filter_buttons[filter_id]
                if show_text:
                    label = tr(config['label'])
                    btn.setText(label)
                    
                    # Calculate required width using BOLD metrics to prevent truncation when active
                    font = btn.font()
                    font.setBold(True)
                    metrics = QFontMetrics(font)
                    
                    text_width = metrics.horizontalAdvance(label)
                    icon_width = btn.iconSize().width() if not btn.icon().isNull() else 0
                    
                    # Buffer: icon + text + horizontal padding (10+10) + icon spacing + requested 15px
                    required_width = text_width + icon_width + 20 + 5 + 15
                    btn.setMinimumWidth(required_width)
                else:
                    btn.setText("")
                    btn.setMinimumWidth(0) # Reset min width allow shrinking to icon size (or rely on style)
    
    def load_icons(self):
        """Load and scale standard icons for folders and audiobook covers from resources"""
        script_dir = Path(__file__).parent
        
        # Determine the default cover icon
        default_cover = self.config.get('default_cover_file', 'resources/icons/default_cover.png')
        self.default_audiobook_icon = load_icon(
            get_base_path() / default_cover,
            self.config.get('audiobook_icon_size', 100)
        )
        
        if not self.default_audiobook_icon:
            self.default_audiobook_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )
        
        # Determine the folder representation icon
        folder_cover = self.config.get('folder_cover_file', 'resources/icons/folder_cover.png')
        self.folder_icon = load_icon(
            get_base_path() / folder_cover,
            self.config.get('folder_icon_size', 35)
        )
        
        if not self.folder_icon:
            self.folder_icon = resize_icon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                self.config.get('folder_icon_size', 35)
            )
    
    def apply_filter(self, filter_type: str):
        """Switch the current library view filter and refresh the audiobook listing"""
        self.current_filter = filter_type
        self.search_edit.clear()  # Reset search results when changing filter categories
        self.current_playing_item = None
        self.load_audiobooks()
    
    def on_show_folders_toggled(self, checked):
        """Toggle folder visibility and refresh the library"""
        self.show_folders = checked
        self.show_folders_toggled.emit(checked)
        self.load_audiobooks()

    def load_audiobooks(self):
        """Retrieve and display audiobooks from the database according to the active filter"""
        self.current_playing_item = None
        self.tree.clear()
        data_by_parent = self.db.load_audiobooks_from_db(self.current_filter)
        self.add_items_from_db(self.tree, '', data_by_parent)
    
    def add_items_from_db(self, parent_item, parent_path: str, data_by_parent: dict):
        """Recursively populate the tree widget with folders and audiobooks from the database map"""
        if parent_path not in data_by_parent:
            return
        
        for data in data_by_parent[parent_path]:
            if data['is_folder']:
                if not self.show_folders:
                    # If folders are hidden by default, recursively add children to the SAME parent
                    self.add_items_from_db(parent_item, data['path'], data_by_parent)
                    continue
                
                item = QTreeWidgetItem(parent_item)
                item.setData(0, Qt.ItemDataRole.UserRole, data['path'])
                item.setText(0, data['name'])
                item.setData(0, Qt.ItemDataRole.UserRole + 1, 'folder')
                item.setIcon(0, self.folder_icon)
                # Restore the expansion state of the folder from previous sessions
                if data.get('is_expanded'):
                    item.setExpanded(True)
            else:
                item = QTreeWidgetItem(parent_item)
                item.setData(0, Qt.ItemDataRole.UserRole, data['path'])
                # Audiobooks are custom-painted by the delegate
                # Set text to empty so the delegate has full control over the item's visual area
                item.setText(0, "")
                item.setData(0, Qt.ItemDataRole.UserRole + 1, 'audiobook')
                item.setData(0, Qt.ItemDataRole.UserRole + 2, (
                    data['author'],
                    data['title'],
                    data['narrator'],
                    data['file_count'],
                    data['duration'],
                    data['listened_duration'],
                    data['progress_percent']
                ))
                
                # Fetch and scale the audiobook cover
                cover_icon = None
                if data['cover_path']:
                    cover_p = Path(data['cover_path'])
                    # For relative paths, resolve them against the library's root directory
                    if not cover_p.is_absolute() and self.config.get('default_path'):
                        cover_p = Path(self.config.get('default_path')) / cover_p
                        
                    cover_icon = load_icon(
                        cover_p,
                        self.config.get('audiobook_icon_size', 100)
                    )
                item.setIcon(0, cover_icon or self.default_audiobook_icon)
            
            # Sub-items traversal
            self.add_items_from_db(item, data['path'], data_by_parent)
    
    def filter_audiobooks(self):
        """Handle real-time search queries by filtering tree items based on text matching"""
        search_text = self.search_edit.text().lower().strip()
        
        if not search_text:
            self.show_all_items(self.tree.invisibleRootItem())
            return
        
        self.filter_tree_items(self.tree.invisibleRootItem(), search_text)
    
    def show_all_items(self, parent_item):
        """Reset the visibility of all items within the tree to visible"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self.show_all_items(child)
    
    def filter_tree_items(self, parent_item, search_text: str) -> bool:
        """Recursively evaluate visibility for each item based on metadata matches and child presence"""
        has_visible = False
        
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
            
            if item_type == 'folder':
                has_children = self.filter_tree_items(child, search_text)
                folder_name = child.text(0).lower()
                matches = search_text in folder_name
                child.setHidden(not (matches or has_children))
                if not child.isHidden():
                    has_visible = True
                    
            elif item_type == 'audiobook':
                data = child.data(0, Qt.ItemDataRole.UserRole + 2)
                matches = False
                if data:
                    author, title, narrator, _, _, _, _ = data
                    if author and search_text in author.lower():
                        matches = True
                    if title and search_text in title.lower():
                        matches = True
                    if narrator and search_text in narrator.lower():
                        matches = True
                
                child.setHidden(not matches)
                if not child.isHidden():
                    has_visible = True
        
        return has_visible
    

    
    def on_item_expanded(self, item):
        """Persist the folder expansion state to the database when a branch is opened"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'folder':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, True)
    
    def on_item_collapsed(self, item):
        """Persist the folder collapse state to the database when a branch is closed"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'folder':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, False)

    def show_context_menu(self, pos):
        """Construct and display a context menu for audiobook items with actions for playback, status updates, and file explorating"""
        item = self.tree.itemAt(pos)
        if not item or item.data(0, Qt.ItemDataRole.UserRole + 1) != 'audiobook':
            return
        
        path = item.data(0, Qt.ItemDataRole.UserRole)
        # Retrieve audiobook details for context actions
        info = self.db.get_audiobook_info(path)
        if not info:
            return
        audiobook_id = info[0]
        duration = item.data(0, Qt.ItemDataRole.UserRole + 2)[4] # Index 4 corresponds to total duration

        menu = QMenu()
        play_action = QAction(tr("library.context_play"), self)
        play_action.setIcon(get_icon("context_play"))
        play_action.triggered.connect(lambda _: self.on_item_double_clicked(item, 0))
        menu.addAction(play_action)
        
        menu.addSeparator()

        # Mark as Completed
        mark_read_action = QAction(tr("library.menu_mark_read"), self)
        mark_read_action.setIcon(get_icon("context_mark_read"))
        mark_read_action.triggered.connect(lambda _: self.mark_as_read(audiobook_id, duration, path))
        menu.addAction(mark_read_action)

        # Mark as Not Started (Reset Progress)
        mark_unread_action = QAction(tr("library.menu_mark_unread"), self)
        mark_unread_action.setIcon(get_icon("context_mark_unread"))
        mark_unread_action.triggered.connect(lambda _: self.mark_as_unread(audiobook_id, path))
        menu.addAction(mark_unread_action)
        
        menu.addSeparator()
        
        open_folder_action = QAction(tr("library.menu_open_folder"), self)
        open_folder_action.setIcon(get_icon("context_open_folder"))
        open_folder_action.triggered.connect(lambda _: self.open_folder(path))
        menu.addAction(open_folder_action)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def mark_as_read(self, audiobook_id, duration, path):
        """Update audiobook status to completed and refresh the library and active player UI if necessary"""
        self.db.mark_audiobook_completed(audiobook_id, duration)
        self.load_audiobooks()
        # Synchronize UI if the modified book is currently loaded in the player
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            window.update_ui_for_audiobook()

    def mark_as_unread(self, audiobook_id, path):
        """Reset audiobook progress to 0% and synchronize the library and active player UI"""
        self.db.reset_audiobook_status(audiobook_id)
        self.load_audiobooks()
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            # Revert controller session state
            window.playback_controller.saved_file_index = 0
            window.playback_controller.saved_position = 0
            window.update_ui_for_audiobook()
    
    def open_folder(self, path: str):
        """Open the target directory in the system's native file explorer (supports Win32, macOS, Linux)"""
        if not path:
            return
            
        try:
            # Resolve the absolute path relative to the library's root
            default_path = self.config.get('default_path', '')
            
            if default_path:
                abs_path = Path(default_path) / path
            else:
                abs_path = Path(path)
                
            # If the path points to a file, target its parent directory
            if abs_path.exists() and abs_path.is_file():
                folder_path = abs_path.parent
            else:
                folder_path = abs_path
                
            if folder_path.exists():
                folder_path_str = str(folder_path.absolute())
                
                if sys.platform == 'win32':
                    import ctypes
                    # Use ShellExecuteW for standardized Explorer behavior on Windows
                    # SW_SHOWNORMAL = 1
                    ctypes.windll.shell32.ShellExecuteW(None, "open", folder_path_str, None, None, 1)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder_path_str], check=False)
                else:
                    subprocess.run(['xdg-open', folder_path_str], check=False)
            else:
                QMessageBox.warning(self, tr("window.title"), f"Path not found: {folder_path}")
        except Exception as e:
            QMessageBox.critical(self, tr("window.title"), f"Error opening folder: {e}")
    
    def on_item_double_clicked(self, item, column):
        """Notify the application when an audiobook item is double-clicked for playback"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'audiobook':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            self.audiobook_selected.emit(path)
    
    def highlight_audiobook(self, audiobook_path: str):
        """Apply active styling (colors, bold font) to the currently playing audiobook in the tree widget"""
        # Clear previous selection styling
        if self.current_playing_item:
            try:
                # Ensure the item still exists in the widget's model
                self.current_playing_item.text(0)
                self.reset_item_colors(self.current_playing_item)
            except RuntimeError:
                # Item was purged during a tree reload
                self.current_playing_item = None
        
        # Locate the new item to highlight
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
            self.current_playing_item = item
            
            # Apply themed highlight colors
            item.setBackground(0, QBrush(self.highlight_color))
            item.setForeground(0, QBrush(self.highlight_text_color))
            
            # Apply bold font weight
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            
            # Scroll the viewport to ensure the item is visible
            self.tree.scrollToItem(item)

    
    def find_item_by_path(self, parent_item, path: str):
        """Recursively search for an item in the tree whose metadata matches the specified relative path"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                return child
            result = self.find_item_by_path(child, path)
            if result:
                return result
        return None
    
    def reset_item_colors(self, item):
        """Restore an item's visual appearance to the default state (transparency and normal font)"""
        try:
            item.setBackground(0, QBrush(Qt.GlobalColor.transparent))
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)
        except RuntimeError:
            # Item has already been dissociated from the widget
            pass

    
    def refresh_audiobook_item(self, audiobook_path: str):
        """Update an item's metadata by re-querying the database (typically used after major status changes)"""
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
        
        # Load fresh record from DB
        data = self.db.get_audiobook_by_path(audiobook_path)
        if data:
            item.setData(0, Qt.ItemDataRole.UserRole + 2, (
                data['author'],
                data['title'],
                data['narrator'],
                data['file_count'],
                data['duration'],
                data['listened_duration'],
                data['progress_percent']
            ))
            # Trigger a repaint by updating text (standard behavior for delegates)
            item.setText(0, item.text(0))

    def update_item_progress(self, audiobook_path: str, listened_duration: float, progress_percent: int):
        """Perform a low-latency UI update for an item's progress without database interaction"""
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
            
        data = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if data and len(data) >= 7:
            # Create a shallow copy and update progress metrics
            new_data = list(data)
            new_data[5] = listened_duration
            new_data[6] = progress_percent
            
            item.setData(0, Qt.ItemDataRole.UserRole + 2, tuple(new_data))
            # Request viewport repaint only to maintain performance
            self.tree.viewport().update()
    
    def update_texts(self):
        """Refynchronize filter button labels and search placeholders following a language preference change"""
        # Update show folders button tooltip
        if hasattr(self, 'btn_show_folders'):
            self.btn_show_folders.setToolTip(tr("library.tooltip_show_folders"))
            
        # Refresh adaptive filter button labels
        self.update_filter_labels()
        
        # Update tooltips for localized filter names
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                self.filter_buttons[filter_id].setToolTip(tr(f"library.tooltip_filter_{filter_id}"))
        
        # Revise search field hint
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))


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
        self.last_pause_time = None
        
        # Load user configurations and localization settings
        self.load_settings()
        self.load_language_preference()
        
        # Configure window aesthetics
        self.setWindowTitle(tr("window.title"))
        self.setWindowIcon(get_icon("app_icon", self.icons_dir))
        
        # Dependency Injection and Component Instantiation
        self.db_manager = DatabaseManager(self.db_file)
        self.player = BassPlayer()
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
        self.setGeometry(self.window_x, self.window_y, self.window_width, self.window_height)
        self.setMinimumSize(450, 450)
        self.statusBar().showMessage(tr("status.load_library"))
        
        # Set initial focus to the library tree to avoid search field grabbing 'Space' key
        self.library_widget.tree.setFocus()
    
    def load_language_preference(self):
        """Retrieve and apply the user's preferred application language from the configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        lang_code = config.get('Display', 'language', fallback='ru')
        try:
            language = Language(lang_code)
            set_language(language)
        except ValueError:
            # Revert to default language if the preference is invalid
            set_language(Language.RUSSIAN)
    
    def save_language_preference(self):
        """Commit the current language setting to the persistent configuration file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'Display' not in config:
            config['Display'] = {}
        
        config['Display']['language'] = get_language().value
        
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
                'ffprobe_path': self.ffprobe_path
            },
            self.delegate,
            show_folders=self.show_folders
        )
        self.library_widget.setMinimumWidth(200)
        self.splitter.addWidget(self.library_widget)
        
        # Playback Controls Component
        self.player_widget = PlayerWidget()
        self.player_widget.setMinimumWidth(400)
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.on_id3_toggled(self.show_id3)
        self.player_widget.id3_toggled_signal.connect(self.on_id3_state_toggled)
        
        self.player_widget.auto_rewind_btn.setChecked(self.auto_rewind)
        self.player_widget.auto_rewind_toggled_signal.connect(self.on_auto_rewind_state_toggled)
        
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
        

        view_menu = menubar.addMenu(tr("menu.view"))
        
        # Language Selection Nested Menu
        language_menu = view_menu.addMenu(tr("menu.language"))
        
        # Russian Localization Toggle
        russian_action = QAction(tr("menu.russian"), self)
        russian_action.setCheckable(True)
        russian_action.setChecked(get_language() == Language.RUSSIAN)
        russian_action.triggered.connect(lambda _: self.change_language(Language.RUSSIAN))
        language_menu.addAction(russian_action)
        
        # English Localization Toggle
        english_action = QAction(tr("menu.english"), self)
        english_action.setCheckable(True)
        english_action.setChecked(get_language() == Language.ENGLISH)
        english_action.triggered.connect(lambda _: self.change_language(Language.ENGLISH))
        language_menu.addAction(english_action)
        
        self.language_actions = {
            Language.RUSSIAN: russian_action,
            Language.ENGLISH: english_action
        }
        
        view_menu.addSeparator()
        
        # CSS Refresh Action
        reload_styles_action = QAction(tr("menu.reload_styles"), self)
        reload_styles_action.setIcon(get_icon("menu_reload"))
        reload_styles_action.setShortcut("Ctrl+Q")
        reload_styles_action.triggered.connect(self.reload_styles)
        view_menu.addAction(reload_styles_action)
        

        help_menu = menubar.addMenu(tr("menu.help"))
        
        # About Dialog Trigger
        about_action = QAction(tr("menu.about"), self)
        about_action.setIcon(get_icon("menu_about"))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def change_language(self, language: Language):
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
    
    def connect_signals(self):
        """Map signals from sub-widgets (Library and Player) to their respective handler methods in the main window"""
        # Library Navigation Signals
        self.library_widget.audiobook_selected.connect(self.on_audiobook_selected)
        self.library_widget.tree.play_button_clicked.connect(self.on_library_play_clicked)
        self.library_widget.show_folders_toggled.connect(self.on_show_folders_toggled)

        # Playback Control Signals
        self.player_widget.play_clicked.connect(self.toggle_play)
        self.player_widget.next_clicked.connect(self.on_next_clicked)
        self.player_widget.prev_clicked.connect(self.on_prev_clicked)
        self.player_widget.rewind_clicked.connect(self.player.rewind)
        self.player_widget.position_changed.connect(self.on_position_changed)
        self.player_widget.volume_changed.connect(self.player.set_volume)
        self.player_widget.speed_changed.connect(self.on_speed_changed)
        self.player_widget.file_selected.connect(self.on_file_selected)
    
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
        self.show_folders = config.getboolean('Library', 'show_folders', fallback=False)
        
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
            'covers_dir': 'data/extracted_covers',
            'default_cover_file': 'resources/icons/default_cover.png',
            'folder_cover_file': 'resources/icons/folder_cover.png'
        }
        config['Display'] = {
            'window_width': '1200',
            'window_height': '800',
            'window_x': '100',
            'window_y': '100',
            'language': 'ru'
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
            'auto_rewind': 'True'
        }
        config['Library'] = {
            'show_folders': 'False'
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
            config['Player']['show_id3'] = str(self.player_widget.show_id3)
            config['Player']['auto_rewind'] = str(self.auto_rewind)
        
        if 'Library' not in config: config['Library'] = {}
        config['Library']['show_folders'] = str(self.show_folders)
        
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
            
            # Refresh library categories if necessary
            self.library_widget.load_audiobooks()

    
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
                if pause_duration > 10: # Only rewind if pause was longer than 10 seconds
                    # Rewind logic: base 10s + 1s per 30s of pause, up to 30s total
                    # So: 1min pause -> 10 + 2 = 12s, 10min pause -> 10 + 20 = 30s
                    rewind_amount = min(30, 10 + (pause_duration / 30.0))
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
        """Seek to a specific temporal position within the active file based on normalized slider input"""
        duration = self.player.get_duration()
        if duration > 0:
            self.player.set_position(normalized * duration)
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
        
        # Synchronize individual track progress indicators
        self.player_widget.update_file_progress(pos, duration)
        
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
        
        # Automate track transition upon reaching the end of the current file
        if duration > 0 and pos >= duration - 0.5 and not self.player.is_playing():
            self.on_next_clicked()
    
    def rescan_directory(self):
        """Initiate a comprehensive scan of the configured media directory with progress feedback via a dialog"""
        if not self.default_path:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.specify_path"))
            return

        def start_scanning_process():
            dialog = ScanProgressDialog(self)
            
            # Refresh the library view and status bar metrics upon scan completion
            def on_finished():
                self.library_widget.load_audiobooks()
                total_count = self.db_manager.get_audiobook_count()
                self.statusBar().showMessage(trf("status.library_count", count=total_count))
                
            dialog.finished.connect(on_finished)
            dialog.show()
            dialog.start_scan(self.default_path, self.ffprobe_path)

        start_scanning_process()
    
    def reload_styles(self):
        """Immediately re-apply global CSS styles and update presentation delegates to reflect theme changes"""
        try:
            from styles import StyleManager, DARK_QSS_PATH
            StyleManager.apply_style(QApplication.instance(), path=DARK_QSS_PATH)
            
            # Synchronize item rendering delegates
            if self.delegate:
                self.delegate.update_styles()
            
            self.statusBar().showMessage(tr("status.styles_reloaded"))
        except Exception as e:
            self.statusBar().showMessage(trf("status.styles_error", error=str(e)))
    
    def show_settings(self):
        """Display the configuration dialog for managing library paths, system binaries, and data preferences"""
        dialog = SettingsDialog(self, self.default_path, self.ffprobe_path)
        
        def on_path_saved(new_path):
            """Commit new root path and initiate a library refresh if the configuration has changed"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                # Synchronize root path in the playback controller
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
                self.library_widget.load_audiobooks()
                self.statusBar().showMessage(tr("status.path_saved"))
        
        def on_scan_requested(new_path):
            """Apply the new path and immediately trigger a directory scan"""
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
            self.rescan_directory()
        
        dialog.path_saved.connect(on_path_saved)
        dialog.scan_requested.connect(on_scan_requested)
        dialog.data_reset_requested.connect(self.perform_full_reset)
        dialog.exec()

    def perform_full_reset(self):
        """Execute a comprehensive wipe of all library metadata, database records, and extracted cover assets while the application remains active"""
        try:
            # 1. Stop active playback to release locks
            self.player.pause()
            
            # 2. Reset the internal state of the playback controller
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = None
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0
            
            # 3. Clear the tree widget (crucial for unlocking cover image assets)
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
            self.update_ui_for_audiobook() # Resets labels and progress sliders
            if self.delegate:
                self.delegate.playing_path = None # Remove tree highlighting
            self.library_widget.load_audiobooks() # Populate empty tree
            
            self.statusBar().showMessage(tr("status.reset_success"))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to completely clear library data: {e}")

    def show_about(self):
        """Display the application information dialog, including versioning and credit details"""
        dialog = AboutDialog(self)
        dialog.exec()
    
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
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(DARK_STYLE)
    
    window = AudiobookPlayerWindow()
    
    # Register the native event filter for taskbar button interaction
    event_filter = TaskbarEventFilter(window)
    app.installNativeEventFilter(event_filter)
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
