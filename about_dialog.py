import sys
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFrame, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt
from translations import tr, trf
from utils import get_base_path

class AboutDialog(QDialog):
    """Custom themed About Dialog for the application"""
    def __init__(self, parent=None):
        """Initialize the frameless about dialog"""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def showEvent(self, event):
        """Ensure window is centered and sized correctly on show"""
        self.adjustSize()
        self.center_window()
        super().showEvent(event)

    def get_app_version(self):
        """Load application version from version.txt"""
        try:
            version_file = get_base_path() / "resources" / "version.txt"
            if version_file.exists():
                return version_file.read_text("utf-8").strip()
        except Exception:
            pass
        return "1.0.0"

    def setup_ui(self):
        """Build the about dialog interface"""
        # Main layout with dark background
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame
        self.container = QFrame()
        self.container.setObjectName("aboutContainer")
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(30, 40, 30, 30)
        container_layout.setSpacing(15)
        
        # Title
        title = QLabel(tr('window.title'))
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)
        
        # Version
        version_text = self.get_app_version()
        version = QLabel(trf('about.version', version=version_text))
        version.setObjectName("aboutVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(version)
        
        # Separator
        line = QFrame()
        line.setObjectName("aboutLine")
        line.setFrameShape(QFrame.Shape.HLine)
        container_layout.addWidget(line)
        
        # Description
        desc = QLabel(tr('about.description'))
        desc.setObjectName("aboutDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        container_layout.addWidget(desc)
        
        container_layout.addSpacing(10)
        
        # Close Button
        close_btn = QPushButton(tr('about.close'))
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        container_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.container)

    def center_window(self):
        """Center the dialog relative to its parent or screen"""
        if self.parent():
            parent_geo = self.parent().frameGeometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(parent_geo.center())
            self.move(self_geo.topLeft())
        else:
            # Center on primary screen if no parent
            screen = QApplication.primaryScreen().geometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(screen.center())
            self.move(self_geo.topLeft())
