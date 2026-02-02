import sys
import io
from pathlib import Path
from functools import lru_cache
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from translations import tr, trf

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

@lru_cache(maxsize=512)
def load_icon(file_path: Path, target_size: int, force_square: bool = False) -> QIcon:
    """Load, scale and return a QIcon from a file path"""
    if file_path.exists() and file_path.is_file():
        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            size_px = int(target_size * 1.5)
            
            # 1. Scale original image once (Foreground)
            fg = pixmap.scaled(size_px, size_px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            if force_square and (fg.width() < size_px or fg.height() < size_px):
                # Create a square canvas
                result = QPixmap(size_px, size_px)
                result.fill(Qt.GlobalColor.black)
                
                painter = QPainter(result)
                try:
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    
                    # Logic to fill gaps by stretching edges
                    blur_factor = 0.05 # Strong blur for the background
                    
                    if fg.height() < size_px: # Landscape
                        y_offset = (size_px - fg.height()) // 2
                        
                        # Top
                        if y_offset > 0:
                            top_strip = fg.copy(0, 0, fg.width(), 1)
                            top_bg = top_strip.scaled(size_px, y_offset, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            # Blur
                            small = top_bg.scaled(int(size_px * blur_factor), int(y_offset * blur_factor) or 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            blurred = small.scaled(size_px, y_offset, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            painter.drawPixmap(0, 0, blurred)
                        
                        # Bottom
                        if size_px - (y_offset + fg.height()) > 0:
                            bot_h = size_px - (y_offset + fg.height())
                            bot_strip = fg.copy(0, fg.height()-1, fg.width(), 1)
                            bot_bg = bot_strip.scaled(size_px, bot_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            # Blur
                            small = bot_bg.scaled(int(size_px * blur_factor), int(bot_h * blur_factor) or 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            blurred = small.scaled(size_px, bot_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            painter.drawPixmap(0, y_offset + fg.height(), blurred)
                        
                    elif fg.width() < size_px: # Portrait
                        x_offset = (size_px - fg.width()) // 2
                        
                        # Left
                        if x_offset > 0:
                            left_strip = fg.copy(0, 0, 1, fg.height())
                            left_bg = left_strip.scaled(x_offset, size_px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            # Blur
                            small = left_bg.scaled(int(x_offset * blur_factor) or 1, int(size_px * blur_factor), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            blurred = small.scaled(x_offset, size_px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            painter.drawPixmap(0, 0, blurred)
                        
                        # Right
                        if size_px - (x_offset + fg.width()) > 0:
                            right_w = size_px - (x_offset + fg.width())
                            right_strip = fg.copy(fg.width()-1, 0, 1, fg.height())
                            right_bg = right_strip.scaled(right_w, size_px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            # Blur
                            small = right_bg.scaled(int(right_w * blur_factor) or 1, int(size_px * blur_factor), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            blurred = small.scaled(right_w, size_px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            painter.drawPixmap(x_offset + fg.width(), 0, blurred)
                        
                    # 2. Draw original image in center
                    x = (size_px - fg.width()) // 2
                    y = (size_px - fg.height()) // 2
                    painter.drawPixmap(x, y, fg)
                finally:
                    painter.end()
                
                pixmap = result
            else:
                 pixmap = fg
            
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    return None

def resize_icon(icon: QIcon, size: int) -> QIcon:
    """Resize an existing QIcon to the specified size"""
    return QIcon(icon.pixmap(QSize(size, size)))

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
