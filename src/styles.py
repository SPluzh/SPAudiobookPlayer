import re
from pathlib import Path
from functools import lru_cache
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

# Theme paths
STYLES_DIR = Path(__file__).parent / "resources" / "styles"
STYLE_QSS_PATH = STYLES_DIR / "style.qss"

# Fallback styles
try:
    STYLE_CONTENT = STYLE_QSS_PATH.read_text(encoding="utf-8")
except Exception:
    STYLE_CONTENT = ""

# Backwards compatibility aliases
DARK_QSS_PATH = STYLE_QSS_PATH
DARK_STYLE = STYLE_CONTENT

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
        'overlay_background', 'overlay_progress_bg', 'separator_dot',
        'placeholder_title', 'placeholder_text', 'placeholder_icon',
        'delegate_status_new', 'delegate_status_started', 'delegate_status_completed',
        'tile_background', 'popup_background', 'popup_border'
    ]

    @staticmethod
    def _process_qss(qss: str, overrides: dict = None) -> str:
        """
        Process QSS variables defined at the top of the file.
        Syntax: /* @var_name: #value */
        """
        # Find all variable definitions in comments
        # Pattern: /* @name: value */
        var_pattern = re.compile(r'/\*\s*@([\w-]+):\s*([^;*]+?)\s*\*/')
        vars = dict(var_pattern.findall(qss))
        
        if overrides:
            # If overrides has "accent", let's automatically generate "accent-dark" and "accent-light"
            # if they are not explicitly in overrides, based on the overridden "accent"
            overrides = dict(overrides)
            if "accent" in overrides and overrides["accent"]:
                acc_color = QColor(overrides["accent"])
                if acc_color.isValid():
                    if "accent-dark" not in overrides:
                        overrides["accent-dark"] = acc_color.darker(130).name()
                    if "accent-light" not in overrides:
                        overrides["accent-light"] = acc_color.lighter(130).name()
            
            # Dynamically compute harmonized background shades when bg-main is overridden
            if "bg-main" in overrides and overrides["bg-main"]:
                bg_color = QColor(overrides["bg-main"])
                if bg_color.isValid():
                    if "bg-dark" not in overrides or not overrides["bg-dark"]:
                        overrides["bg-dark"] = bg_color.darker(120).name()
                    if "bg-hover" not in overrides:
                        overrides["bg-hover"] = bg_color.lighter(110).name()
                    if "bg-focus" not in overrides:
                        overrides["bg-focus"] = bg_color.darker(105).name()
                    if "bg-disabled" not in overrides:
                        overrides["bg-disabled"] = bg_color.darker(140).name()
                    if "bg-tabbar" not in overrides:
                        overrides["bg-tabbar"] = bg_color.darker(150).name()
                    if "bg-black" not in overrides:
                        overrides["bg-black"] = bg_color.darker(220).name()
            
            # Dynamically compute harmonized text shades when text is overridden
            if "text" in overrides and overrides["text"]:
                text_color = QColor(overrides["text"])
                if text_color.isValid():
                    bg_color_str = overrides.get("bg-main") or vars.get("bg-main") or "#444444"
                    bg_color = QColor(bg_color_str)
                    if bg_color.isValid():
                        is_light = text_color.lightness() > bg_color.lightness()
                        
                        def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
                            r = int(c1.red() * (1 - t) + c2.red() * t)
                            g = int(c1.green() * (1 - t) + c2.green() * t)
                            b = int(c1.blue() * (1 - t) + c2.blue() * t)
                            return QColor(r, g, b)
                        
                        if "text-bright" not in overrides:
                            target = QColor("#ffffff") if is_light else QColor("#000000")
                            overrides["text-bright"] = lerp_color(text_color, target, 0.5).name()
                        if "text-dim" not in overrides:
                            overrides["text-dim"] = lerp_color(text_color, bg_color, 0.45).name()
                        if "text-muted" not in overrides:
                            overrides["text-muted"] = lerp_color(text_color, bg_color, 0.6).name()
                        if "text-disabled" not in overrides:
                            overrides["text-disabled"] = lerp_color(text_color, bg_color, 0.75).name()
                        if "text-delegate" not in overrides:
                            overrides["text-delegate"] = lerp_color(text_color, bg_color, 0.15).name()
            
            vars.update(overrides)
            
        if not vars:
            return qss
            
        processed_qss = qss
        # Replace occurrences of @name with value
        # Sort by length descending to avoid partial replacements (e.g. @bg vs @bg-dark)
        for name in sorted(vars.keys(), key=len, reverse=True):
            value = vars[name].strip()
            processed_qss = processed_qss.replace(f'@{name}', value)
            
        return processed_qss

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
    def get_theme_path(theme_name: str) -> Path:
        """Get the file path for a given theme name"""
        return STYLE_QSS_PATH

    @staticmethod
    def get_style(path: Path, overrides: dict = None) -> str:
        """Read stylesheet content from the specified file path and process variables"""
        if path.exists():
            content = path.read_text(encoding="utf-8")
            return StyleManager._process_qss(content, overrides)
        return ""

    @staticmethod
    def apply_style(app, theme: str = "dark", overrides: dict = None):
        """Apply the specified stylesheet to the entire application"""
        path = StyleManager.get_theme_path(theme)
        qss = StyleManager.get_style(path, overrides)
        if qss:
            app.setStyleSheet(qss)

    @staticmethod
    def get_default_vars(theme: str = "dark") -> dict:
        """Parse default variable values from QSS comments without applying style."""
        path = StyleManager.get_theme_path(theme)
        if not path.exists():
            return {}
        content = path.read_text(encoding="utf-8")
        var_pattern = re.compile(r'/\*\s*@([\w-]+):\s*([^;*]+?)\s*\*/')
        return {k: v.strip() for k, v in var_pattern.findall(content)}

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

