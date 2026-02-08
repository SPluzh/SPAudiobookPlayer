import sys
import os
import subprocess
import configparser
import shutil
from functools import lru_cache
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar, 
    QLabel, QLineEdit, QMenu, QStyle, QButtonGroup, QDialog, 
    QTextEdit, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QStyledItemDelegate
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QRectF, QPoint, QPointF, QThread
from PyQt6.QtGui import (
    QIcon, QAction, QPixmap, QBrush, QColor, QFont, QPen, QPainter, 
    QPainterPath, QFontMetrics, QTextCursor
)

from database import DatabaseManager
from translations import tr, trf
from utils import (
    get_base_path, get_icon, load_icon, resize_icon, 
    format_time, format_time_short, OutputCapture
)
from scanner import AudiobookScanner
from tags_dialog import TagManagerDialog
from metadata_dialog import MetadataEditDialog

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
        'delegate_file_count',
        'delegate_favorite'
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
    
    @lru_cache(maxsize=32)
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
        self._get_style.cache_clear()
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
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
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

    def get_heart_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the favorite heart icon relative to the main icon"""
        heart_size = 20.0
        # Position: Top-Right of icon, same as in paint
        return QRectF(
            float(icon_rect.right() - heart_size + 5), 
            float(icon_rect.top() - 5), 
            float(heart_size), float(heart_size)
        )

    def get_info_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the info icon"""
        info_size = 20.0
        # Position: Top-Left of icon, mirrored from heart
        return QRectF(
            float(icon_rect.left() - 5), 
            float(icon_rect.top() - 5), 
            float(info_size), float(info_size)
        )

    def _paint_audiobook(self, painter, option, index):
        """Render detailed audiobook item with cover, progress, and metadata"""
        painter.save()
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_y = option.rect.top() + (option.rect.height() - self.audiobook_icon_size) // 2
        icon_rect = QRect(
            option.rect.left() + self.horizontal_padding,
            icon_y,
            self.audiobook_icon_size,
            self.audiobook_icon_size
        )
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            painter.restore()
            return
            
        author, title, narrator, file_count, duration, listened_duration, \
        progress_percent, codec, b_min, b_max, b_mode, container = data[:12]
        description = data[12] if len(data) > 12 else ""
        
        # Unpack status data for favorites
        
        # Unpack status data for favorites
        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
        is_favorite = False
        if status_data and len(status_data) >= 3:
            is_favorite = status_data[2]
        
        if icon:
            painter.save()
            path = QPainterPath()
            path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
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

            # Draw Favorite Heart
            if is_favorite:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Position: Top-Right of icon
                heart_rect = self.get_heart_rect(QRectF(icon_rect))
                
                # Draw circle background
                painter.setBrush(QColor(255, 255, 255, 200))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(heart_rect)
                
                # Draw Heart Shape
                painter.setBrush(QColor("#018574"))
                # Make the heart wider by reducing horizontal padding
                hr = heart_rect.adjusted(1, 2, -1, -3)
                
                path = QPainterPath()
                path.moveTo(hr.center().x(), hr.bottom())
                path.cubicTo(hr.right(), hr.center().y(), hr.right(), hr.top(), hr.center().x(), hr.top() + hr.height()*0.2)
                path.cubicTo(hr.left(), hr.top(), hr.left(), hr.center().y(), hr.center().x(), hr.bottom())
                
                painter.drawPath(path)
                painter.drawPath(path)
                painter.restore()

            # Draw Info Icon if description exists (Always visible)
            if description:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                info_rect = self.get_info_rect(QRectF(icon_rect))
                
                # Check hover for info icon
                is_over_info = False
                if self.mouse_pos and info_rect.contains(QPointF(self.mouse_pos)):
                    is_over_info = True
                    
                painter.setBrush(QColor(255, 255, 255, 200) if not is_over_info else QColor(255, 255, 255, 255))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(info_rect)
                
                # Draw 'i'
                painter.setPen(QColor("#018574"))
                font = painter.font()
                font.setBold(True)
                font.setPixelSize(14)
                painter.setFont(font)
                painter.drawText(info_rect, Qt.AlignmentFlag.AlignCenter, "i")
                painter.restore()
 
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
        
        # Technical Metadata (Bitrate, Mode, Codec/Container)
        if b_min or codec or container:
            # Format: [icon] [bitrate] [units] [mode] [codec]/[container]
            tech_line = []
            
            # 1. Bitrate range
            if b_min:
                # Safe conversion for old/new bitrate values (bps vs kbps)
                calc_min = b_min // 1000 if b_min > 5000 else b_min
                calc_max = b_max // 1000 if b_max > 5000 else b_max
                
                if calc_min == calc_max:
                    br_str = f"{calc_min}"
                else:
                    br_str = f"{calc_min}-{calc_max}"
                
                tech_line.append(f"{br_str} {tr('units.kbps', default='kbps')}")
            
            # 2. Bitrate Mode (VBR/CBR)
            if b_mode:
                tech_line.append(b_mode)
            
            # 3. Codec and Container
            codec_info = []
            if codec:
                codec_info.append(codec.lower())
            if container and container.lower() != codec.lower():
                codec_info.append(container.lower())
            
            if codec_info:
                tech_line.append("/".join(codec_info))
                
            if tech_line:
                full_tech_text = f"{tr('delegate.codec_prefix')} {' '.join(tech_line)}"
                # Use same style as narrator or file count for technical info
                font_tech, color_tech = self._get_style('delegate_file_count')
                info_parts.append((full_tech_text, font_tech, color_tech))
        
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
        
        text_y += line_height + self.line_spacing
        
        # Tags rendering
        tags = index.data(Qt.ItemDataRole.UserRole + 4)
        if tags:
            tag_x = text_x
            
            painter.save()
            
            for tag in tags:
                tag_name = tag['name']
                tag_color = QColor(tag['color'] or "#018574")
                
                # Dynamic text color based on brightness
                text_color = Qt.GlobalColor.white if tag_color.lightness() < 130 else Qt.GlobalColor.black
                
                painter.setFont(QFont("Segoe UI", 8))
                fm = painter.fontMetrics()
                t_w = fm.horizontalAdvance(tag_name)
                t_h = fm.height() + 4
                
                tag_rect = QRectF(float(tag_x), float(text_y), float(t_w + 12), float(t_h))
                
                # Check for overflow
                if tag_rect.right() > option.rect.right() - 10:
                    break
                    
                path = QPainterPath()
                path.addRoundedRect(tag_rect, 4, 4)
                
                painter.setBrush(tag_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)
                
                painter.setPen(text_color)
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_name)
                
                tag_x += tag_rect.width() + 6
                
            painter.restore()

        painter.restore()


class LibraryTree(QTreeWidget):
    """Customized tree widget that handles hover detection and direct interaction with audiobook 'Play' buttons"""
    play_button_clicked = pyqtSignal(str) # Emits the relative path to the selected audiobook
    favorite_clicked = pyqtSignal(str) # Emits path when heart is clicked
    description_requested = pyqtSignal(str) # Emits path when info icon is clicked

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
                     icon_y = rect.top() + (rect.height() - icon_size) // 2
                     icon_rect = QRect(
                         rect.left() + delegate.horizontal_padding,
                         icon_y,
                         icon_size, icon_size
                     )
                     play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                     if play_rect.contains(QPointF(event.pos())):
                         self.setCursor(Qt.CursorShape.PointingHandCursor)
                         return
                     
                     # Check heart hover
                     has_fav_data = False
                     status_data = index.data(Qt.ItemDataRole.UserRole + 3)
                     if status_data and len(status_data) >= 3:
                         if status_data[2]: # is_favorite
                             has_fav_data = True
                     
                     if has_fav_data:
                         heart_rect = delegate.get_heart_rect(QRectF(icon_rect))
                         if heart_rect.contains(QPointF(event.pos())):
                             self.setCursor(Qt.CursorShape.PointingHandCursor)
                             return

                     # Check info hover
                     data = index.data(Qt.ItemDataRole.UserRole + 2)
                     description = data[12] if data and len(data) > 12 else ""
                     if description:
                         info_rect = delegate.get_info_rect(QRectF(icon_rect))
                         if info_rect.contains(QPointF(event.pos())):
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
                        icon_y = rect.top() + (rect.height() - icon_size) // 2
                        icon_rect = QRect(
                            rect.left() + delegate.horizontal_padding,
                            icon_y,
                            icon_size, icon_size
                        )
                        play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                        if play_rect.contains(QPointF(event.pos())):
                            path = index.data(Qt.ItemDataRole.UserRole)
                            self.play_button_clicked.emit(path)
                            return
                        
                        # Check heart click
                        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
                        is_favorite = False
                        if status_data and len(status_data) >= 3:
                            is_favorite = status_data[2]
                        
                        if is_favorite:
                            heart_rect = delegate.get_heart_rect(QRectF(icon_rect))
                            if heart_rect.contains(QPointF(event.pos())):
                                path = index.data(Qt.ItemDataRole.UserRole)
                                self.favorite_clicked.emit(path)
                                return
                        
                        # Check info click
                        data = index.data(Qt.ItemDataRole.UserRole + 2)
                        description = data[12] if data and len(data) > 12 else ""
                        if description:
                            info_rect = delegate.get_info_rect(QRectF(icon_rect))
                            if info_rect.contains(QPointF(event.pos())):
                                path = index.data(Qt.ItemDataRole.UserRole)
                                self.description_requested.emit(path)
                                return
        super().mousePressEvent(event)


class LibraryWidget(QWidget):
    """Container for the audiobook tree, search filters, and status-based navigation buttons"""
    
    audiobook_selected = pyqtSignal(str) # Emits the relative path of the selected audiobook
    show_folders_toggled = pyqtSignal(bool) # Emits the new state of the folders toggle
    delete_requested = pyqtSignal(int, str) # Emits (audiobook_id, rel_path)
    folder_delete_requested = pyqtSignal(str) # Emits folder relative path
    scan_requested = pyqtSignal()
    
    # Internal configuration for status filtering
    FILTER_CONFIG = {
        'all': {'label': "library.filter_all", 'icon': "filter_all"},
        'not_started': {'label': "library.filter_not_started", 'icon': "filter_not_started"},
        'in_progress': {'label': "library.filter_in_progress", 'icon': "filter_in_progress"},
        'completed': {'label': "library.filter_completed", 'icon': "filter_completed"},
    }
    
    def __init__(self, db_manager: DatabaseManager, config: dict, delegate=None, show_folders: bool = False, show_filter_labels: bool = True):
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
        self.show_filter_labels = show_filter_labels
        self.cached_library_data = None  # Cache for fast reconstruction
        self.setup_ui()
        self.load_icons()
    
    def setup_ui(self):
        """Assemble the search bar, filter buttons, and the main library tree widget"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(3)
        
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
        
        # Favorites Filter (Icon-only)
        self.btn_favorites = QPushButton("")
        self.btn_favorites.setObjectName("filterBtn")
        self.btn_favorites.setCheckable(True)
        self.btn_favorites.setFixedWidth(40)
        self.btn_favorites.setIcon(get_icon("favorites"))
        self.btn_favorites.setToolTip(tr("library.filter_favorites"))
        self.btn_favorites.clicked.connect(lambda: self.apply_filter('favorites'))
        self.btn_favorites.setProperty('filter_type', 'favorites')
        filter_layout.addWidget(self.btn_favorites)
        
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
        
        # Add favorites to group and dictionary for state management
        self.filter_group.addButton(self.btn_favorites)
        self.filter_buttons['favorites'] = self.btn_favorites
            
        last_btn = self.filter_buttons[self.current_filter]
        if last_btn:
             last_btn.setChecked(True)

        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)
        
        # Дерево аудиокниг
        self.tree = LibraryTree()
        self.tree.setHeaderHidden(True)
        self.tree.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Disable focus to avoid intercepting hotkeys
        self.tree.setIconSize(QSize(
            self.config.get('audiobook_icon_size', 100),
            self.config.get('audiobook_icon_size', 100)
        ))
        self.tree.setIndentation(20)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.favorite_clicked.connect(self.on_tree_favorite_clicked)
        self.tree.description_requested.connect(self.show_description_dialog)
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
        show_text = (self.width() >= 450) if self.show_filter_labels else False
        
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

    
    def on_tree_favorite_clicked(self, path: str):
        """Handle click on the favorite heart icon in the tree"""
        # Find ID for path
        info = self.db.get_audiobook_info(path)
        if not info:
            return
            
        audiobook_id = info[0]
        
        # Check current status to prevent accidental reset (unfavoriting)
        # We want this action to: Ensure Favorite AND/OR Go To Favorites
        data = self.db.get_audiobook_by_path(path)
        if data and not data.get('is_favorite'):
             self.toggle_favorite(audiobook_id, path)
        
        # Activate Favorites filter if not already active
        if self.current_filter != 'favorites':
            if self.btn_favorites:
                self.btn_favorites.setChecked(True)
                self.btn_favorites.setChecked(True)
                self.apply_filter('favorites')

    def show_description_dialog(self, path: str):
        """Show a dialog with the audiobook description"""
        info = self.db.get_audiobook_by_path(path)
        if not info or not info.get('description'):
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("library.description_title"))
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title_label = QLabel(info.get('title', ''))
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(12)
        title_label.setFont(font)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        
        # Text
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info.get('description', ''))
        layout.addWidget(text_edit)
        
        # Close button
        close_btn = QPushButton(tr("dialog.close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
        
        dialog.exec()

    def apply_filter(self, filter_type: str):
        """Switch the current library view filter and refresh the audiobook listing"""
        self.current_filter = filter_type
        # When switching filters, reload from DB to apply correct sorting and subset
        self.load_audiobooks(use_cache=False)
    
    def on_show_folders_toggled(self, checked):
        """Toggle folder visibility and refresh the library"""
        self.show_folders = checked
        self.show_folders_toggled.emit(checked)
        self.load_audiobooks(use_cache=True)

    def refresh_library(self):
        """Force a database reload and refresh the UI"""
        self.load_audiobooks(use_cache=False)

    def load_audiobooks(self, use_cache: bool = True):
        """Retrieve and display audiobooks from the database according to the active filter"""
        self.current_playing_item = None
        self.tree.clear()
        
        # Check cache or force reload
        # Always load all audiobooks to enable fast client-side filtering
        if not use_cache or self.cached_library_data is None:
             self.cached_library_data = self.db.load_audiobooks_from_db(self.current_filter)

        # Pre-fetch all tags logic
        all_tags = self.db.get_all_audiobook_tags()
        
        # Optimize tree population by disabling repaints and sorting
        self.tree.setUpdatesEnabled(False)
        self.tree.blockSignals(True)
        try:
            # If folders are hidden and we are in a non-'all' filter,
            # we should populate as a flat list to guarantee the SQL sort order
            # is visually preserved across the entire library.
            if not self.show_folders and self.current_filter != 'all':
                all_items = []
                for parent_path, items in self.cached_library_data.items():
                    for item_data in items:
                        if not item_data['is_folder']:
                            # Attach tags to data dict temporarily for item creation
                            if 'id' in item_data:
                                item_data['tags'] = all_tags.get(item_data['id'], [])
                            all_items.append(item_data)
                
                # Re-sort at client side to ensure absolute order (SQL order might be fragmented in the map)
                sort_key = 'name'
                if self.current_filter == 'in_progress': sort_key = 'last_updated'
                elif self.current_filter == 'completed': sort_key = 'time_finished'
                elif self.current_filter == 'not_started': sort_key = 'time_added'
                elif self.current_filter == 'favorites': sort_key = 'name' # Sort favorites by name
                
                all_items.sort(key=lambda x: (x.get(sort_key) or '', x.get('name') or ''), reverse=(sort_key != 'name'))
                
                # Batch add to avoid recursion overhead
                self.add_flat_items(self.tree, all_items)
            else:
                # Need to inject tags into the recursive add
                # We can modify cached_library_data in place safely as it is a dict of lists
                for items in self.cached_library_data.values():
                    for item_data in items:
                        if not item_data['is_folder'] and 'id' in item_data:
                             item_data['tags'] = all_tags.get(item_data['id'], [])
                             
                self.add_items_from_db(self.tree, '', self.cached_library_data)
        finally:
            self.tree.blockSignals(False)
            self.tree.setUpdatesEnabled(True)
            
        # Apply current filter immediately after loading
        self.filter_audiobooks()
    
    def add_flat_items(self, parent_item, items_list: list):
        """Populate the tree with a flat list of audiobooks, ignoring hierarchy"""
        for data in items_list:
            self._create_item_from_data(parent_item, data)

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
                
                # Sub-items traversal
                self.add_items_from_db(item, data['path'], data_by_parent)
            else:
                self._create_item_from_data(parent_item, data)

    def _create_item_from_data(self, parent_item, data):
        """Shared helper to create a tree item for an audiobook with all its metadata and icons"""
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
            data['progress_percent'],
            data['codec'],
            data['bitrate_min'],
            data['bitrate_max'],
            data['bitrate_mode'],
            data['container'],
            data.get('description', '')
        ))
        # Store status flags for client-side filtering
        item.setData(0, Qt.ItemDataRole.UserRole + 3, (
            data['is_started'],
            data['is_completed'],
            data['is_favorite']
        ))
        
        # Fetch and scale the audiobook cover
        cover_icon = None
        
        # Prioritize cached cover (fastest access)
        cover_p_str = data.get('cached_cover_path')
        if not cover_p_str:
             cover_p_str = data.get('cover_path')
             
        if cover_p_str:
            cover_p = Path(cover_p_str)
            # For relative paths (legacy or uncached), resolve them against the library's root directory
            if not cover_p.is_absolute() and self.config.get('default_path'):
                cover_p = Path(self.config.get('default_path')) / cover_p
                
            cover_icon = load_icon(
                cover_p,
                self.config.get('audiobook_icon_size', 100),
                force_square=True
            )
        item.setIcon(0, cover_icon or self.default_audiobook_icon)
        
        # Store tags
        if 'tags' in data:
            item.setData(0, Qt.ItemDataRole.UserRole + 4, data['tags'])
            
        return item

    
    def filter_audiobooks(self):
        """Handle real-time search queries by filtering tree items based on text matching"""
        search_text = self.search_edit.text().lower().strip()
        
        if not search_text and self.current_filter == 'all':
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
                has_visible_children = self.filter_tree_items(child, search_text)
                folder_name = child.text(0).lower()
                
                if search_text:
                    fn_matches = search_text in folder_name
                    child.setHidden(not (fn_matches or has_visible_children))
                else:
                    child.setHidden(not has_visible_children)

                if not child.isHidden():
                    has_visible = True
                    
            elif item_type == 'audiobook':
                # 1. Check Status Filter
                status_data = child.data(0, Qt.ItemDataRole.UserRole + 3)
                status_match = True
                if status_data and len(status_data) >= 2:
                    is_started = status_data[0]
                    is_completed = status_data[1]
                    if self.current_filter == 'not_started':
                        status_match = not is_started
                    elif self.current_filter == 'in_progress':
                        status_match = is_started and not is_completed
                    elif self.current_filter == 'completed':
                        status_match = is_completed
                
                # 2. Check Text Search
                text_match = True
                if search_text:
                    data = child.data(0, Qt.ItemDataRole.UserRole + 2)
                    text_match = False
                    if data:
                        # author, title, narrator, file_count, duration, listened_duration, progress_percent, codec, b_min, b_max, b_mode, container
                        author, title, narrator = data[0:3]
                        codec, b_min, b_max, b_mode, container = data[7:12]
                        
                        if author and search_text in author.lower():
                            text_match = True
                        if title and search_text in title.lower():
                            text_match = True
                        if narrator and search_text in narrator.lower():
                            text_match = True
                        if codec and search_text in codec.lower():
                            text_match = True
                        if container and search_text in container.lower():
                            text_match = True
                        if b_mode and search_text in b_mode.lower():
                            text_match = True
                        
                        # Tag Search
                        tags = child.data(0, Qt.ItemDataRole.UserRole + 4)
                        if tags and isinstance(tags, list):
                            for tag in tags:
                                if isinstance(tag, dict) and 'name' in tag:
                                    if search_text in tag['name'].lower():
                                        text_match = True
                                        break
                                    
                        # Bitrate search
                        search_min = b_min // 1000 if b_min > 5000 else b_min
                        search_max = b_max // 1000 if b_max > 5000 else b_max
                        
                        if search_min and search_text in str(search_min):
                            text_match = True
                        if search_max and search_text in str(search_max):
                            text_match = True
                
                child.setHidden(not (status_match and text_match))
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
        """Construct and display a context menu for items in the library tree"""
        item = self.tree.itemAt(pos)
        if not item:
            return
            
        role = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        
        if role == 'audiobook':
            # Audiobook context menu (existing logic)
            info = self.db.get_audiobook_info(path)
            if not info:
                return
            audiobook_id = info[0]
            
            # Fetch fresh favorite status
            is_favorite = False
            status_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
            if status_data and len(status_data) >= 3:
                is_favorite = status_data[2]
            
            duration = item.data(0, Qt.ItemDataRole.UserRole + 2)[4]

            menu = QMenu()
            play_action = QAction(tr("library.context_play"), self)
            play_action.setIcon(get_icon("context_play"))
            play_action.triggered.connect(lambda _: self.on_item_double_clicked(item, 0))
            menu.addAction(play_action)
            
            # Favorites Action
            fav_text = tr("library.menu_remove_favorite") if is_favorite else tr("library.menu_add_favorite")
            fav_icon = get_icon("context_favorite_on" if is_favorite else "context_favorite_off")
            
            # Fallback icons if resource not present
            if not fav_icon or fav_icon.isNull():
                 fav_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
            
            fav_action = QAction(fav_text, self)
            fav_action.setIcon(fav_icon)
            fav_action.triggered.connect(lambda _: self.toggle_favorite(audiobook_id, path))
            menu.addAction(fav_action)
            
            # Tags Submenu
            menu.addSeparator()
            tags_menu = menu.addMenu(tr("tags.menu_title"))
            tags_menu.setIcon(get_icon("context_tags")) # Ensure icon exists or fallback logic if needed
            
            # Populate with existing tags
            all_tags = self.db.get_all_tags()
            current_tags = self.db.get_tags_for_audiobook(audiobook_id)
            current_tag_ids = {t['id'] for t in current_tags}
            
            if all_tags:
                for tag in all_tags:
                    # Create checkable action for each tag
                    tag_action = QAction(tag['name'], self)
                    tag_action.setCheckable(True)
                    tag_action.setChecked(tag['id'] in current_tag_ids)
                    
                    # Set color icon if available
                    if tag.get('color'):
                        pixmap = QPixmap(14, 14)
                        pixmap.fill(QColor(tag['color']))
                        tag_action.setIcon(QIcon(pixmap))
                    
                    # Connect signal
                    tag_action.triggered.connect(
                        lambda checked, tid=tag['id'], p=path: 
                        self.toggle_tag_from_context_menu(audiobook_id, tid, p, checked)
                    )
                    tags_menu.addAction(tag_action)
                
                tags_menu.addSeparator()
            
            assign_action = QAction(tr("tags.menu_assign"), self)
            assign_action.triggered.connect(lambda _: self.open_tag_assignment(audiobook_id, path))
            tags_menu.addAction(assign_action)
            
            menu.addSeparator()

            edit_metadata_action = QAction(tr("library.menu_edit_metadata"), self)
            edit_metadata_action.setIcon(get_icon("context_edit_metadata"))
            edit_metadata_action.triggered.connect(lambda _: self.open_metadata_editor(audiobook_id, path))
            menu.addAction(edit_metadata_action)
            
            menu.addSeparator()

            mark_read_action = QAction(tr("library.menu_mark_read"), self)
            mark_read_action.setIcon(get_icon("context_mark_read"))
            mark_read_action.triggered.connect(lambda _: self.mark_as_read(audiobook_id, duration, path))
            menu.addAction(mark_read_action)

            mark_unread_action = QAction(tr("library.menu_mark_unread"), self)
            mark_unread_action.setIcon(get_icon("context_mark_unread"))
            mark_unread_action.triggered.connect(lambda _: self.mark_as_unread(audiobook_id, path))
            menu.addAction(mark_unread_action)
            
            menu.addSeparator()
            
            open_folder_action = QAction(tr("library.menu_open_folder"), self)
            open_folder_action.setIcon(get_icon("context_open_folder"))
            open_folder_action.triggered.connect(lambda _: self.open_folder(path))
            menu.addAction(open_folder_action)
            
            menu.addSeparator()
            
            delete_action = QAction(tr("library.menu_delete"), self)
            delete_action.setIcon(get_icon("delete"))
            delete_action.triggered.connect(lambda _: self.confirm_delete(audiobook_id, path))
            menu.addAction(delete_action)
            
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            
        elif role == 'folder':
            # Folder context menu
            menu = QMenu()
            
            open_folder_action = QAction(tr("library.menu_open_folder"), self)
            open_folder_action.setIcon(get_icon("context_open_folder"))
            open_folder_action.triggered.connect(lambda _: self.open_folder(path))
            menu.addAction(open_folder_action)
            
            menu.addSeparator()
            
            delete_action = QAction(tr("library.menu_delete_folder"), self)
            delete_action.setIcon(get_icon("delete"))
            delete_action.triggered.connect(lambda _: self.confirm_delete_folder(path))
            menu.addAction(delete_action)

            menu.addSeparator()

            merge_action = QAction(tr("library.menu_merge_folders"), self)
            merge_action.setIcon(get_icon("merge"))
            merge_action.triggered.connect(lambda _: self.on_merge_folders_requested(path))
            menu.addAction(merge_action)
            
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def mark_as_read(self, audiobook_id, duration, path):
        self.db.mark_audiobook_completed(audiobook_id, duration)
        self.update_cache_item_status(path, is_started=True, is_completed=True)
        item = self.find_item_by_path(self.tree.invisibleRootItem(), path)
        if item:
            # Preserve existing favorite status
            current_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
            is_favorite = False
            if current_data and len(current_data) >= 3:
                is_favorite = current_data[2]
            
            item.setData(0, Qt.ItemDataRole.UserRole + 3, (True, True, is_favorite))
            self.refresh_audiobook_item(path)
        self.filter_audiobooks()
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            window.update_ui_for_audiobook()

    def mark_as_unread(self, audiobook_id, path):
        self.db.reset_audiobook_status(audiobook_id)
        self.update_cache_item_status(path, is_started=False, is_completed=False)
        item = self.find_item_by_path(self.tree.invisibleRootItem(), path)
        if item:
            # Preserve existing favorite status
            current_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
            is_favorite = False
            if current_data and len(current_data) >= 3:
                is_favorite = current_data[2]
                
            item.setData(0, Qt.ItemDataRole.UserRole + 3, (False, False, is_favorite))
            self.refresh_audiobook_item(path)
        self.filter_audiobooks()
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            window.playback_controller.saved_file_index = 0
            window.playback_controller.saved_position = 0
            window.update_ui_for_audiobook()
    
    def toggle_favorite(self, audiobook_id: int, path: str):
        """Toggle favorite status and refresh item"""
        new_state = self.db.toggle_favorite(audiobook_id)
        self.refresh_audiobook_item(path)
        
        # If we are in Favorites view and we removed it, reload to hide it
        if self.current_filter == 'favorites' and not new_state:
            self.load_audiobooks(use_cache=False)
            
    def open_tag_assignment(self, audiobook_id, path):
        """Open dialog to assign tags to audiobook"""
        # Unified dialog handling both assignment and management
        dialog = TagManagerDialog(self.db, self, audiobook_id)
        if dialog.exec():
            # Refresh this item to show new tags
            self.refresh_audiobook_item(path)
            
    def toggle_tag_from_context_menu(self, audiobook_id: int, tag_id: int, path: str, checked: bool):
        """Handle toggling a tag directly from the context menu"""
        if checked:
            self.db.add_tag_to_audiobook(audiobook_id, tag_id)
        else:
            self.db.remove_tag_from_audiobook(audiobook_id, tag_id)
        
        # Refresh the UI for this item
        self.refresh_audiobook_item(path)
            


    def open_metadata_editor(self, audiobook_id: int, path: str):
        """Open dialog to edit audiobook metadata (author, title, narrator)"""
        dialog = MetadataEditDialog(self.db, audiobook_id, self)
        if dialog.exec():
            # Get updated data
            author, title, narrator = dialog.get_data()
            
            # Update database
            self.db.update_audiobook_metadata(audiobook_id, author, title, narrator)
            
            # Refresh UI item
            self.refresh_audiobook_item(path)
            
            # If currently filtered by text, re-apply filter in case metadata changed visibility
            if self.search_edit.text():
                self.filter_audiobooks()

    def confirm_delete(self, audiobook_id: int, path: str):
        """Ask for user confirmation before proceeding with book deletion"""
        display_path = os.path.basename(path)
        reply = QMessageBox.question(
            self, 
            tr("library.confirm_delete_title"),
            trf("library.confirm_delete_msg", path=display_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(audiobook_id, path)

    def remove_audiobook_from_ui(self, path: str):
        """Cleanly remove an audiobook from the library tree and internal cache"""
        # 1. Synchronize the in-memory cache
        if self.cached_library_data:
            found = False
            for parent, items in self.cached_library_data.items():
                for i, item in enumerate(items):
                    if item['path'] == path:
                        items.pop(i)
                        found = True
                        break
                if found:
                    break
        
        # 2. Update the visual tree representation
        item = self.find_item_by_path(self.tree.invisibleRootItem(), path)
        if item:
            parent = item.parent() or self.tree.invisibleRootItem()
            parent.removeChild(item)
            
        # 3. Refresh status metrics in the main window
        window = self.window()
        if hasattr(window, 'statusBar'):
            total_count = self.db.get_audiobook_count()
            window.statusBar().showMessage(trf("status.library_count", count=total_count))
    
    def confirm_delete_folder(self, path: str):
        """Ask for user confirmation before proceeding with folder removal"""
        display_path = os.path.basename(path)
        
        # Fetch nested items to warn the user about what else will be removed from the library
        contents = self.db.get_folder_contents(path)
        items_str = ""
        if contents:
            items_list = []
            # Limit display to first 15 items to keep the dialog readable
            for name, is_folder in contents[:15]:
                items_list.append(f"  {name}")
            
            if len(contents) > 15:
                items_list.append(f"  ... ({len(contents) - 15} more)")
            
            header = tr("library.delete_folder_contents_header")
            items_str = f"\n\n{header}\n" + "\n".join(items_list)
            
        reply = QMessageBox.question(
            self, 
            tr("library.confirm_delete_folder_title"),
            trf("library.confirm_delete_folder_msg", path=display_path, items=items_str),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.folder_delete_requested.emit(path)

    def on_merge_folders_requested(self, path: str):
        """Handle request to merge folders"""
        reply = QMessageBox.question(
            self,
            tr("library.merge_confirm_title"),
            tr("library.merge_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.perform_virtual_merge(path)

    def perform_virtual_merge(self, path: str):
        """Mark folder as merged in DB and trigger rescan"""
        try:
            self.db.set_folder_merged(path, True)
            # Trigger a rescan to update the library structure
            self.scan_requested.emit()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("window.title"),
                f"Error merging folders: {str(e)}"
            )

    def remove_folder_from_ui(self, path: str):
        """Recursively remove a folder and all its contents from the tree and internal cache"""
        # 1. Purge from in-memory cache
        if self.cached_library_data:
            # Remove the folder itself
            for parent, items in list(self.cached_library_data.items()):
                if parent == path:
                    del self.cached_library_data[parent]
                else:
                    self.cached_library_data[parent] = [
                        item for item in items if item['path'] != path
                    ]
            
            # Recursive removal of nested paths from cache
            prefix = path + os.sep
            for parent in list(self.cached_library_data.keys()):
                if parent.startswith(prefix):
                    del self.cached_library_data[parent]
                else:
                    self.cached_library_data[parent] = [
                        item for item in self.cached_library_data[parent] 
                        if not item['path'].startswith(prefix)
                    ]

        # 2. Prune the visual tree
        item = self.find_item_by_path(self.tree.invisibleRootItem(), path)
        if item:
            parent = item.parent() or self.tree.invisibleRootItem()
            parent.removeChild(item)
            
        # 3. Synchronize status metrics
        window = self.window()
        if hasattr(window, 'statusBar'):
            total_count = self.db.get_audiobook_count()
            window.statusBar().showMessage(trf("status.library_count", count=total_count))
    
    def open_folder(self, path: str):
        if not path:
            return
        try:
            default_path = self.config.get('default_path', '')
            print(f"DEBUG: Opening folder. Config default_path: {default_path}")
            
            if default_path:
                abs_path = Path(default_path) / path
            else:
                abs_path = Path(path)
                
            print(f"DEBUG: Target path: {abs_path}")
            if abs_path.exists() and abs_path.is_file():
                folder_path = abs_path.parent
            else:
                folder_path = abs_path
            if folder_path.exists():
                folder_path_str = str(folder_path.absolute())
                if sys.platform == 'win32':
                    import ctypes
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
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'audiobook':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            self.audiobook_selected.emit(path)
    
    def highlight_audiobook(self, audiobook_path: str):
        if self.current_playing_item:
            try:
                self.current_playing_item.text(0)
                self.reset_item_colors(self.current_playing_item)
            except RuntimeError:
                self.current_playing_item = None
        
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
            self.current_playing_item = item
            item.setBackground(0, QBrush(self.highlight_color))
            item.setForeground(0, QBrush(self.highlight_text_color))
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            self.tree.scrollToItem(item)

    def find_item_by_path(self, parent_item, path: str):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                return child
            result = self.find_item_by_path(child, path)
            if result:
                return result
        return None
    
    def reset_item_colors(self, item):
        try:
            item.setBackground(0, QBrush(Qt.GlobalColor.transparent))
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)
        except RuntimeError:
            pass

    def refresh_audiobook_item(self, audiobook_path: str):
        # If we are in "In Progress" mode, a metadata update (like track change)
        # implies a timestamp update, which affects sorting order.
        # We must reload the list to ensure the active book/folder jumps to the top.
        if self.current_filter == 'in_progress':
            self.load_audiobooks(use_cache=False)
            return

        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
        data = self.db.get_audiobook_by_path(audiobook_path)
        if data:
            item.setData(0, Qt.ItemDataRole.UserRole + 2, (
                data['author'],
                data['title'],
                data['narrator'],
                data['file_count'],
                data['duration'],
                data['listened_duration'],
                data['progress_percent'],
                data['codec'],
                data['bitrate_min'],
                data['bitrate_max'],
                data['bitrate_mode'],
                data['container'],
                data.get('description', '')
            ))
            if 'is_started' in data and 'is_completed' in data:
                item.setData(0, Qt.ItemDataRole.UserRole + 3, (
                    data['is_started'],
                    data['is_completed'],
                    data['is_favorite']
                ))
            
            # Refresh tags
            info = self.db.get_audiobook_info(audiobook_path)
            if info:
                tags = self.db.get_tags_for_audiobook(info[0])
                item.setData(0, Qt.ItemDataRole.UserRole + 4, tags)
            
            item.setText(0, item.text(0))
            self.update_cache_item_status(audiobook_path, data['is_started'], data['is_completed'])
            self.tree.viewport().update()

    def update_item_progress(self, audiobook_path: str, listened_duration: float, progress_percent: int):
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if data and len(data) >= 7:
            new_data = list(data)
            new_data[5] = listened_duration
            new_data[6] = progress_percent
            item.setData(0, Qt.ItemDataRole.UserRole + 2, tuple(new_data))
            self.tree.viewport().update()
    
    def update_cache_item_status(self, path: str, is_started: bool, is_completed: bool):
        if not self.cached_library_data:
            return
        found = False
        for parent, items in self.cached_library_data.items():
            for item in items:
                if item['path'] == path:
                    item['is_started'] = is_started
                    item['is_completed'] = is_completed
                    # is_favorite is not cached here for now, as it requires a DB reload for full consistency
                    # but we could add it if needed.
                    found = True
                    break
            if found:
                break
    
    def update_texts(self):
        if hasattr(self, 'btn_show_folders'):
            self.btn_show_folders.setToolTip(tr("library.tooltip_show_folders"))
        self.update_filter_labels()
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                self.filter_buttons[filter_id].setToolTip(tr(f"library.tooltip_filter_{filter_id}"))
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))
