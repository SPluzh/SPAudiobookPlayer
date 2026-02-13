import sys
from pathlib import Path
from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, 
    QLabel, QProgressBar, QListWidget, QListWidgetItem, QSizePolicy,
    QFrame, QGridLayout, QStyle, QStyleOptionSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint

from bass_player import BassPlayer
from database import DatabaseManager
from translations import tr, trf

from utils import get_icon, format_time, format_time_short
from visualizer import VisualizerButton


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
        self.current_description: str = ""
        
        # Saved state for session restoration
        self.saved_file_index: Optional[int] = None
        self.saved_position: Optional[float] = None
    
    def load_audiobook(self, audiobook_path: str) -> bool:
        """Load audiobook data from the database and prepare the player for playback"""
        self.player.pause()
        
        # Save current progress before switching, but DO NOT update the timestamp
        # for the book we are leaving (to keep it below the new one in recency)
        self.save_current_progress(update_timestamp=False)
        
        # Retrieve audiobook metadata
        audiobook_info = self.db.get_audiobook_info(audiobook_path)
        if not audiobook_info:
            return False
        
        audiobook_id, abook_name, author, title, saved_file_index, \
        saved_position, total_dur, saved_speed, use_id3_tags, \
        cover_path, cached_cover_path, description = audiobook_info
        
        # Update internal state with database values
        self.current_audiobook_id = audiobook_id
        self.current_audiobook_path = audiobook_path
        self.total_duration = total_dur or 0
        self.saved_file_index = saved_file_index
        self.saved_position = saved_position
        self.use_id3_tags = bool(use_id3_tags)
        self.current_description = description or ""
        
        # Prioritize cached cover path
        self.current_cover_path = cached_cover_path if cached_cover_path else cover_path
        
        # Load audiobook file list
        files = self.db.get_audiobook_files(audiobook_id)
        self.files_list = []
        
        for file_path, file_name, duration, track_num, tag_title, start_offset in files:
            self.files_list.append({
                'path': file_path,
                'name': file_name,
                'tag_title': tag_title or '',
                'duration': duration or 0,
                'start_offset': start_offset or 0
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
                # Seek to saved position if present, otherwise to chapter start
                start_offset = self.files_list[self.current_file_index].get('start_offset', 0)
                if saved_position is not None and saved_position > 0:
                     # saved_position in DB is the absolute position in the physical file
                     self.player.set_position(saved_position)
                elif start_offset > 0:
                    self.player.set_position(start_offset)
                
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
            start_offset = file_info.get('start_offset', 0)
            if start_offset > 0:
                self.player.set_position(start_offset)
                
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
        current_file_info = self.files_list[self.current_file_index]
        start_offset = current_file_info.get('start_offset', 0)
        
        if self.player.get_position() > start_offset + 3:
            # If more than 3 seconds into the chapter, just restart it
            self.player.set_position(start_offset)
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
        # total_pos = sum(durations of previous virtual files) + (current_physical_pos - chapter_start_offset)
        current_file_info = self.files_list[self.current_file_index]
        start_offset = current_file_info.get('start_offset', 0)
        return self.global_position + max(0, self.player.get_position() - start_offset)
    
    def get_progress_percent(self) -> int:
        """Calculate the current playback progress as a percentage (0-100)"""
        if self.total_duration <= 0:
            return 0
            
        current = self.get_current_position()
        
        # Consider finished if within 1 second of total duration
        if current >= self.total_duration - 1:
            return 100
        
        return int((current / self.total_duration) * 100)
    
    def save_current_progress(self, update_timestamp: bool = True):
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
            progress_percent,
            update_timestamp=update_timestamp
        )
        
        # Update library if we are in a recency-sensitive view
        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'library_widget') and \
           self.parent_app.library_widget.current_filter == 'in_progress':
            self.parent_app.library_widget.refresh_audiobook_item(self.current_audiobook_path)
    
    def get_audiobook_title(self) -> str:
        """Fetch the displayable name for the currently playing audiobook"""
        if not self.current_audiobook_path:
            return "Audiobook Player"
            
        info = self.db.get_audiobook_info(self.current_audiobook_path)
        if info:
            # info contains 12 fields (including description and covers)
            _, name, author, title, _, _, _, _, _, _, _, _ = info
            return name
        return "Audiobook Player"

    def add_current_as_bookmark(self, title: str, description: str = "") -> bool:
        """Save the current playback position as a bookmark"""
        if not self.current_audiobook_id:
            return False
            
        current_file = self.files_list[self.current_file_index]
        file_name = current_file['name']
        position = self.player.get_position()
        
        # If no title provided, generate one from timestamp
        if not title:
            timestamp = format_time_short(self.get_current_position())
            title = f"{tr('bookmarks.bookmark_at')} {timestamp}"
            
        return self.db.add_bookmark(
            self.current_audiobook_id,
            file_name,
            position,
            title,
            description
        ) is not None

    def jump_to_bookmark(self, bookmark_id: int) -> bool:
        """Resume playback from a specific bookmark"""
        bookmarks = self.db.get_bookmarks(self.current_audiobook_id)
        target_bookmark = next((b for b in bookmarks if b['id'] == bookmark_id), None)
        
        if not target_bookmark:
            return False
            
        # Find the file index matching the bookmark's file name
        target_file_index = -1
        for i, file_info in enumerate(self.files_list):
            if file_info['name'] == target_bookmark['file_name']:
                target_file_index = i
                break
                
        if target_file_index == -1:
            return False
            
        # Play file and seek to position
        if self.play_file_at_index(target_file_index, start_playing=True):
            self.player.set_position(target_bookmark['time_position'])
            return True
            
        return False


class ClickableSlider(QSlider):
    """A slider that jumps directly to the clicked position"""
    
    def __init__(self, orientation=Qt.Orientation.Horizontal):
        super().__init__(orientation)

    def mousePressEvent(self, event):
        """Handle mouse click to jump to value"""
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.pixelPosToRangeValue(event.pos())
            self.setValue(val)
            self.sliderMoved.emit(val)  # Emit signal continuously
            self.sliderPressed.emit() # Inform about start of interaction 
            event.accept()
        super().mousePressEvent(event)
        
    def pixelPosToRangeValue(self, pos):
        """Convert pixel coordinate to slider value"""
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        
        # Calculate available slider length
        slider_len = self.style().pixelMetric(QStyle.PixelMetric.PM_SliderLength, opt, self)
        available_width = self.width() - slider_len
        
        if available_width <= 0:
            return self.minimum()
            
        # Calculate relative position
        pos_x = pos.x() - (slider_len // 2)
        pos_x = max(0, min(pos_x, available_width))
        
        # Map to range
        range_val = self.maximum() - self.minimum()
        val = self.minimum() + (pos_x / available_width) * range_val
        
        return int(max(self.minimum(), min(self.maximum(), val)))


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
    noise_suppression_toggled_signal = pyqtSignal(bool)
    vad_threshold_changed_signal = pyqtSignal(int)  # 0-100
    vad_grace_period_changed_signal = pyqtSignal(int)  # 0-100 (mapped to 0-1000ms?)
    vad_retroactive_grace_changed_signal = pyqtSignal(int)  # 0-100
    deesser_preset_changed_signal = pyqtSignal(int) # 0, 1, 2
    compressor_preset_changed_signal = pyqtSignal(int) # 0, 1, 2
    pitch_toggled_signal = pyqtSignal(bool)
    pitch_changed_signal = pyqtSignal(float)
    bookmarks_clicked = pyqtSignal()
    
    def __init__(self):
        """Initialize widget state and prepare basic icon properties"""
        super().__init__()
        self.show_id3 = False
        self.visualizer = None # Deprecated
        self.slider_dragging = False
        
        # State variables for presets (default to Medium=1)
        self.deesser_preset = 1
        self.compressor_preset = 1
        
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
        
        # The instruction implies that self.volume_slider should be a ClickableSlider and defined here.
        # The original code defines it later as a QSlider.
        # I will define it here as ClickableSlider and remove its later QSlider definition.
        self.volume_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)

        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)
        
        # Audio Effect Buttons Row (Above Volume)
        btns_row = QHBoxLayout()
        btns_row.setSpacing(5)
        
        icon_size = QSize(20, 20) # Added as per instruction
        
        # ID3 Meta-tag Toggle
        self.id3_btn = QPushButton(tr("player.btn_id3"))
        self.id3_btn.setCheckable(True)
        self.id3_btn.setFixedWidth(40)
        self.id3_btn.setObjectName("id3Btn")
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.id3_btn.toggled.connect(self.on_id3_toggled)
        btns_row.addWidget(self.id3_btn)
        
        # Auto-rewind Toggle
        self.auto_rewind_btn = QPushButton(tr("player.btn_autorewind"))
        self.auto_rewind_btn.setCheckable(True)
        self.auto_rewind_btn.setFixedWidth(40)
        self.auto_rewind_btn.setObjectName("autoRewindBtn")
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))
        self.auto_rewind_btn.toggled.connect(self.on_auto_rewind_toggled)
        btns_row.addWidget(self.auto_rewind_btn)

        # Bookmarks Button
        self.bookmarks_btn = QPushButton(tr("bookmarks.button_label"))
        self.bookmarks_btn.setCheckable(False) # Unlike ID3, this opens a dialog
        self.bookmarks_btn.setFixedWidth(40)
        self.bookmarks_btn.setObjectName("bookmarksBtn")
        self.bookmarks_btn.setToolTip(tr("bookmarks.list_title"))
        self.bookmarks_btn.clicked.connect(self.bookmarks_clicked)
        btns_row.addWidget(self.bookmarks_btn)

        btns_row.addStretch()
        
        # DeEsser Toggle
        self.deesser_btn = QPushButton(tr("player.btn_deesser"))
        self.deesser_btn.setCheckable(True)
        self.deesser_btn.setFixedWidth(40)
        self.deesser_btn.setObjectName("deesserBtn")
        self.deesser_btn.setToolTip(tr("player.tooltip_deesser"))
        self.deesser_btn.toggled.connect(self.on_deesser_toggled)
        # Right-click for DeEsser presets
        self.deesser_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.deesser_btn.customContextMenuRequested.connect(self.show_deesser_popup)
        btns_row.addWidget(self.deesser_btn)
        
        self.compressor_btn = QPushButton(tr("player.btn_compressor"))
        self.compressor_btn.setCheckable(True)
        self.compressor_btn.setFixedWidth(40)
        self.compressor_btn.setObjectName("compressorBtn")
        self.compressor_btn.setToolTip(tr("player.tooltip_compressor"))
        self.compressor_btn.toggled.connect(self.on_compressor_toggled)
        # Right-click for Compressor presets
        self.compressor_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.compressor_btn.customContextMenuRequested.connect(self.show_compressor_popup)
        btns_row.addWidget(self.compressor_btn)
        
        # Noise Suppression Toggle
        self.noise_suppression_btn = QPushButton(tr("player.btn_noise_suppression"))
        self.noise_suppression_btn.setCheckable(True)
        self.noise_suppression_btn.setFixedWidth(40)
        self.noise_suppression_btn.setObjectName("noiseSuppressionBtn")
        self.noise_suppression_btn.setToolTip(tr("player.tooltip_noise_suppression"))
        self.noise_suppression_btn.toggled.connect(self.on_noise_suppression_toggled)
        # Right-click for VAD threshold popup
        self.noise_suppression_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.noise_suppression_btn.customContextMenuRequested.connect(self.show_vad_slider_popup)
        btns_row.addWidget(self.noise_suppression_btn)
        
        # Pitch Toggle
        self.pitch_btn = QPushButton(tr("player.btn_pitch"))
        self.pitch_btn.setCheckable(True)
        self.pitch_btn.setFixedWidth(40)
        self.pitch_btn.setObjectName("pitchBtn")
        self.pitch_btn.setToolTip(tr("player.tooltip_pitch"))
        self.pitch_btn.toggled.connect(self.on_pitch_toggled)
        # Right-click for Pitch settings
        self.pitch_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pitch_btn.customContextMenuRequested.connect(self.show_pitch_popup)
        btns_row.addWidget(self.pitch_btn)
        
        # VAD Threshold Popup (Advanced Settings)
        self.vad_popup = QWidget(self, Qt.WindowType.Popup)
        self.vad_popup.setObjectName("vadPopup")
        vad_layout = QGridLayout(self.vad_popup)
        vad_layout.setContentsMargins(8, 8, 8, 8)
        vad_layout.setSpacing(8)
        
        # 1. Sensitivity (Threshold)
        self.vad_sens_label_title = QLabel(tr("player.vad_sens_label"))
        vad_layout.addWidget(self.vad_sens_label_title, 0, 0)
        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(0, 100)
        self.vad_slider.setValue(90)
        self.vad_slider.setFixedWidth(120)
        self.vad_slider.setToolTip(tr("player.tooltip_vad_threshold"))
        self.vad_slider.valueChanged.connect(self.on_vad_threshold_changed)
        vad_layout.addWidget(self.vad_slider, 0, 1)
        self.vad_label = QLabel("90%")
        self.vad_label.setFixedWidth(35)
        vad_layout.addWidget(self.vad_label, 0, 2)
        
        # 2. Grace Period
        self.vad_grace_label_title = QLabel(tr("player.vad_grace_label"))
        vad_layout.addWidget(self.vad_grace_label_title, 1, 0)
        self.vad_grace_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_grace_slider.setRange(0, 100) # 0-100% (arbitrary scale)
        self.vad_grace_slider.setValue(20)
        self.vad_grace_slider.setFixedWidth(120)
        self.vad_grace_slider.setToolTip(tr("player.tooltip_vad_grace"))
        self.vad_grace_slider.valueChanged.connect(self.on_vad_grace_changed)
        vad_layout.addWidget(self.vad_grace_slider, 1, 1)
        self.vad_grace_label = QLabel("20%")
        self.vad_grace_label.setFixedWidth(35)
        vad_layout.addWidget(self.vad_grace_label, 1, 2)
        
        # 3. Retroactive Grace
        self.vad_retro_label_title = QLabel(tr("player.vad_retro_label"))
        vad_layout.addWidget(self.vad_retro_label_title, 2, 0)
        self.vad_retro_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_retro_slider.setRange(0, 100)
        self.vad_retro_slider.setValue(0)
        self.vad_retro_slider.setFixedWidth(120)
        self.vad_retro_slider.setToolTip(tr("player.tooltip_vad_retro"))
        self.vad_retro_slider.valueChanged.connect(self.on_vad_retro_changed)
        vad_layout.addWidget(self.vad_retro_slider, 2, 1)
        self.vad_retro_label = QLabel("0%")
        self.vad_retro_label.setFixedWidth(35)
        vad_layout.addWidget(self.vad_retro_label, 2, 2)
        
        # DeEsser Preset Popup
        self.deesser_popup = QWidget(self, Qt.WindowType.Popup)
        self.deesser_popup.setObjectName("deesserPopup")
        deesser_layout = QHBoxLayout(self.deesser_popup)
        deesser_layout.setContentsMargins(8, 4, 8, 4)
        
        self.deesser_slider = QSlider(Qt.Orientation.Horizontal)
        self.deesser_slider.setRange(0, 2) # 0=Light, 1=Medium, 2=Strong
        self.deesser_slider.setValue(1)
        self.deesser_slider.setFixedWidth(80)
        self.deesser_slider.valueChanged.connect(self.on_deesser_preset_changed)
        deesser_layout.addWidget(self.deesser_slider)
        
        self.deesser_desc_label = QLabel(tr("player.preset_medium")) # Default
        self.deesser_desc_label.setFixedWidth(60)
        self.deesser_desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        deesser_layout.addWidget(self.deesser_desc_label)
        
        # Compressor Preset Popup
        self.compressor_popup = QWidget(self, Qt.WindowType.Popup)
        self.compressor_popup.setObjectName("compressorPopup")
        comp_layout = QHBoxLayout(self.compressor_popup)
        comp_layout.setContentsMargins(8, 4, 8, 4)
        
        self.comp_slider = QSlider(Qt.Orientation.Horizontal)
        self.comp_slider.setRange(0, 2) # 0=Light, 1=Medium, 2=Strong
        self.comp_slider.setValue(1)
        self.comp_slider.setFixedWidth(80)
        self.comp_slider.valueChanged.connect(self.on_compressor_preset_changed)
        comp_layout.addWidget(self.comp_slider)
        
        self.comp_desc_label = QLabel(tr("player.preset_medium")) # Default
        self.comp_desc_label.setFixedWidth(60)
        self.comp_desc_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        comp_layout.addWidget(self.comp_desc_label)
        
        # Pitch Popup
        self.pitch_popup = QWidget(self, Qt.WindowType.Popup)
        self.pitch_popup.setObjectName("pitchPopup")
        pitch_layout = QHBoxLayout(self.pitch_popup)
        pitch_layout.setContentsMargins(8, 4, 8, 4)
        
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-120, 120) # -12.0 to +12.0 semitones
        self.pitch_slider.setValue(0)
        self.pitch_slider.setFixedWidth(120)
        self.pitch_slider.valueChanged.connect(self.on_pitch_slider_changed)
        pitch_layout.addWidget(self.pitch_slider)
        
        self.pitch_val_label = QLabel(f"0.0 {tr('player.pitch_label')}")
        self.pitch_val_label.setFixedWidth(60)
        self.pitch_val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pitch_layout.addWidget(self.pitch_val_label)

        settings_layout.addLayout(btns_row)
        
        # Sliders Row (Volume + Speed)
        sliders_row = QHBoxLayout()
        sliders_row.setSpacing(5)
        
        # Volume
        # Volume (already defined as ClickableSlider above)
        self.volume_slider.setObjectName("volumeSlider")
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
        
        # Core Play/Pause Action (VisualizerButton)
        self.play_btn = VisualizerButton()
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setToolTip(tr("player.play"))
        self.play_btn.setIconSize(icon_size) # Use smaller icon size for button to leave room for vis? Or standard 32? Let's keep 32.
        self.play_btn.setIconSize(QSize(32, 32))
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
    
    def update_file_progress(self, position: float, duration: float, speed: float = 1.0):
        if not self.slider_dragging:
            display_pos = position / speed if speed > 0 else position
            if duration >= 3600:
                self.time_current.setText(format_time(display_pos))
            else:
                self.time_current.setText(format_time_short(display_pos))
                
            if duration > 0:
                self.position_slider.setValue(int((position / duration) * 1000))
        
        display_dur = duration / speed if speed > 0 else duration
        if duration >= 3600:
            self.time_duration.setText(format_time(display_dur))
        else:
            self.time_duration.setText(format_time_short(display_dur))
    
    def update_total_progress(self, current: float, total: float, speed: float = 1.0):
        if speed > 0:
            self.total_time_label.setText(format_time(current / speed))
            self.total_duration_label.setText(format_time(total / speed))
        else:
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
    
    def on_noise_suppression_toggled(self, checked):
        self.noise_suppression_toggled_signal.emit(checked)
    
    def show_vad_slider_popup(self, pos):
        """Show VAD threshold slider popup on right-click"""
        global_pos = self.noise_suppression_btn.mapToGlobal(QPoint(0, self.noise_suppression_btn.height()))
        self.vad_popup.move(global_pos)
        self.vad_popup.show()
    
    def on_vad_threshold_changed(self, value):
        """Handle VAD threshold slider change"""
        self.vad_label.setText(f"{value}%")
        self.vad_threshold_changed_signal.emit(value)
    
    def set_vad_threshold_value(self, value: int):
        """Set VAD slider value programmatically (from settings)"""
        self.vad_slider.blockSignals(True)
        self.vad_slider.setValue(value)
        self.vad_label.setText(f"{value}%")
        self.vad_slider.blockSignals(False)

    def on_vad_grace_changed(self, value: int):
        """Handle VAD Grace Period slider change"""
        self.vad_grace_label.setText(f"{value}%")
        self.vad_grace_period_changed_signal.emit(value)

    def set_vad_grace_value(self, value: int):
        """Set VAD Grace Period slider value programmatically"""
        self.vad_grace_slider.blockSignals(True)
        self.vad_grace_slider.setValue(value)
        self.vad_grace_label.setText(f"{value}%")
        self.vad_grace_slider.blockSignals(False)

    def on_vad_retro_changed(self, value: int):
        """Handle Retroactive VAD Grace slider change"""
        self.vad_retro_label.setText(f"{value}%")
        self.vad_retroactive_grace_changed_signal.emit(value)

    def set_vad_retro_value(self, value: int):
        """Programmatically update VAD retroactive grace slider"""
        self.vad_retro_slider.blockSignals(True)
        self.vad_retro_slider.setValue(int(value))
        self.vad_retro_label.setText(f"{value}%")
        self.vad_retro_slider.blockSignals(False)

    def show_deesser_popup(self, pos):
        """Show DeEsser preset popup below the button"""
        global_pos = self.deesser_btn.mapToGlobal(QPoint(0, self.deesser_btn.height()))
        self.deesser_popup.move(global_pos)
        self.deesser_popup.show()

    def on_deesser_preset_changed(self, value: int):
        """Handle changes to DeEsser preset slider"""
        # Update label text
        labels = {
            0: tr("player.preset_light"),
            1: tr("player.preset_medium"),
            2: tr("player.preset_strong")
        }
        self.deesser_desc_label.setText(labels.get(value, ""))
        self.deesser_preset_changed_signal.emit(value)

    def set_deesser_preset_value(self, value: int):
        """Programmatically set DeEsser preset"""
        self.deesser_slider.blockSignals(True)
        self.deesser_slider.setValue(value)
        # Also update label
        labels = {
            0: tr("player.preset_light"),
            1: tr("player.preset_medium"),
            2: tr("player.preset_strong")
        }
        self.deesser_desc_label.setText(labels.get(value, ""))
        self.deesser_slider.blockSignals(False)

    def show_compressor_popup(self, pos):
        """Show Compressor preset popup below the button"""
        global_pos = self.compressor_btn.mapToGlobal(QPoint(0, self.compressor_btn.height()))
        self.compressor_popup.move(global_pos)
        self.compressor_popup.show()

    def on_compressor_preset_changed(self, value: int):
        """Handle changes to Compressor preset slider"""
        labels = {
            0: tr("player.preset_light"),
            1: tr("player.preset_medium"),
            2: tr("player.preset_strong")
        }
        self.comp_desc_label.setText(labels.get(value, ""))
        self.compressor_preset_changed_signal.emit(value)

    def set_compressor_preset_value(self, value: int):
        """Programmatically set Compressor preset"""
        self.comp_slider.blockSignals(True)
        self.comp_slider.setValue(value)
        # Also update label
        labels = {
            0: tr("player.preset_light"),
            1: tr("player.preset_medium"),
            2: tr("player.preset_strong")
        }
        self.comp_desc_label.setText(labels.get(value, ""))
        self.comp_slider.blockSignals(False)

    def on_pitch_toggled(self, checked):
        self.pitch_toggled_signal.emit(checked)

    def show_pitch_popup(self, pos):
        """Show Pitch settings popup below the button"""
        global_pos = self.pitch_btn.mapToGlobal(QPoint(0, self.pitch_btn.height()))
        self.pitch_popup.move(global_pos)
        self.pitch_popup.show()

    def on_pitch_slider_changed(self, value: int):
        """Handle pitch slider change (value is x10 semitones)"""
        semitones = value / 10.0
        self.pitch_val_label.setText(f"{semitones:+.1f} {tr('player.pitch_label')}")
        self.pitch_changed_signal.emit(semitones)

    def set_pitch_value(self, semitones: float):
        """Programmatically set pitch value"""
        self.pitch_slider.blockSignals(True)
        self.pitch_slider.setValue(int(semitones * 10))
        self.pitch_val_label.setText(f"{semitones:+.1f} {tr('player.pitch_label')}")
        self.pitch_slider.blockSignals(False)

    
    def set_noise_suppression_active(self, active: bool):
        """Visual indicator when noise suppression is processing"""
        self.noise_suppression_btn.setProperty("processing", active)
        self.noise_suppression_btn.style().unpolish(self.noise_suppression_btn)
        self.noise_suppression_btn.style().polish(self.noise_suppression_btn)
    
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
        """Update UI texts when language changes"""
        # Buttons
        self.id3_btn.setText(tr("player.btn_id3"))
        self.id3_btn.setToolTip(tr("player.show_id3"))
        
        self.bookmarks_btn.setText(tr("bookmarks.button_label"))
        self.bookmarks_btn.setToolTip(tr("bookmarks.list_title"))
        
        self.auto_rewind_btn.setText(tr("player.btn_autorewind"))
        self.auto_rewind_btn.setToolTip(tr("player.tooltip_auto_rewind"))
        
        self.deesser_btn.setText(tr("player.btn_deesser"))
        self.deesser_btn.setToolTip(tr("player.tooltip_deesser"))
        
        self.compressor_btn.setText(tr("player.btn_compressor"))
        self.compressor_btn.setToolTip(tr("player.tooltip_compressor"))
        
        self.noise_suppression_btn.setText(tr("player.btn_noise_suppression"))
        self.noise_suppression_btn.setToolTip(tr("player.tooltip_noise_suppression"))
        
        self.pitch_btn.setText(tr("player.btn_pitch"))
        self.pitch_btn.setToolTip(tr("player.tooltip_pitch"))
        
        # Sliders
        self.volume_slider.setToolTip(tr("player.volume"))
        
        # Update dynamic labels
        speed_value = self.speed_slider.value() / 10
        self.speed_label.setText(trf("formats.speed", value=speed_value))
        self.volume_label.setText(trf("formats.percent", value=self.volume_slider.value()))
        
        # Control Buttons Tooltips
        self.btn_prev.setToolTip(tr("player.prev_track"))
        self.btn_next.setToolTip(tr("player.next_track"))
        self.btn_rw60.setToolTip(tr("player.rewind_60"))
        self.btn_rw10.setToolTip(tr("player.rewind_10"))
        self.btn_ff10.setToolTip(tr("player.forward_10"))
        self.btn_ff60.setToolTip(tr("player.forward_60"))
        self.play_btn.setToolTip(tr("player.play"))
        
        # Popups
        if hasattr(self, 'deesser_desc_label'):
             # Re-trigger preset changed to update label text
             self.on_deesser_preset_changed(self.deesser_preset)
             
        if hasattr(self, 'comp_desc_label'):
             self.on_compressor_preset_changed(self.compressor_preset)
             
        if hasattr(self, 'vad_label'):
            # Update VAD labels if needed, though they are usually numeric. 
            # But the static labels "Sensitivity:", etc are in the popup layout.
            if hasattr(self, 'vad_sens_label_title'):
                self.vad_sens_label_title.setText(tr("player.vad_sens_label"))
            if hasattr(self, 'vad_grace_label_title'):
                self.vad_grace_label_title.setText(tr("player.vad_grace_label"))
            if hasattr(self, 'vad_retro_label_title'):
                self.vad_retro_label_title.setText(tr("player.vad_retro_label"))
            
            # Update tooltips for VAD sliders
            if hasattr(self, 'vad_slider'):
                self.vad_slider.setToolTip(tr("player.tooltip_vad_threshold"))
            if hasattr(self, 'vad_grace_slider'):
                self.vad_grace_slider.setToolTip(tr("player.tooltip_vad_grace"))
            if hasattr(self, 'vad_retro_slider'):
                self.vad_retro_slider.setToolTip(tr("player.tooltip_vad_retro"))
        
        if hasattr(self, 'pitch_val_label'):
             # Update pitch label unit "st"
             semitones = self.pitch_slider.value() / 10.0
             self.pitch_val_label.setText(f"{semitones:+.1f} {tr('player.pitch_label')}")
