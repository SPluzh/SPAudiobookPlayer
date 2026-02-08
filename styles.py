from pathlib import Path
from functools import lru_cache
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

# Path to the dark theme stylesheet
DARK_QSS_PATH = Path(__file__).parent / "resources" / "styles" / "dark.qss"

# Initial load of the dark style
try:
    DARK_STYLE = DARK_QSS_PATH.read_text(encoding="utf-8")
except Exception:
    DARK_STYLE = ""  # Fallback to empty style if file is missing

class StyleManager:
    """Manager for application-wide visual styles and themes"""
    
    _proxy_widgets = {}
    _property_cache = {}
    _monitored_objects = [
        'delegate_author', 'delegate_title', 'delegate_narrator', 
        'delegate_info', 'delegate_folder', 'delegate_progress', 
        'delegate_duration', 'delegate_file_count', 'delegate_favorite',
        'delegate_accent', 'delegate_accent_secondary', 'delegate_text_dim',
        'delegate_info_font', 'delegate_regular_font', 'theme_primary',
        'overlay_background', 'overlay_progress_bg', 'separator_dot'
    ]

    @staticmethod
    def init(app):
        """Initialize proxy widgets and pre-cache theme properties"""
        for obj_name in StyleManager._monitored_objects:
            if obj_name not in StyleManager._proxy_widgets:
                label = QLabel()
                label.setObjectName(obj_name)
                # Setting a parent isn't strictly necessary but can help with lifecycle 
                # if we were to link it to a hidden window. For now, we keep them alive in the dict.
                StyleManager._proxy_widgets[obj_name] = label
        
        # Initial property extraction
        StyleManager.refresh_cache()

    @staticmethod
    def refresh_cache():
        """Force re-extraction of all monitored theme properties"""
        for obj_name, label in StyleManager._proxy_widgets.items():
            label.ensurePolished()
            font = label.font()
            color = label.palette().color(label.foregroundRole())
            StyleManager._property_cache[obj_name] = (font, color)

    @staticmethod
    def get_style(path: Path = DARK_QSS_PATH) -> str:
        """Read stylesheet content from the specified file path"""
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def apply_style(app, path: Path = DARK_QSS_PATH):
        """Apply the specified stylesheet to the entire application"""
        qss = StyleManager.get_style(path)
        if qss:
            app.setStyleSheet(qss)

    @staticmethod
    def get_theme_property(object_name: str) -> tuple[QFont, QColor]:
        """
        Fetch font and color for a specific object name.
        Uses cached values if available, otherwise attempts a safe extraction.
        """
        if object_name in StyleManager._property_cache:
            return StyleManager._property_cache[object_name]
            
        print(f"DEBUG: StyleManager extracting property for '{object_name}' (NOT IN CACHE)")
        
        # Fallback for unexpected object names (creates widget only if necessary)
        if object_name not in StyleManager._proxy_widgets:
            print(f"DEBUG: StyleManager creating unexpected proxy for '{object_name}'")
            label = QLabel()
            label.setObjectName(object_name)
            StyleManager._proxy_widgets[object_name] = label
        
        label = StyleManager._proxy_widgets[object_name]
        label.ensurePolished()
        
        font = label.font()
        color = label.palette().color(label.foregroundRole())
        
        # Cache it for future use
        StyleManager._property_cache[object_name] = (font, color)
        return font, color
