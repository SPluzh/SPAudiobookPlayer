from pathlib import Path

# Path to the dark theme stylesheet
DARK_QSS_PATH = Path(__file__).parent / "resources" / "styles" / "dark.qss"

# Initial load of the dark style
try:
    DARK_STYLE = DARK_QSS_PATH.read_text(encoding="utf-8")
except Exception:
    DARK_STYLE = ""  # Fallback to empty style if file is missing

class StyleManager:
    """Manager for application-wide visual styles and themes"""
    
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
