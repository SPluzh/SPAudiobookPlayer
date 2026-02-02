import sys
from pathlib import Path
from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, 
    QLabel, QProgressBar, QListWidget, QListWidgetItem, QSizePolicy,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from bass_player import BassPlayer
from database import DatabaseManager
from translations import tr, trf
from utils import get_icon, format_time, format_time_short

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
                
                # Update last_updated timestamp in database
                self.db.update_last_updated(self.current_audiobook_id)
                
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
    deesser_toggled_signal = pyqtSignal(bool)
    compressor_toggled_signal = pyqtSignal(bool)
    
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
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(0)
        
        # Primary player container
        player_frame = QFrame()
        player_layout = QVBoxLayout(player_frame)
        

        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)
        
        # Audio Effect Buttons Row (Above Volume)
        btns_row = QHBoxLayout()
        btns_row.setSpacing(5)
        
        # ID3 Meta-tag Toggle
        self.id3_btn = QPushButton("ID3")
        self.id3_btn.setCheckable(True)
        self.id3_btn.setFixedWidth(40)
        self.id3_btn.setObjectName("id3Btn")
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.id3_btn.toggled.connect(self.on_id3_toggled)
        btns_row.addWidget(self.id3_btn)
        
        # Auto-rewind Toggle
        self.auto_rewind_btn = QPushButton("AR")
        self.auto_rewind_btn.setCheckable(True)
        self.auto_rewind_btn.setFixedWidth(40)
        self.auto_rewind_btn.setObjectName("autoRewindBtn")
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))
        self.auto_rewind_btn.toggled.connect(self.on_auto_rewind_toggled)
        btns_row.addWidget(self.auto_rewind_btn)
        
        # DeEsser Toggle
        self.deesser_btn = QPushButton("DS")
        self.deesser_btn.setCheckable(True)
        self.deesser_btn.setFixedWidth(40)
        self.deesser_btn.setObjectName("deesserBtn")
        self.deesser_btn.setToolTip(tr("player.tooltip_deesser"))
        self.deesser_btn.toggled.connect(self.on_deesser_toggled)
        btns_row.addWidget(self.deesser_btn)
        
        self.compressor_btn = QPushButton("C")
        self.compressor_btn.setCheckable(True)
        self.compressor_btn.setFixedWidth(40)
        self.compressor_btn.setObjectName("compressorBtn")
        self.compressor_btn.setToolTip(tr("player.tooltip_compressor"))
        self.compressor_btn.toggled.connect(self.on_compressor_toggled)
        btns_row.addWidget(self.compressor_btn)
        btns_row.addStretch()
        
        settings_layout.addLayout(btns_row)
        
        # Sliders Row (Volume + Speed)
        sliders_row = QHBoxLayout()
        sliders_row.setSpacing(5)
        
        # Volume
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMinimumWidth(100)
        self.volume_slider.setToolTip(tr("player.volume"))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        sliders_row.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(trf("formats.percent", value=100))
        self.volume_label.setMinimumWidth(45)
        sliders_row.addWidget(self.volume_label)
        
        sliders_row.addStretch()
        
        # Speed
        self.speed_label = QLabel(trf("formats.speed", value=1.0))
        self.speed_label.setFixedWidth(35)
        sliders_row.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setMinimumWidth(100)
        self.speed_slider.setToolTip(tr("player.speed"))
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        sliders_row.addWidget(self.speed_slider)
        
        settings_layout.addLayout(sliders_row)
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
        self.file_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        layout.addWidget(self.file_list)
    
    def create_button(self, object_name: str, tooltip: str, icon_size: QSize) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName(object_name)
        btn.setToolTip(tooltip)
        btn.setIconSize(icon_size)
        return btn
    
    def load_icons(self):
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
        self.volume_label.setText(trf("formats.percent", value=value))
        self.volume_changed.emit(value)
    
    def on_speed_changed(self, value: int):
        self.speed_label.setText(trf("formats.speed", value=value/10))
        self.speed_changed.emit(value)
    
    def on_position_pressed(self):
        self.slider_dragging = True
    
    def on_position_released(self):
        self.slider_dragging = False
        self.position_changed.emit(self.position_slider.value() / 1000.0)
    
    def on_position_moved(self, value: int):
        pass
    
    def on_file_double_clicked(self, item):
        index = self.file_list.row(item)
        self.file_selected.emit(index)
    
    def set_playing(self, is_playing: bool):
        self.play_btn.setIcon(self.pause_icon if is_playing else self.play_icon)
        self.play_btn.setToolTip(tr("player.pause") if is_playing else tr("player.play"))
    
    def update_file_progress(self, position: float, duration: float):
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
        self.show_id3 = checked
        if hasattr(self, 'last_files_list') and self.last_files_list:
            current_row = self.file_list.currentRow()
            self.load_files(self.last_files_list, current_row)
        self.id3_toggled_signal.emit(checked)
    
    def on_auto_rewind_toggled(self, checked):
        self.auto_rewind_toggled_signal.emit(checked)

    def on_deesser_toggled(self, checked):
        self.deesser_toggled_signal.emit(checked)

    def on_compressor_toggled(self, checked):
        self.compressor_toggled_signal.emit(checked)
    
    def load_files(self, files_list: list, current_index: int = 0):
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
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            original_text = item.data(Qt.ItemDataRole.UserRole + 1)
            if not original_text and i == index:
                original_text = item.text()
                item.setData(Qt.ItemDataRole.UserRole + 1, original_text)
            
            if i == index:
                item.setText(trf("formats.playing_indicator", text=original_text))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                if original_text:
                    item.setText(original_text)
                    item.setData(Qt.ItemDataRole.UserRole + 1, None)
                
                font = item.font()
                font.setBold(False)
                item.setFont(font)
    
    def set_speed(self, value: int):
        self.speed_slider.setValue(value)
        self.speed_label.setText(trf("formats.speed", value=value/10))
    
    def set_volume(self, value: int):
        self.volume_slider.setValue(value)
        self.volume_label.setText(trf("formats.percent", value=value))
    
    def update_texts(self):
        speed_value = self.speed_slider.value() / 10
        self.speed_label.setText(trf("formats.speed", value=speed_value))
        self.volume_label.setText(trf("formats.percent", value=self.volume_slider.value()))
        
        self.btn_prev.setToolTip(tr("player.prev_track"))
        self.btn_next.setToolTip(tr("player.next_track"))
        self.btn_rw60.setToolTip(tr("player.rewind_60"))
        self.btn_rw10.setToolTip(tr("player.rewind_10"))
        self.btn_ff10.setToolTip(tr("player.forward_10"))
        self.btn_ff60.setToolTip(tr("player.forward_60"))
        self.play_btn.setToolTip(tr("player.play"))
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))
        self.deesser_btn.setToolTip(tr("player.tooltip_deesser"))
        self.compressor_btn.setToolTip(tr("player.tooltip_compressor"))
