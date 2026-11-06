from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QSizePolicy, QTextEdit, QProgressBar, QMessageBox,
    QCheckBox, QComboBox, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import pyqtSignal, QThread, Qt
from PyQt6.QtGui import QFont, QTextCursor
import sys
import os
import configparser
from typing import Union, List, Optional, Tuple
from pathlib import Path
import update_ffmpeg
from translations import tr, trf, get_all_translation_languages
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
    path_saved = pyqtSignal(str)                   # Library primary path was updated (backward-compat)
    paths_saved = pyqtSignal(list, list)           # (all_paths, excluded_paths)
    scan_requested = pyqtSignal(str, bool)         # Scan triggered for primary path (backward-compat)
    scan_paths_requested = pyqtSignal(list, list, bool) # Scan triggered: (all_paths, excluded_paths, force_rescan)
    data_reset_requested = pyqtSignal()            # Request to wipe all local database and covers
    opus_convert_requested = pyqtSignal()          # Request to open Opus conversion dialog
    auto_update_toggled = pyqtSignal(bool)         # Auto-update check toggled
    opus_workers_changed = pyqtSignal(int)         # Number of parallel encoding threads updated
    subtitle_target_lang_changed = pyqtSignal(str) # Target translation language updated
    subtitle_translation_provider_changed = pyqtSignal(str) # Translation provider updated
    closed = pyqtSignal()                          # Dialog closed
    
    def __init__(
        self,
        parent=None,
        current_path: Union[str, List[str]] = "",
        ffprobe_path=None,
        db_manager=None,
        auto_check: bool = True,
        opus_workers: int = 0,
        subtitle_target_lang: str = "en",
        subtitle_translation_provider: str = "google",
        excluded_paths: Optional[List[str]] = None,
    ):
        """Initialize settings dialog with current configuration values"""
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(760, 440)
        
        # Parse current_path
        if isinstance(current_path, list):
            self.library_paths = [str(p).strip() for p in current_path if str(p).strip()]
        elif isinstance(current_path, str) and current_path.strip():
            self.library_paths = [p.strip() for p in current_path.split(";") if p.strip()]
        else:
            self.library_paths = []
            
        self.excluded_paths = [str(p).strip() for p in excluded_paths] if excluded_paths else []
        self._deleted_paths: List[str] = []
        
        self.current_path = self.library_paths[0] if self.library_paths else ""
        self.ffprobe_path = ffprobe_path
        self.db_manager = db_manager
        self.auto_check = auto_check
        self.opus_workers = opus_workers
        self.subtitle_target_lang = subtitle_target_lang
        self.subtitle_translation_provider = subtitle_translation_provider
        
        self.pathslist = None
        self.auto_update_checkbox = None
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        # Library Path Configuration (Multi-Source List)
        path_group = QGroupBox(tr("settings.library_path_group"))
        path_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        path_layout = QVBoxLayout(path_group)
        
        self.pathslist = QTreeWidget()
        self.pathslist.setObjectName("pathsList")
        self.pathslist.setHeaderHidden(True)
        self.pathslist.setIndentation(0)
        self.pathslist.setMinimumHeight(110)
        self.pathslist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pathslist.itemChanged.connect(self.on_path_checked)
        path_layout.addWidget(self.pathslist, 1)

        buttons_layout = QHBoxLayout()
        self.add_path_btn = QPushButton(tr("settings.add_path"))
        self.add_path_btn.setObjectName("addPathBtn")
        self.add_path_btn.setIcon(get_icon("add"))
        self.add_path_btn.clicked.connect(self.add_path)
        buttons_layout.addWidget(self.add_path_btn)

        self.edit_path_btn = QPushButton(tr("settings.edit_path"))
        self.edit_path_btn.setObjectName("editPathBtn")
        self.edit_path_btn.setIcon(get_icon("edit"))
        self.edit_path_btn.clicked.connect(self.edit_path)
        buttons_layout.addWidget(self.edit_path_btn)

        self.remove_path_btn = QPushButton(tr("settings.remove_path"))
        self.remove_path_btn.setObjectName("removePathBtn")
        self.remove_path_btn.setIcon(get_icon("delete"))
        self.remove_path_btn.clicked.connect(self.remove_path)
        buttons_layout.addWidget(self.remove_path_btn)

        path_layout.addLayout(buttons_layout)
        left_layout.addWidget(path_group, 1)

        # Populate paths list
        self.pathslist.blockSignals(True)
        for p in self.library_paths:
            item = QTreeWidgetItem([p])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            norm_excluded = {os.path.normcase(os.path.normpath(ep)) for ep in self.excluded_paths}
            if os.path.normcase(os.path.normpath(p)) in norm_excluded:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                font = item.font(0)
                font.setStrikeOut(True)
                item.setFont(0, font)
            else:
                item.setCheckState(0, Qt.CheckState.Checked)
            self.pathslist.addTopLevelItem(item)
            self._validate_path(item)
        if self.pathslist.topLevelItemCount() > 0:
            self.pathslist.setCurrentItem(self.pathslist.topLevelItem(0))
        self.pathslist.blockSignals(False)

        # Library Scan Group
        scan_group = QGroupBox(tr("settings.scan_group"))
        scan_layout = QVBoxLayout(scan_group)
        
        # Checkbox for force rescan
        self.force_rescan_checkbox = QCheckBox(tr("settings.force_rescan"))
        self.force_rescan_checkbox.setObjectName("forceRescanCheckbox")
        scan_layout.addWidget(self.force_rescan_checkbox)

        rescan_btn = QPushButton(tr("settings.scan_button"))
        rescan_btn.setObjectName("scanBtn")
        rescan_btn.setIcon(get_icon("scan"))
        rescan_btn.clicked.connect(self.on_scan_requested)
        scan_layout.addWidget(rescan_btn)
        
        scan_info = QLabel(tr("settings.scan_info"))
        scan_info.setWordWrap(True)
        scan_layout.addWidget(scan_info)
        
        left_layout.addWidget(scan_group, 0)
        
        content_layout.addLayout(left_layout, 3)

        # Right layout for columns
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)

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
        self.auto_update_checkbox.setObjectName("autoUpdateCheckbox")
        self.auto_update_checkbox.setChecked(self.auto_check)
        tools_layout.addWidget(self.auto_update_checkbox)
        
        auto_update_info = QLabel(tr("settings.auto_update_info"))
        auto_update_info.setWordWrap(True)
        auto_update_info.setObjectName("infoLabelSmall")
        tools_layout.addWidget(auto_update_info)
        
        tools_layout.addStretch()
        right_layout.addWidget(tools_group)

        # Opus Conversion Group
        opus_group = QGroupBox(tr("settings.opus_group"))
        opus_layout = QVBoxLayout(opus_group)
        
        opus_btn = QPushButton(tr("opus_converter.settings_btn"))
        opus_btn.clicked.connect(self.on_convert_opus)
        opus_layout.addWidget(opus_btn)
        
        opus_info = QLabel(tr("opus_converter.settings_info"))
        opus_info.setWordWrap(True)
        opus_info.setObjectName("infoLabelSmall")
        opus_layout.addWidget(opus_info)
        
        # Opus Workers selection
        workers_layout = QHBoxLayout()
        self.workers_lbl = QLabel(tr("settings.opus_workers_label"))
        
        preset_values = [0, 1, 2, 4, 6, 8, 10, 12, 16, 20, 32]
        if self.opus_workers not in preset_values:
            preset_values.append(self.opus_workers)
            preset_values.sort()
            
        self.workers_combo = QComboBox()
        for val in preset_values:
            if val == 0:
                self.workers_combo.addItem(tr("settings.opus_workers_auto"), 0)
            else:
                self.workers_combo.addItem(str(val), val)
                
        self.workers_combo.setCurrentIndex(self.workers_combo.findData(self.opus_workers))
        self.workers_combo.setToolTip(tr("settings.opus_workers_tooltip"))
        
        workers_layout.addWidget(self.workers_lbl)
        workers_layout.addWidget(self.workers_combo)
        workers_layout.addStretch()
        opus_layout.addLayout(workers_layout)
        
        opus_layout.addStretch()
        right_layout.addWidget(opus_group)

        # Subtitle Translation Settings Group
        translation_group = QGroupBox(tr("settings.translation_group"))
        translation_layout = QVBoxLayout(translation_group)

        # Subtitle Target Language selection
        lang_layout = QHBoxLayout()
        self.lang_lbl = QLabel(tr("settings.translation_lang_label"))
        
        self.lang_combo = QComboBox()
        # Populate with available languages
        for code, name in get_all_translation_languages():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex(self.lang_combo.findData(self.subtitle_target_lang))
        
        lang_layout.addWidget(self.lang_lbl)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        translation_layout.addLayout(lang_layout)

        # Subtitle Translation Provider selection
        provider_layout = QHBoxLayout()
        self.provider_lbl = QLabel(tr("settings.translation_provider_label"))
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Google", "google")
        self.provider_combo.addItem("Free Dictionary", "freedict")
        self.provider_combo.setCurrentIndex(self.provider_combo.findData(self.subtitle_translation_provider))
        self.provider_combo.setToolTip(tr("settings.translation_provider_tooltip"))
        
        provider_layout.addWidget(self.provider_lbl)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        translation_layout.addLayout(provider_layout)

        translation_layout.addStretch()
        right_layout.addWidget(translation_group)
        
        right_layout.addStretch()
        content_layout.addLayout(right_layout, 2)
        
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

    def _validate_path(self, item: QTreeWidgetItem):
        """Check if path exists on disk and assign corresponding icon and tooltip"""
        path = item.text(0)
        if os.path.exists(path):
            item.setIcon(0, get_icon("check"))
            item.setToolTip(0, trf("settings.path_valid", path=path))
        else:
            item.setIcon(0, get_icon("fail"))
            item.setToolTip(0, trf("settings.path_invalid", path=path))

    def on_path_checked(self, item: QTreeWidgetItem, column: int):
        """Update font strikeout when path active state changes"""
        font = item.font(0)
        is_unchecked = (item.checkState(0) == Qt.CheckState.Unchecked)
        font.setStrikeOut(is_unchecked)
        item.setFont(0, font)

    def add_path(self):
        """Open directory chooser and add a new path to the list"""
        directory = QFileDialog.getExistingDirectory(self, tr("settings.choose_directory"))
        if directory:
            norm = os.path.normpath(directory)
            for i in range(self.pathslist.topLevelItemCount()):
                if os.path.normpath(self.pathslist.topLevelItem(i).text(0)) == norm:
                    return
            item = QTreeWidgetItem([norm])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            self.pathslist.addTopLevelItem(item)
            self._validate_path(item)
            self.pathslist.setCurrentItem(item)
            if hasattr(self, "_deleted_paths") and norm in self._deleted_paths:
                self._deleted_paths.remove(norm)

    def edit_path(self):
        """Edit currently selected path"""
        current = self.pathslist.currentItem()
        if not current:
            return
        old_path = current.text(0)
        directory = QFileDialog.getExistingDirectory(self, tr("settings.choose_directory"), old_path)
        if directory:
            norm = os.path.normpath(directory)
            if norm != os.path.normpath(old_path):
                for i in range(self.pathslist.topLevelItemCount()):
                    if os.path.normpath(self.pathslist.topLevelItem(i).text(0)) == norm:
                        return
                if not hasattr(self, "_deleted_paths"):
                    self._deleted_paths = []
                if os.path.normpath(old_path) not in self._deleted_paths:
                    self._deleted_paths.append(os.path.normpath(old_path))
                current.setText(0, norm)
                self._validate_path(current)

    def remove_path(self):
        """Prompt and remove selected path from list"""
        current = self.pathslist.currentItem()
        if not current:
            return
        reply = QMessageBox.question(
            self,
            tr("settings.confirm"),
            tr("settings.remove_path_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            path_to_remove = current.text(0)
            norm = os.path.normpath(path_to_remove)
            if not hasattr(self, "_deleted_paths"):
                self._deleted_paths = []
            if norm not in self._deleted_paths:
                self._deleted_paths.append(norm)
            index = self.pathslist.indexOfTopLevelItem(current)
            self.pathslist.takeTopLevelItem(index)

    def _collect_paths_from_ui(self) -> Tuple[List[str], List[str], str]:
        """Collect all paths, excluded paths, and primary path from the tree widget"""
        all_paths = []
        excluded_paths = []
        for i in range(self.pathslist.topLevelItemCount()):
            item = self.pathslist.topLevelItem(i)
            p = item.text(0)
            all_paths.append(p)
            if item.checkState(0) == Qt.CheckState.Unchecked:
                excluded_paths.append(p)
        active_paths = [p for p in all_paths if p not in excluded_paths]
        primary_path = active_paths[0] if active_paths else (all_paths[0] if all_paths else "")
        if hasattr(self, "_deleted_paths") and self._deleted_paths and self.db_manager:
            for p in self._deleted_paths:
                if hasattr(self.db_manager, "delete_audiobooks_by_root"):
                    self.db_manager.delete_audiobooks_by_root(p)
            self._deleted_paths.clear()
        return all_paths, excluded_paths, primary_path

    def get_path(self) -> str:
        """Return primary active library path"""
        _, _, primary_path = self._collect_paths_from_ui()
        return primary_path

    def browse_directory(self):
        """Backward-compatible directory browser triggering add_path"""
        self.add_path()

    def on_save(self):
        """Emit save signals with updated paths and configurations and accept dialog"""
        all_paths, excluded_paths, primary_path = self._collect_paths_from_ui()
        self.paths_saved.emit(all_paths, excluded_paths)
        if primary_path:
            self.path_saved.emit(primary_path)
            
        # Emit auto-update toggled signal
        self.auto_update_toggled.emit(self.auto_update_checkbox.isChecked())
        
        # Emit opus workers changed signal
        self.opus_workers_changed.emit(self.workers_combo.currentData())

        # Emit target language and translation provider signals
        self.subtitle_target_lang_changed.emit(self.lang_combo.currentData())
        self.subtitle_translation_provider_changed.emit(self.provider_combo.currentData())
        
        self.accept()

    def on_scan_requested(self):
        """Emit scan requested signal with the active paths"""
        all_paths, excluded_paths, primary_path = self._collect_paths_from_ui()
        active_paths = [p for p in all_paths if p not in excluded_paths]
        if not active_paths:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.specify_path"))
            return
        force = self.force_rescan_checkbox.isChecked()
        self.scan_paths_requested.emit(all_paths, excluded_paths, force)
        self.scan_requested.emit(primary_path, force)

    def update_ffprobe_status(self):
        """Check for ffprobe presence and update the button label accordingly"""
        ffprobe_exe = self.ffprobe_path
        
        if ffprobe_exe and ffprobe_exe.exists():
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
            ffprobe_path=str(self.ffprobe_path) if self.ffprobe_path else 'ffprobe',
            max_workers=self.workers_combo.currentData()
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
