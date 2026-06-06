import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QApplication,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QFont
from translations import tr, trf
from utils import get_base_path


class AboutDialog(QDialog):
    """Custom themed About Dialog for the application"""

    def __init__(self, parent=None):
        """Initialize the frameless about dialog"""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        try:
            self.setup_ui()
        except Exception as e:
            import traceback

            traceback.print_exc()

    def showEvent(self, event):
        """Ensure window is centered and sized correctly on show"""
        try:
            self.adjustSize()
            self.center_window()
        except Exception as e:
            pass
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

        # Container frame
        self.container = QFrame()
        self.container.setObjectName("aboutContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)

        # Title with version
        version_text = self.get_app_version()
        title = QLabel(f"{tr('window.title')} {version_text}")
        title.setObjectName("aboutTitle")
        container_layout.addWidget(title)

        # GitHub and Feedback Links Layout
        links_layout = QHBoxLayout()
        links_layout.setContentsMargins(0, 0, 0, 0)
        links_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # GitHub Link Group
        github_link_group = QHBoxLayout()
        github_link_group.setSpacing(5)

        # Icon Label
        github_icon_label = QLabel()
        github_icon_path = str(get_base_path() / "resources" / "icons" / "github.png")
        github_icon_label.setPixmap(QIcon(github_icon_path).pixmap(16, 16))
        github_link_group.addWidget(github_icon_label)

        # Text Label
        github_text_label = QLabel(tr("about.github", "GitHub"))
        github_text_label.setObjectName("aboutGithubLink")
        github_text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        github_text_label.mousePressEvent = lambda e: self.open_github()
        github_link_group.addWidget(github_text_label)

        links_layout.addLayout(github_link_group)

        links_layout.addSpacing(15)

        # Feedback Link Group
        feedback_link_group = QHBoxLayout()
        feedback_link_group.setSpacing(5)

        # Icon Label
        feedback_icon_label = QLabel()
        feedback_icon_label.setPixmap(QIcon(github_icon_path).pixmap(16, 16))
        feedback_link_group.addWidget(feedback_icon_label)

        # Text Label
        feedback_text_label = QLabel(tr("about.feedback", "Feedback, Suggestions & Bugs"))
        feedback_text_label.setObjectName("aboutGithubLink")
        feedback_text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        feedback_text_label.mousePressEvent = lambda e: self.open_feedback()
        feedback_link_group.addWidget(feedback_text_label)

        links_layout.addLayout(feedback_link_group)
        container_layout.addLayout(links_layout)

        # Separator
        line = QFrame()
        line.setObjectName("aboutLine")
        line.setFrameShape(QFrame.Shape.HLine)
        container_layout.addWidget(line)

        # Description
        desc = QLabel(tr("about.description"))
        desc.setObjectName("aboutDesc")
        desc.setWordWrap(True)
        container_layout.addWidget(desc)

        # Columns layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(30)
        columns_layout.setContentsMargins(0, 0, 0, 0)

        # Left Column: Supported Formats & Hotkeys
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        left_column.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Supported Formats
        formats_title = QLabel(tr("about.supported_formats"))
        formats_title.setObjectName("aboutSectionTitle")
        left_column.addWidget(formats_title)

        formats_content = QLabel(tr("about.formats_list"))
        formats_content.setObjectName("aboutSectionContent")
        formats_content.setWordWrap(True)
        left_column.addWidget(formats_content)

        left_column.addSpacing(15)

        # Supported Cover Formats
        covers_title = QLabel(tr("about.supported_covers_title"))
        covers_title.setObjectName("aboutSectionTitle")
        left_column.addWidget(covers_title)

        covers_content = QLabel(tr("about.covers_list"))
        covers_content.setObjectName("aboutSectionContent")
        covers_content.setWordWrap(True)
        left_column.addWidget(covers_content)

        left_column.addSpacing(15)

        # Hotkeys
        hotkeys_title = QLabel(tr("about.hotkeys_title", "Hotkeys:"))
        hotkeys_title.setObjectName("aboutSectionTitle")
        left_column.addWidget(hotkeys_title)

        hotkeys_content = QLabel(
            tr(
                "about.hotkeys_list",
                "Space — Play / Pause\n[ and ] — Previous / Next File\nLeft / Right — Rewind / Forward 10s\nShift + Left / Right — Rewind / Forward 60s\nUp / Down — Playback Speed (±0.1x)\nShift + Up / Down — Volume (±5%)",
            )
        )
        hotkeys_content.setObjectName("aboutSectionContent")
        hotkeys_content.setWordWrap(True)
        left_column.addWidget(hotkeys_content)

        left_column.addSpacing(15)

        # Global Hotkeys
        global_hotkeys_title = QLabel(tr("about.global_hotkeys_title", "Global Media Keys (in background):"))
        global_hotkeys_title.setObjectName("aboutSectionTitle")
        left_column.addWidget(global_hotkeys_title)

        global_hotkeys_content = QLabel(
            tr(
                "about.global_hotkeys_list",
                "Play/Pause — Play / Pause\nStop — Pause\nNext Track — Forward 10s\nPrev Track — Rewind 10s",
            )
        )
        global_hotkeys_content.setObjectName("aboutSectionContent")
        global_hotkeys_content.setWordWrap(True)
        left_column.addWidget(global_hotkeys_content)

        # Right Column: Recommended Library Structure
        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        right_column.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Library Hierarchy
        hierarchy_title = QLabel(tr("about.library_hierarchy_title"))
        hierarchy_title.setObjectName("aboutSectionTitle")
        right_column.addWidget(hierarchy_title)

        hierarchy_text = tr("about.library_hierarchy_text")
        hierarchy_html = hierarchy_text.replace(" ", "&nbsp;").replace("\n", "<br>")
        hierarchy_content = QLabel(hierarchy_html)
        hierarchy_content.setObjectName("aboutRightContent")
        hierarchy_content.setTextFormat(Qt.TextFormat.RichText)
        hierarchy_content.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_column.addWidget(hierarchy_content)

        # Add columns to the main columns layout
        columns_layout.addLayout(left_column, 1)
        columns_layout.addLayout(right_column, 1)

        container_layout.addLayout(columns_layout)

        container_layout.addSpacing(15)

        # Close Button
        close_btn = QPushButton(tr("about.close"))
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def open_github(self):
        """Open project GitHub repository in default browser"""
        QDesktopServices.openUrl(QUrl("https://github.com/SPluzh/SPAudiobookPlayer"))

    def open_feedback(self):
        """Open project feedback and issues page in default browser"""
        QDesktopServices.openUrl(QUrl("https://github.com/SPluzh/SPAudiobookPlayer/issues"))
