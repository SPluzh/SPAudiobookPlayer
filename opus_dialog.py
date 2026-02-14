"""
Opus Conversion Dialog
UI dialog for converting audiobook library files to Opus format.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QProgressBar, QTextEdit, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QTextCursor

from translations import tr, trf
from utils import get_icon
from opus_converter import OpusConversionThread, count_convertible_files


class OpusConversionDialog(QDialog):
    """Dialog for converting library audio files to Opus format"""
    
    # Signal emitted when a file has been converted (old_path, new_path, bitrate)
    file_converted = pyqtSignal(str, str, str)
    # Signal emitted when all conversions are complete
    conversion_complete = pyqtSignal()
    
    def __init__(self, parent=None, library_path="", ffmpeg_path="ffmpeg", ffprobe_path="ffprobe"):
        super().__init__(parent)
        self.library_path = library_path
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.thread = None
        self._is_converting = False
        
        self.setWindowTitle(tr("opus_converter.dialog_title"))
        self.setMinimumSize(600, 250)
        self._setup_ui()
        self._update_file_count()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Combined settings row
        settings_row_layout = QHBoxLayout()
        settings_row_layout.setContentsMargins(0, 0, 0, 0)
        
        # Bitrate selector
        bitrate_label = QLabel(tr("opus_converter.bitrate_label"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["16k", "24k", "32k", "48k", "64k"])
        self.bitrate_combo.setCurrentText("32k")
        self.bitrate_combo.setToolTip(tr("opus_converter.bitrate_tooltip"))
        settings_row_layout.addWidget(bitrate_label)
        settings_row_layout.addWidget(self.bitrate_combo)
        
        settings_row_layout.addSpacing(20)
        
        # Stereo handling selector
        stereo_label = QLabel(tr("opus_converter.stereo_label"))
        self.stereo_combo = QComboBox()
        self.stereo_combo.addItem(tr("opus_converter.stereo_downmix"), "downmix")
        self.stereo_combo.addItem(tr("opus_converter.stereo_keep"), "keep")
        self.stereo_combo.setToolTip(tr("opus_converter.stereo_tooltip"))
        settings_row_layout.addWidget(stereo_label)
        settings_row_layout.addWidget(self.stereo_combo)
        
        settings_row_layout.addStretch()
        
        # Add simpler container or just layout
        layout.addLayout(settings_row_layout)
        
        # File count info
        self.file_count_label = QLabel()
        self.file_count_label.setObjectName("infoLabelSmall")
        self.file_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.file_count_label)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel()
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        
        # Console log
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("scanConsole")
        self.console.setMinimumHeight(80)
        layout.addWidget(self.console)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton(tr("opus_converter.start_btn"))
        self.start_btn.setObjectName("saveBtn")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton(tr("opus_converter.cancel_btn"))
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setVisible(False)
        btn_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setMinimumHeight(36)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setVisible(False)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
    
    def _update_file_count(self):
        """Count and display the number of convertible files"""
        count = count_convertible_files(self.library_path)
        if count > 0:
            self.file_count_label.setText(
                trf("opus_converter.files_to_convert", count=count)
            )
            self.start_btn.setEnabled(True)
        else:
            self.file_count_label.setText(tr("opus_converter.no_files"))
            self.start_btn.setEnabled(False)
        self._file_count = count
    
    def _on_start(self):
        """Start conversion after confirmation"""
        if not self.library_path:
            return
        
        # Blur parent if available
        self._apply_blur()
        
        # Confirmation dialog
        reply = QMessageBox.warning(
            self,
            tr("opus_converter.confirm_title"),
            tr("opus_converter.confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        self._remove_blur()
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Start conversion
        self._is_converting = True
        self.start_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.bitrate_combo.setEnabled(False)
        self.stereo_combo.setEnabled(False)
        
        bitrate = self.bitrate_combo.currentText()
        stereo = self.stereo_combo.currentData()
        
        self.thread = OpusConversionThread(
            library_path=self.library_path,
            bitrate=bitrate,
            stereo_strategy=stereo,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
            parent=self
        )
        
        self.thread.progress.connect(self._on_progress)
        self.thread.file_converted.connect(self._on_file_converted)
        self.thread.log_message.connect(self._on_log)
        self.thread.conversion_finished.connect(self._on_finished)
        self.thread.start()
    
    def _on_cancel(self):
        """Cancel ongoing conversion"""
        if self.thread and self.thread.isRunning():
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText(tr("opus_converter.cancelling"))
            self.thread.cancel()
    
    def _on_progress(self, current: int, total: int, filename: str):
        """Update progress bar and label"""
        percent = int(current * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(
            trf("opus_converter.progress", current=current, total=total)
        )
    
    def _on_file_converted(self, old_path: str, new_path: str, bitrate: str):
        """Forward file conversion signal"""
        self.file_converted.emit(old_path, new_path, bitrate)
    
    def _on_log(self, text: str):
        """Append log message to console"""
        self.console.append(text)
        # Auto-scroll to bottom
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.console.setTextCursor(cursor)
    
    def _on_finished(self, success: bool, summary: str):
        """Handle conversion completion"""
        self._is_converting = False
        self.cancel_btn.setVisible(False)
        self.close_btn.setVisible(True)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        
        if success:
            self.progress_label.setText(
                trf("opus_converter.success", converted=self.thread.stats.converted if self.thread else 0)
            )
        else:
            self.progress_label.setText(tr("opus_converter.error") + f": {summary}")
        
        # Emit completion signal
        self.conversion_complete.emit()
    
    def _apply_blur(self):
        """Proxy blur request"""
        if self.parent() and hasattr(self.parent(), 'apply_blur'):
            self.parent().apply_blur()
    
    def _remove_blur(self):
        """Proxy blur remove"""
        if self.parent() and hasattr(self.parent(), 'remove_blur'):
            self.parent().remove_blur()
    
    def closeEvent(self, event):
        """Prevent closing while conversion is in progress"""
        if self._is_converting and self.thread and self.thread.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)
