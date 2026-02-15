from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QSizePolicy, QTextEdit, QProgressBar, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtGui import QFont, QTextCursor
import sys
import configparser
from pathlib import Path
import update_ffmpeg
from translations import tr, trf
from utils import get_icon, OutputCapture
from opus_dialog import OpusConversionDialog


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

class SettingsDialog(QDialog):
    """Dialogue for configuring application settings"""
    
    # Signals
    path_saved = pyqtSignal(str)       # Library path was updated
    scan_requested = pyqtSignal(str)   # Scan process triggered with specific path
    data_reset_requested = pyqtSignal()# Request to wipe all local database and covers
    opus_convert_requested = pyqtSignal() # Request to open Opus conversion dialog
    auto_update_toggled = pyqtSignal(bool) # Auto-update check toggled
    closed = pyqtSignal()              # Dialog closed
    
    def __init__(self, parent=None, current_path="", ffprobe_path=None, db_manager=None, auto_check=True):
        """Initialize settings dialog with current configuration values"""
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(720, 300)
        self.current_path = current_path
        self.ffprobe_path = ffprobe_path
        self.db_manager = db_manager
        self.auto_check = auto_check
        self.settings_path_edit = None
        self.auto_update_checkbox = None
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
        browse_btn.setIcon(get_icon("context_open_folder"))
        browse_btn.clicked.connect(self.browse_directory)
        path_edit_layout.addWidget(browse_btn)
        
        path_layout.addLayout(path_edit_layout)
        left_layout.addWidget(path_group)

        # Library Scan Group
        scan_group = QGroupBox(tr("settings.scan_group"))
        scan_layout = QVBoxLayout(scan_group)
        
        rescan_btn = QPushButton(tr("settings.scan_button"))
        rescan_btn.setObjectName("scanBtn")
        rescan_btn.setIcon(get_icon("scan"))
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
        tools_info.setObjectName("infoLabelSmall")
        tools_layout.addWidget(tools_info)

        # Opus Conversion
        opus_btn = QPushButton(tr("opus_converter.settings_btn"))
        opus_btn.clicked.connect(self.on_convert_opus)
        tools_layout.addWidget(opus_btn)
        
        opus_info = QLabel(tr("opus_converter.settings_info"))
        opus_info.setWordWrap(True)
        opus_info.setObjectName("infoLabelSmall")
        tools_layout.addWidget(opus_info)
        
        # Data Reset Configuration
        reset_btn = QPushButton(tr("settings.reset_data_btn"))
        reset_btn.setObjectName("resetBtn")
        reset_btn.setIcon(get_icon("delete"))
        reset_btn.clicked.connect(self.on_reset_data)
        tools_layout.addWidget(reset_btn)
        
        reset_info = QLabel(tr("settings.reset_data_info"))
        reset_info.setWordWrap(True)
        reset_info.setObjectName("infoLabelSmall")
        tools_layout.addWidget(reset_info)
        
        tools_layout.addSpacing(10)
        
        # Auto Update Check toggle
        self.auto_update_checkbox = QCheckBox(tr("settings.auto_update_label"))
        self.auto_update_checkbox.setChecked(self.auto_check)
        tools_layout.addWidget(self.auto_update_checkbox)
        
        auto_update_info = QLabel(tr("settings.auto_update_info"))
        auto_update_info.setWordWrap(True)
        auto_update_info.setObjectName("infoLabelSmall")
        tools_layout.addWidget(auto_update_info)
        
        tools_layout.addStretch()
        
        content_layout.addWidget(tools_group, 1)
        
        main_layout.addLayout(content_layout)

        self.update_ffprobe_status()

        # Save Action
        save_button = QPushButton(tr("settings.save"))
        save_button.setObjectName("saveBtn")
        save_button.setIcon(get_icon("save"))
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
            
        # Emit auto-update toggled signal
        self.auto_update_toggled.emit(self.auto_update_checkbox.isChecked())
        
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
            self.update_btn.setIcon(get_icon("check"))
        else:
            self.update_btn.setText(tr("ffmpeg_updater.settings_btn"))
            self.update_btn.setIcon(get_icon("download"))

    def on_update_ffmpeg(self):
        """Open the update dialog and refresh ffprobe status after closure"""
        self.apply_blur()
        dialog = UpdateProgressDialog(self)
        dialog.start_update()
        dialog.exec()
        self.remove_blur()
        self.update_ffprobe_status()

    def on_convert_opus(self):
        """Open Opus conversion dialog"""
        self.apply_blur()
        dialog = OpusConversionDialog(
            parent=self,
            library_path=self.current_path,
            ffmpeg_path=str(self.ffprobe_path).replace('ffprobe', 'ffmpeg') if self.ffprobe_path else 'ffmpeg',
            ffprobe_path=str(self.ffprobe_path) if self.ffprobe_path else 'ffprobe'
        )
        # Connect file conversion signal to database update
        if self.db_manager:
            dialog.file_converted.connect(
                lambda old, new, br: self.db_manager.update_file_extension(old, new, br)
            )
        dialog.conversion_complete.connect(lambda: self.opus_convert_requested.emit())
        dialog.exec()
        self.remove_blur()

    def _on_opus_file_converted(self, old_path: str, new_path: str):
        """Forward individual file conversion to whoever is listening"""
        pass

    def on_reset_data(self):
        """Handle library data reset with user confirmation"""
        self.apply_blur()
        reply = QMessageBox.question(
            self,
            tr("settings.reset_confirm_title"),
            tr("settings.reset_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        self.remove_blur()
        
        if reply == QMessageBox.StandardButton.Yes:
            self.data_reset_requested.emit()

    def apply_blur(self):
        """Proxy blur request to parent window if supported"""
        if self.parent() and hasattr(self.parent(), 'apply_blur'):
            self.parent().apply_blur()

    def remove_blur(self):
        """Proxy blur remove request to parent window if supported"""
        if self.parent() and hasattr(self.parent(), 'remove_blur'):
            self.parent().remove_blur()
