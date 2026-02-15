"""
Update dialog for SP Audiobook Player.
Shows available update info, download progress, and handles the update flow.
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QApplication, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from translations import tr, trf
from updater import (
    check_for_update, UpdateDownloader, apply_update,
    get_app_root, get_current_version, format_size,
    UpdateCheckResult
)


class UpdateCheckThread(QThread):
    """Background thread for checking updates"""
    result_ready = pyqtSignal(object)  # UpdateCheckResult
    
    def run(self):
        result = check_for_update()
        self.result_ready.emit(result)


class UpdateDownloadThread(QThread):
    """Background thread for downloading updates"""
    progress = pyqtSignal(float, str)  # percent, status_text
    finished = pyqtSignal(bool, str)   # success, zip_path or error
    
    def __init__(self, url: str, target_path: Path):
        super().__init__()
        self.url = url
        self.target_path = target_path
        self.downloader = None
    
    def run(self):
        def on_progress(percent, downloaded, total, speed, eta):
            speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
            eta_min = int(eta // 60)
            eta_sec = int(eta % 60)
            eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
            status = f"{format_size(downloaded)} / {format_size(total)} ({speed_str}, ETA: {eta_str})"
            self.progress.emit(percent, status)
        
        self.downloader = UpdateDownloader(
            self.url, self.target_path,
            progress_callback=on_progress
        )
        
        success = self.downloader.download()
        if success:
            self.finished.emit(True, str(self.target_path))
        else:
            self.finished.emit(False, tr("updater.download_error"))
    
    def cancel(self):
        if self.downloader:
            self.downloader.cancel()


class UpdateDialog(QDialog):
    """Dialog for showing update availability and handling download/install"""
    
    update_accepted = pyqtSignal()  # Signal to restart the app
    
    def __init__(self, update_info: UpdateCheckResult, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_thread = None
        
        self.setWindowTitle(tr("updater.title"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(trf("updater.new_version_available", version=self.update_info.remote_version))
        header.setObjectName("updateHeader")
        header_font = header.font()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Current version info
        current_ver = get_current_version()
        version_info = QLabel(trf("updater.version_info", 
                                   current=current_ver, 
                                   new=self.update_info.remote_version))
        version_info.setObjectName("updateVersionInfo")
        layout.addWidget(version_info)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("updateSeparator")
        layout.addWidget(line)
        
        # Release notes
        if self.update_info.release_notes:
            notes_label = QLabel(tr("updater.release_notes"))
            notes_font = notes_label.font()
            notes_font.setBold(True)
            notes_label.setFont(notes_font)
            layout.addWidget(notes_label)
            
            self.notes_text = QTextEdit()
            self.notes_text.setReadOnly(True)
            self.notes_text.setMaximumHeight(200)
            self.notes_text.setPlainText(self.update_info.release_notes)
            layout.addWidget(self.notes_text)
        
        # Download size
        if self.update_info.download_size > 0:
            size_label = QLabel(trf("updater.download_size", 
                                     size=format_size(self.update_info.download_size)))
            layout.addWidget(size_label)
        
        # Progress section (hidden initially)
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("updateProgressLabel")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)
        
        # Spacer
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.skip_btn = QPushButton(tr("updater.skip"))
        self.skip_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.skip_btn)
        
        self.update_btn = QPushButton(tr("updater.update_now"))
        self.update_btn.setDefault(True)
        self.update_btn.setObjectName("updateButton")
        self.update_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.update_btn)
        
        layout.addLayout(btn_layout)
    
    def start_download(self):
        """Start downloading the update"""
        self.update_btn.setEnabled(False)
        self.update_btn.setText(tr("updater.downloading"))
        self.skip_btn.setText(tr("updater.cancel"))
        self.skip_btn.clicked.disconnect()
        self.skip_btn.clicked.connect(self.cancel_download)
        
        self.progress_frame.show()
        self.progress_label.setText(tr("updater.starting_download"))
        
        # Download to app root temp location
        app_root = get_app_root()
        zip_path = app_root / "_update_download.zip"
        
        self.download_thread = UpdateDownloadThread(
            self.update_info.download_url, zip_path
        )
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
    
    def cancel_download(self):
        """Cancel the ongoing download"""
        if self.download_thread:
            self.download_thread.cancel()
        self.reject()
    
    def on_download_progress(self, percent: float, status: str):
        """Update progress bar and label"""
        self.progress_bar.setValue(int(percent))
        self.progress_label.setText(status)
    
    def on_download_finished(self, success: bool, result: str):
        """Handle download completion"""
        if not success:
            self.progress_label.setText(trf("updater.error", error=result))
            self.update_btn.setEnabled(True)
            self.update_btn.setText(tr("updater.retry"))
            self.skip_btn.setText(tr("updater.close"))
            self.skip_btn.clicked.disconnect()
            self.skip_btn.clicked.connect(self.reject)
            return
        
        # Download succeeded, now apply update
        self.progress_label.setText(tr("updater.extracting"))
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        
        zip_path = Path(result)
        
        def on_apply_progress(status=""):
            pass
        
        success = apply_update(zip_path, progress_callback=on_apply_progress)
        
        if success:
            self.progress_label.setText(tr("updater.restart_required"))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            
            self.skip_btn.hide()
            self.update_btn.setEnabled(True)
            self.update_btn.setText(tr("updater.restart_now"))
            self.update_btn.clicked.disconnect()
            self.update_btn.clicked.connect(self.restart_app)
        else:
            self.progress_label.setText(tr("updater.apply_error"))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.skip_btn.setText(tr("updater.close"))
            self.skip_btn.clicked.disconnect()
            self.skip_btn.clicked.connect(self.reject)
    
    def restart_app(self):
        """Close the app to let the update script take over"""
        self.update_accepted.emit()
        # The main window will handle closing the app
        self.accept()
