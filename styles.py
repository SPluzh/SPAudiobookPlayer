from pathlib import Path

# Пусть путь к файлу dark.qss
DARK_QSS_PATH = Path(__file__).parent / "resources" / "styles" / "dark.qss"

# ==========================
# DARK_STYLE (для совместимости)
# ==========================
try:
    DARK_STYLE = DARK_QSS_PATH.read_text(encoding="utf-8")
except Exception:
    DARK_STYLE = ""  # Если файла нет, пустой стиль

# ==========================
# Менеджер стилей
# ==========================
class StyleManager:
    """Менеджер стилей приложения"""
    
    @staticmethod
    def get_style(path: Path = DARK_QSS_PATH) -> str:
        """Читает стиль из файла"""
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def apply_style(app, path: Path = DARK_QSS_PATH):
        """Применяет стиль к приложению"""
        qss = StyleManager.get_style(path)
        if qss:
            app.setStyleSheet(qss)
