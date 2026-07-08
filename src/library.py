import sys
import os
import subprocess
import configparser
import shutil
import zlib
from functools import lru_cache
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QProgressBar,
    QLabel,
    QLineEdit,
    QMenu,
    QStyle,
    QButtonGroup,
    QDialog,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QStyledItemDelegate,
    QToolTip,
    QListWidget,
    QListWidgetItem,
    QStyleOptionViewItem,
    QFrame,
    QCheckBox,
    QApplication,
    QScrollArea,
    QStackedWidget,
    QLayout,
    QStyleOption,
    QSizePolicy,
)
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QSize,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    QThread,
    QEvent,
    QTimer,
    QUrl,
    QModelIndex,
)
from PyQt6.QtGui import (
    QIcon,
    QAction,
    QPixmap,
    QBrush,
    QColor,
    QFont,
    QPen,
    QPainter,
    QPainterPath,
    QPalette,
    QFontMetrics,
    QTextCursor,
)

from database import DatabaseManager
from translations import tr, trf
from utils import (
    get_base_path,
    get_icon,
    load_icon,
    resize_icon,
    format_time,
    format_time_short,
    format_duration,
    format_size,
    OutputCapture,
)
from search_utils import smart_search
from scanner import AudiobookScanner
from tags_dialog import TagManagerDialog
from styles import StyleManager


from metadata_dialog import MetadataEditDialog
from opus_dialog import OpusConversionDialog


def get_placeholder_folder_rect(rect):
    """Calculate the folder icon rect within the given bounds"""
    center = rect.center()
    icon_size = 64
    icon_y_center = center.y() - 40
    # Create a slightly larger hit area for easier clicking
    hit_rect = QRectF(
        float(center.x() - icon_size / 2),
        float(icon_y_center - icon_size / 2 - icon_size * 0.1),
        float(icon_size),
        float(icon_size * 1.0),
    )
    return hit_rect


def draw_library_placeholder(painter, rect):
    """Draw a beautiful placeholder when the library is empty"""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    center = rect.center()

    # 1. Stylized Folder Icon
    icon_size = 64

    # Get color from StyleManager
    _, icon_color = StyleManager.get_theme_property("placeholder_icon")

    painter.setOpacity(1.0)
    painter.setBrush(QBrush(icon_color))
    painter.setPen(Qt.PenStyle.NoPen)

    # Move icon up to prevent overlap
    icon_y_center = center.y() - 40

    # Draw folder shape
    folder_rect = QRectF(
        float(center.x() - icon_size / 2),
        float(icon_y_center - icon_size / 2),
        float(icon_size),
        float(icon_size * 0.7),
    )
    painter.drawRoundedRect(folder_rect, 5, 5)
    # Folder tab
    tab_rect = QRectF(
        float(center.x() - icon_size / 2),
        float(icon_y_center - icon_size / 2 - icon_size * 0.1),
        float(icon_size * 0.4),
        float(icon_size * 0.2),
    )
    painter.drawRoundedRect(tab_rect, 3, 3)

    # 2. Text Message
    painter.setOpacity(1.0)

    # Title
    font_title, color_title = StyleManager.get_theme_property("placeholder_title")
    painter.setPen(QPen(color_title))
    painter.setFont(font_title)

    title_text = tr("status.no_audiobooks_title")

    # Position title below icon
    title_top = icon_y_center + icon_size * 0.6
    painter.drawText(
        QRectF(float(rect.left() + 20), float(title_top), float(rect.width() - 40), 30),
        Qt.AlignmentFlag.AlignCenter,
        title_text,
    )

    # Instructions
    font_text, color_text = StyleManager.get_theme_property("placeholder_text")
    painter.setFont(font_text)
    painter.setPen(QPen(color_text))

    text = tr("status.no_audiobooks_instructions")

    # Position text below title
    text_top = title_top + 45
    text_rect = QRectF(
        float(rect.left() + 40),
        float(text_top),
        float(rect.width() - 80),
        float(rect.height() - text_top),
    )

    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignTop
        | Qt.AlignmentFlag.AlignHCenter
        | Qt.TextFlag.TextWordWrap,
        text,
    )


class TagFilterPopup(QWidget):
    """A popup widget containing a checkable list of tags for filtering"""

    filter_changed = pyqtSignal(set)  # Emits set of checked tag IDs

    def __init__(self, all_tags, selected_ids, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main container frame to handle border and background seamlessley
        self.container_frame = QFrame()
        self.container_frame.setObjectName("TagPopupFrame")

        # Set layout for popup itself (transparent wrapper)
        popup_layout = QVBoxLayout()
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)
        self.setLayout(popup_layout)
        popup_layout.addWidget(self.container_frame)

        # Set layout for inner frame
        container_layout = QVBoxLayout(self.container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Helper layout for buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(5, 5, 5, 5)
        btn_layout.setSpacing(5)

        self.btn_select_all = QPushButton(tr("library.select_all"))
        self.btn_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_all.clicked.connect(self.select_all)

        self.btn_deselect_all = QPushButton(tr("library.deselect_all"))
        self.btn_deselect_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_deselect_all.clicked.connect(self.deselect_all)

        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)

        # Container for buttons - transparent background, no border
        btn_container = QWidget()
        btn_container.setLayout(btn_layout)
        container_layout.addWidget(btn_container)

        # Separator line
        line = QFrame()
        line.setObjectName("popupSeparator")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        container_layout.addWidget(line)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("popupTagList")
        self.list_widget.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )  # Selection handled by checkboxes
        self.list_widget.itemChanged.connect(self._on_item_changed)

        # Install event filter to handle row click
        self.list_widget.viewport().installEventFilter(self)

        # Enforce consistent style (border, rounded corners) regardless of focus state
        # Border handled by container frame, list is transparent/seamless
        # Styles moved to style.qss (#TagPopupFrame, #popupTagList, #popupSeparator)

        # Populate list
        if not all_tags:
            item = QListWidgetItem(
                tr("library.no_tags_available")
                if hasattr(tr, "library.no_tags_available")
                else "No tags available"
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.btn_select_all.setEnabled(False)
            self.btn_deselect_all.setEnabled(False)
        else:
            for tag in all_tags:
                item = QListWidgetItem(tag["name"])
                item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(
                    Qt.CheckState.Checked
                    if tag["id"] in selected_ids
                    else Qt.CheckState.Unchecked
                )
                item.setData(Qt.ItemDataRole.UserRole, tag["id"])

                if tag.get("color"):
                    pixmap = QPixmap(14, 14)
                    pixmap.fill(QColor(tag["color"]))
                    item.setIcon(QIcon(pixmap))

                self.list_widget.addItem(item)

        # Calculate size based on content (max height constraints?)
        rows = self.list_widget.count()
        row_height = self.list_widget.sizeHintForRow(0) if rows > 0 else 20
        # Add a bit of buffer + header height (increased to avoid scrollbar)
        height = min(400, rows * row_height + 25 + 40)
        width = self.list_widget.sizeHintForColumn(0) + 50  # + checkbox/scroll
        width = max(200, width)  # Min width for buttons

        self.list_widget.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.resize(width, height)
        container_layout.addWidget(self.list_widget)

    def select_all(self):
        self._set_all_checked(Qt.CheckState.Checked)

    def deselect_all(self):
        self._set_all_checked(Qt.CheckState.Unchecked)

    def _set_all_checked(self, state):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(state)
        self.list_widget.blockSignals(False)
        # Manually trigger update
        self._on_item_changed(None)

    def eventFilter(self, source, event):
        if (
            source == self.list_widget.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            item = self.list_widget.itemAt(event.pos())
            if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                # Check if click is on the checkbox itself (to avoid double toggle)
                opt = QStyleOptionViewItem()
                rect = self.list_widget.visualItemRect(item)
                opt.rect = rect
                # This gives us a reasonable approximation of where the checkbox is
                # For exact precision we'd need initViewItemOption which is protected
                # But usually checkbox is at the left edge
                style = self.list_widget.style()
                check_rect = style.subElementRect(
                    QStyle.SubElement.SE_ItemViewItemCheckIndicator,
                    opt,
                    self.list_widget,
                )

                # If we are NOT clicking the checkbox, toggle it manually
                if not check_rect.contains(event.pos()):
                    current = item.checkState()
                    item.setCheckState(
                        Qt.CheckState.Unchecked
                        if current == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )
                    return True  # Consume event to prevent default handling (selection etc)

        return super().eventFilter(source, event)

    def _on_item_changed(self, item):
        """Handle checkbox toggle"""
        if item is not None:
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            if tag_id is None:
                return

        # Collect all checked IDs
        checked_ids = set()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                tid = it.data(Qt.ItemDataRole.UserRole)
                if tid is not None:
                    checked_ids.add(tid)

        self.filter_changed.emit(checked_ids)


class ScannerThread(QThread):
    """Background thread for scanning a directory for audiobooks"""

    progress = pyqtSignal(str)  # Log message signal
    finished_scan = pyqtSignal(int)  # Number of audiobooks found signal

    def __init__(self, root_path, ffprobe_path=None, subfolder_path=None, force_rescan=False):
        """Initialize the scanner thread with target path and optional ffprobe path"""
        super().__init__()
        self.root_path = root_path
        self.ffprobe_path = ffprobe_path
        self.subfolder_path = subfolder_path
        self.force_rescan = force_rescan

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
                config_file = script_dir / "resources" / "settings.ini"
                config = configparser.ConfigParser()
                if config_file.exists():
                    config.read(config_file, encoding="utf-8")
                ffprobe_path_str = config.get(
                    "Paths", "ffprobe_path", fallback="resources/bin/ffprobe.exe"
                )
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

            scanner = AudiobookScanner(
                "settings.ini"
            )  # AudiobookScanner handles resources/ internally
            count = scanner.scan_directory(self.root_path, subfolder_path=self.subfolder_path, force_rescan=self.force_rescan)

            # Restore stdout
            sys.stdout = old_stdout
            self.finished_scan.emit(count)
        except Exception as e:
            print(f"Scanner error: {e}")
            self.finished_scan.emit(0)


class CopyThread(QThread):
    """Background thread for copying files/folders to the library"""

    progress = pyqtSignal(str)
    finished_copy = pyqtSignal(int)

    def __init__(self, urls, dest_dir):
        super().__init__()
        self.urls = urls
        self.dest_dir = Path(dest_dir)

    def run(self):
        count = 0

        for url in self.urls:
            try:
                if isinstance(url, str):
                    local_path = Path(url)
                else:
                    local_path = Path(url.toLocalFile())

                if not local_path.exists():
                    continue

                self.progress.emit(f"Copying {local_path.name}...")

                if local_path.is_dir():
                    # Check if folder looks like an audiobook (has audio files)
                    # For now just copy
                    dest = self.dest_dir / local_path.name

                    # Handle duplicate names by appending number
                    if dest.exists():
                        counter = 1
                        while True:
                            new_dest = self.dest_dir / f"{local_path.name}_{counter}"
                            if not new_dest.exists():
                                dest = new_dest
                                break
                            counter += 1

                    shutil.copytree(local_path, dest)
                    count += 1

                elif local_path.is_file():
                    # Create folder for single file
                    folder_name = local_path.stem
                    dest_folder = self.dest_dir / folder_name

                    # Handle duplicate folder names
                    if dest_folder.exists():
                        counter = 1
                        while True:
                            new_dest_folder = self.dest_dir / f"{folder_name}_{counter}"
                            if not new_dest_folder.exists():
                                dest_folder = new_dest_folder
                                break
                            counter += 1

                    dest_folder.mkdir(exist_ok=True)
                    shutil.copy2(local_path, dest_folder / local_path.name)
                    count += 1

            except Exception as e:
                print(f"Copy error: {e}")

        self.finished_copy.emit(count)


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
        self.progress_bar.setRange(0, 0)  # Indeterminate state
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Console Output
        self.console = QTextEdit()
        self.console.setObjectName("scanConsole")
        self.console.setReadOnly(True)
        # Use monospaced font for console - properties extracted from #scanConsole in QSS
        font, _ = StyleManager.get_theme_property("scanConsole")
        self.console.setFont(font)
        layout.addWidget(self.console, 1)

        # Close Button
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

        self.thread = None

    def start_scan(self, root_path, ffprobe_path=None, subfolder_path=None, force_rescan=False):
        """Start the background scanning thread"""
        self.thread = ScannerThread(root_path, ffprobe_path, subfolder_path, force_rescan=force_rescan)
        self.thread.progress.connect(self.append_log)
        self.thread.finished_scan.connect(self.on_finished)
        self.thread.start()

    def append_log(self, text):
        """Append log text to the console, handling carriage returns for in-place updates"""
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Try to parse progress percentage and item count to update the progress bar
        # Format: "15% | [15/100] Book Title"
        import re
        match = re.search(r'(\d+)%\s+\|\s+\[(\d+)/(\d+)\]', text)
        if match:
            percent = int(match.group(1))
            current = int(match.group(2))
            total = int(match.group(3))
            
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat(f"{percent}% ({current}/{total})")
            
            # Update status label to show current phase
            self.status_label.setText(f"{tr('scanner.processing_books')}: {current}/{total}")

        # Handle \r (carriage return) by overwriting the current line
        if "\r" in text:
            parts = text.split("\r")
            for i, part in enumerate(parts):
                if i > 0:  # Part after \r
                    # Select current block/line and remove it
                    cursor.movePosition(
                        QTextCursor.MoveOperation.StartOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
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


# Nesting lines color palette
NESTING_COLORS = [
    QColor("#3498db"),  # Blue
    QColor("#9b59b6"),  # Purple
    QColor("#e74c3c"),  # Red
    QColor("#2ecc71"),  # Light green
    QColor("#8e44ad"),  # Deep purple
    QColor("#d35400"),  # Pumpkin
    QColor("#c0392b"),  # Dark red
    QColor("#16a085"),  # Sea green
    QColor("#2980b9"),  # Strong blue
]


def is_last_visible_child(item):
    p_item = item.parent()
    if p_item:
        # Find all visible children of the parent
        visible_children = [p_item.child(i) for i in range(p_item.childCount()) if not p_item.child(i).isHidden()]
        return visible_children[-1] == item if visible_children else False
    else:
        tree = item.treeWidget()
        if tree:
            visible_top_items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount()) if not tree.topLevelItem(i).isHidden()]
            return visible_top_items[-1] == item if visible_top_items else False
        return False


def get_item_nesting_chain(item):
    """
    Get chain of parent paths for consistent color hashing and last-child info.
    Returns:
        list: List of tuples (parent_path_str, is_last_child_bool)
    """
    chain = []
    current = item.parent()
    while current:
        parent_path = current.data(0, Qt.ItemDataRole.UserRole)
        is_last = is_last_visible_child(current)
        if parent_path:
            chain.insert(0, (str(parent_path), is_last))
        else:
            chain.insert(0, (f"unknown_{len(chain)}", is_last))
        current = current.parent()
    return chain


class MultiLineDelegate(QStyledItemDelegate):
    """Custom item delegate for library tree items with styling and localization support"""

    # QSS object names for various item components
    STYLE_NAMES = [
        "delegate_author",
        "delegate_title",
        "delegate_narrator",
        "delegate_info",
        "delegate_folder",
        "delegate_progress",
        "delegate_duration",
        "delegate_file_count",
        "delegate_favorite",
    ]

    def _get_info_parts(self, progress_percent, file_count, duration, total_size,
                        b_min, b_max, b_mode, codec, container,
                        year_written, year_recorded, language):
        """Build the list of active info line parts in order based on self.info_order"""
        order_list = [item.strip() for item in self.info_order.split(",") if item.strip()]
        
        info_parts = []
        
        for field in order_list:
            if field == "progress":
                if getattr(self, "show_info_progress", True):
                    font_prog, color_prog = self._get_style("delegate_progress")
                    progress_text = trf("delegate.progress", percent=int(progress_percent))
                    info_parts.append((None, progress_text, font_prog, color_prog))
                    
            elif field == "file_count":
                if file_count and getattr(self, "show_info_file_count", True):
                    font_fc, color_fc = self._get_style("delegate_file_count")
                    info_parts.append((self.info_file_count_icon, str(file_count), font_fc, color_fc))
                    
            elif field == "duration":
                if duration and getattr(self, "show_info_duration", True):
                    font_dur, color_dur = self._get_style("delegate_duration")
                    duration_text = format_duration(duration)
                    info_parts.append((self.info_duration_icon, duration_text, font_dur, color_dur))
                    
            elif field == "size":
                if total_size and getattr(self, "show_info_size", True):
                    font_sz, color_sz = self._get_style("delegate_file_count")
                    size_text = format_size(total_size)
                    info_parts.append((self.info_size_icon, size_text, font_sz, color_sz))
                    
            elif field == "technical":
                if (b_min or codec or container) and getattr(self, "show_info_technical", True):
                    tech_line = []
                    if b_min:
                        calc_min = b_min // 1000 if b_min > 5000 else b_min
                        calc_max = b_max // 1000 if b_max > 5000 else b_max
                        if calc_min == calc_max:
                            br_str = f"{calc_min}"
                        else:
                            br_str = f"{calc_min}-{calc_max}"
                        tech_line.append(f"{br_str} {tr('units.kbps', default='kbps')}")
                    if b_mode:
                        tech_line.append(b_mode)
                    codec_info = []
                    if codec:
                        codec_info.append(codec.lower())
                    if container and container.lower() != codec.lower():
                        codec_info.append(container.lower())
                    if codec_info:
                        tech_line.append("/".join(codec_info))
                    if tech_line:
                        full_tech_text = ' '.join(tech_line)
                        font_tech, color_tech = self._get_style("delegate_file_count")
                        info_parts.append((self.info_bitrate_icon, full_tech_text, font_tech, color_tech))
                        
            elif field == "year_written":
                if year_written and str(year_written).strip() and getattr(self, "show_info_year_written", True):
                    font_yw, color_yw = self._get_style("delegate_file_count")
                    if self.author_icon and not self.author_icon.isNull():
                        info_parts.append((self.author_icon, str(year_written), font_yw, color_yw))
                    else:
                        yw_prefix = tr("delegate.year_written_prefix", default="✍️")
                        info_parts.append((None, f"{yw_prefix} {year_written}", font_yw, color_yw))
                        
            elif field == "year_recorded":
                if year_recorded and str(year_recorded).strip() and getattr(self, "show_info_year_recorded", True):
                    font_yr, color_yr = self._get_style("delegate_file_count")
                    if self.narrator_icon and not self.narrator_icon.isNull():
                        info_parts.append((self.narrator_icon, str(year_recorded), font_yr, color_yr))
                    else:
                        yr_prefix = tr("delegate.year_recorded_prefix", default="💿")
                        info_parts.append((None, f"{yr_prefix} {year_recorded}", font_yr, color_yr))
                        
            elif field == "language":
                if language and str(language).strip() and getattr(self, "show_info_language", True):
                    font_lang, color_lang = self._get_style("delegate_file_count")
                    if self.info_language_icon and not self.info_language_icon.isNull():
                        info_parts.append((self.info_language_icon, language, font_lang, color_lang))
                    else:
                        lang_prefix = tr("delegate.language_prefix", default="🌐")
                        info_parts.append((None, f"{lang_prefix} {language}", font_lang, color_lang))
                        
        return info_parts

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
        self.show_nesting_lines = True
        self.show_detailed_info = True
        self.show_status_triangle = True
        
        # Book info elements visibility flags
        self.show_info_progress = True
        self.show_info_file_count = True
        self.show_info_duration = True
        self.show_info_size = True
        self.show_info_technical = True
        self.show_info_year_written = True
        self.show_info_year_recorded = True
        self.show_info_language = True
        self.info_order = "progress,file_count,duration,size,technical,year_written,year_recorded,language"

        # UI state for interaction
        self.hovered_index = None
        self.hovered_field = None
        self.mouse_pos = None

        # Narrator icon
        self.narrator_icon = get_icon("narrator")
        self.author_icon = get_icon("author")

        # Technical/metadata icons
        self.info_bitrate_icon = get_icon("info_bitrate")
        self.info_file_count_icon = get_icon("info_file_count")
        self.info_duration_icon = get_icon("info_duration")
        self.info_size_icon = get_icon("info_size")
        self.info_language_icon = get_icon("languages")

        # Nesting lines color palette
        self.NESTING_COLORS = NESTING_COLORS

    @lru_cache(maxsize=32)
    def _get_style(self, style_name: str) -> tuple[QFont, QColor]:
        """Fetch font and color settings from the style manager mapped to the given name"""
        return StyleManager.get_theme_property(style_name)

    def update_styles(self):
        """Force a refresh of style properties from the loaded QSS"""
        self._get_style.cache_clear()
        # Proxy widgets in StyleManager handle themselves when ensurePolished is called

    def load_icons(self):
        """Reload all SVGs to apply the new color/thickness"""
        self.narrator_icon = get_icon("narrator")
        self.author_icon = get_icon("author")
        self.info_bitrate_icon = get_icon("info_bitrate")
        self.info_file_count_icon = get_icon("info_file_count")
        self.info_duration_icon = get_icon("info_duration")
        self.info_size_icon = get_icon("info_size")
        self.info_language_icon = get_icon("languages")

    def _get_nesting_chain(self, index):
        """
        Get chain of parent paths for consistent color hashing and last-child info.

        Returns:
            list: List of tuples (parent_path_str, is_last_child_bool)
        """
        chain = []
        current = index.parent()

        while current.isValid():
            # Get parent path (unique identifier)
            parent_path = current.data(Qt.ItemDataRole.UserRole)

            # Check if this parent is the last child in ITS parent
            is_last = False
            p_idx = current.parent()

            if p_idx.isValid():
                is_last = current.row() == p_idx.model().rowCount(p_idx) - 1
            else:
                model = current.model()
                if model:
                    is_last = current.row() == model.rowCount(QModelIndex()) - 1

            if parent_path:
                chain.insert(0, (str(parent_path), is_last))  # Top parents first
            else:
                chain.insert(0, (f"unknown_{len(chain)}", is_last))

            current = p_idx

        return chain

    def get_nesting_offset(self, index: QModelIndex) -> int:
        """Calculate horizontal offset for item content based on nesting depth"""
        if not self.show_nesting_lines:
            return 0

        # Quick depth check without building the full chain
        depth = 0
        curr = index.parent()
        while curr.isValid():
            depth += 1
            curr = curr.parent()

        if depth <= 0:
            return 0

        # Get tree indentation
        tree = getattr(self, "tree", None) or self.parent()
        indent = 12
        if hasattr(tree, "indentation"):
            indent = tree.indentation()

        line_width = 2
        spacing = max(2, indent - line_width)
        return line_width + spacing

    def _draw_nesting_lines(self, painter, rect, chain, index=None):
        """
        Draw colored vertical lines indicating nesting depth.
        Color is uniquely determined by parent paths.

        Args:
            painter: QPainter object
            rect: QRect of item drawing area
            chain: List of tuples (parent_path, is_last_child) from _get_nesting_chain()
            index: QModelIndex of current item (optional)

        Returns:
            int: Offset in pixels to shift content right
        """
        if not self.show_nesting_lines:
            return 0

        depth = len(chain)
        if depth <= 0:
            return 0

        line_width = 2

        # Get tree indentation for perfect line alignment
        tree = getattr(self, "tree", None) or self.parent()
        indent = 12  # Default value matching tree.setIndentation(12)
        if hasattr(tree, "indentation"):
            indent = tree.indentation()

        spacing = max(2, indent - line_width)

        # Determine if this item is the last child of its parent
        is_last_child = False
        if index is not None and index.isValid() and index.parent().isValid():
            p_idx = index.parent()
            is_last_child = index.row() == p_idx.model().rowCount(p_idx) - 1

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        for i in range(depth):
            parent_path_str, _ = chain[i]

            # If ancestor line already ended in previous folder, skip it for descendants
            if i < depth - 1:
                child_is_last = chain[i + 1][1]
                if child_is_last:
                    continue

            # Hash path to get stable positive integer
            path_hash = zlib.adler32(parent_path_str.encode("utf-8", errors="ignore"))
            color_index = path_hash % len(self.NESTING_COLORS)
            color = self.NESTING_COLORS[color_index]

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            # Key trick: shift lines left by `indent` depending on their level,
            # so they align perfectly with parent line
            line_x = rect.left() - (depth - 1 - i) * indent

            if i == depth - 1:
                # This is the item's own nesting line
                if is_last_child:
                    # └ pattern: vertical from top to middle + horizontal branch
                    # Vertical segment (top to middle)
                    painter.drawRect(
                        QRectF(
                            line_x,
                            rect.top(),
                            line_width,
                            rect.height() / 2 + line_width / 2,
                        )
                    )

                    # Horizontal segment (from middle right, pointing to thumbnail)
                    painter.drawRect(
                        QRectF(
                            line_x,
                            rect.top() + (rect.height() - line_width) / 2,
                            indent,
                            line_width,
                        )
                    )
                else:
                    # ├ pattern: full vertical line + horizontal branch at middle
                    # Full vertical line
                    painter.drawRect(
                        QRectF(line_x, rect.top(), line_width, rect.height())
                    )

                    # Horizontal branch at middle
                    painter.drawRect(
                        QRectF(
                            line_x,
                            rect.top() + (rect.height() - line_width) / 2,
                            indent,
                            line_width,
                        )
                    )
            else:
                # Regular full vertical line for parent levels
                painter.drawRect(QRectF(line_x, rect.top(), line_width, rect.height()))

        painter.restore()

        # Return offset only for last line plus spacing,
        # because other lines were drawn left, inside branching area
        return line_width + spacing

    def sizeHint(self, option, index) -> QSize:
        """Determine item size based on type (folder vs audiobook)"""
        size = super().sizeHint(option, index)
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)

        if item_type == "folder":
            size.setHeight(self.folder_row_height)
        elif item_type == "audiobook":
            size.setHeight(self.audiobook_row_height)

        return size

    def paint(self, painter, option, index):
        """Perform custom rendering for library items based on their type and state"""
        try:
            item_type = index.data(Qt.ItemDataRole.UserRole + 1)

            if item_type == "folder":
                self._paint_folder(painter, option, index)
            elif item_type == "audiobook":
                self._paint_audiobook(painter, option, index)
            else:
                super().paint(painter, option, index)
        except Exception as e:
            import traceback

            print(f"ERROR: Exception in MultiLineDelegate.paint: {e}")
            traceback.print_exc()

    def _paint_folder(self, painter, option, index):
        """Draw a folder item with icon and display name"""
        painter.save()

        # Draw nesting lines
        chain = self._get_nesting_chain(index)
        nesting_offset = self._draw_nesting_lines(painter, option.rect, chain, index)

        # Active folder indicator: Draw accent bar if playing_path is within this folder
        folder_path = index.data(Qt.ItemDataRole.UserRole)
        if self.playing_path and folder_path:
            is_active = False
            # Normalize for comparison
            p_path = str(self.playing_path).replace("\\", "/")
            f_path = str(folder_path).replace("\\", "/")

            if p_path.startswith(f_path):
                # Ensure it's a subpath or identical
                if len(p_path) == len(f_path) or p_path[len(f_path)] == "/":
                    is_active = True

            if is_active:
                _, accent_color = self._get_style("delegate_accent")
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(accent_color)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                # Draw rounded bar on the left edge with a small vertical margin for better visibility of rounding
                # Position it after nesting lines
                bar_rect = QRectF(
                    float(option.rect.left() + nesting_offset + 2),
                    float(option.rect.top() + 4),
                    3.0,
                    float(option.rect.height() - 8),
                )
                painter.drawRoundedRect(bar_rect, 2, 2)

        font, color = self._get_style("delegate_folder")
        painter.setFont(font)
        painter.setPen(color)

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_size = 20
        icon_rect = QRect(
            option.rect.left() + nesting_offset + self.horizontal_padding,
            option.rect.top() + (option.rect.height() - icon_size) // 2,
            icon_size,
            icon_size,
        )
        if icon:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            icon.paint(painter, icon_rect)

        # Draw mass selection checkbox if mode is active
        tree = getattr(self, "tree", None) or self.parent()
        mass_mode = getattr(tree, "mass_selection_mode", False)
        if mass_mode:
            cb_rect = self.get_checkbox_rect(QRectF(icon_rect))
            selected_paths = getattr(tree, "selected_audiobook_paths", set())
            is_checked = folder_path in selected_paths
            
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            border_color = QColor("#555555")
            _, accent_color = self._get_style("delegate_accent")
            
            is_over_cb = False
            if self.mouse_pos and cb_rect.contains(QPointF(self.mouse_pos)):
                is_over_cb = True
                
            if is_checked:
                bg_color = accent_color
                if is_over_cb:
                    bg_color = bg_color.lighter(110)
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(cb_rect, 4.0, 4.0)
                
                checkmark_path = QPainterPath()
                w = cb_rect.width()
                h = cb_rect.height()
                checkmark_path.moveTo(cb_rect.left() + w * 0.25, cb_rect.top() + h * 0.5)
                checkmark_path.lineTo(cb_rect.left() + w * 0.45, cb_rect.top() + h * 0.75)
                checkmark_path.lineTo(cb_rect.left() + w * 0.75, cb_rect.top() + h * 0.35)
                
                pen = QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(checkmark_path)
            else:
                bg_color = QColor(Qt.GlobalColor.transparent)
                if is_over_cb:
                    border_color = border_color.lighter(130)
                painter.setBrush(bg_color)
                painter.setPen(QPen(border_color, 1.5))
                painter.drawRoundedRect(cb_rect, 4.0, 4.0)
                
            painter.restore()

        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_x = icon_rect.right() + (43 if mass_mode else 8)
        text_rect = QRect(
            text_x,
            option.rect.top(),
            option.rect.right() - text_x - 18,
            option.rect.height(),
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text or "")

        # Draw horizontal line at bottom for expanded folders
        # Get the tree widget from the option
        tree_widget = option.widget
        if (
            tree_widget
            and isinstance(tree_widget, QTreeWidget)
            and self.show_nesting_lines
        ):
            item = tree_widget.itemFromIndex(index)
            if item:
                is_exp = item.isExpanded()
                child_cnt = item.childCount()
                if is_exp and child_cnt > 0:
                    folder_path = index.data(Qt.ItemDataRole.UserRole)
                    if folder_path:
                        # Calculate color for next nesting level (children's color)
                        path_hash = zlib.adler32(
                            str(folder_path).encode("utf-8", errors="ignore")
                        )
                        color_index = path_hash % len(self.NESTING_COLORS)
                        line_color = self.NESTING_COLORS[color_index]

                        # Draw horizontal line at bottom
                        line_width = 2
                        painter.save()
                        painter.setPen(QPen(line_color, line_width))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

                        # Calculate starting X position to avoid intersection with parent's vertical line
                        start_x = option.rect.left()
                        depth = len(chain)
                        if depth > 0:
                            gap = 4
                            start_x += line_width + gap

                        # Draw line at the very bottom of the item
                        y_pos = option.rect.bottom() - 1
                        painter.drawLine(
                            start_x, y_pos, option.rect.right(), y_pos
                        )

                        painter.restore()

        painter.restore()

    def get_icon_rect(self, rect: QRect, index) -> QRect:
        """Calculate the rect for the cover icon, taking progress bar into account"""
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        if item_type == "folder":
            nesting_offset = self.get_nesting_offset(index)
            icon_size = 20
            return QRect(
                rect.left() + nesting_offset + self.horizontal_padding,
                rect.top() + (rect.height() - icon_size) // 2,
                icon_size,
                icon_size,
            )
        elif item_type != "audiobook":
            return QRect()

        nesting_offset = self.get_nesting_offset(index)

        # Check if progress bar is present
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        progress_percent = 0
        if data and len(data) >= 7:
            progress_percent = data[6]

        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
        is_started = False
        if status_data and len(status_data) >= 3:
            is_started = bool(status_data[0])

        has_progress = (progress_percent > 0 or is_started)

        pb_h = 5
        if has_progress:
            icon_y = rect.top() + (rect.height() - (self.audiobook_icon_size + pb_h)) // 2 + 2
        else:
            icon_y = rect.top() + (rect.height() - self.audiobook_icon_size) // 2

        return QRect(
            rect.left() + nesting_offset + self.horizontal_padding,
            icon_y,
            self.audiobook_icon_size,
            self.audiobook_icon_size,
        )

    def get_checkbox_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate bounds for the mass selection checkbox"""
        cb_width = 18.0
        cb_height = 18.0
        x = icon_rect.right() + 10.0
        y = icon_rect.top() + (icon_rect.height() - cb_height) / 2.0
        return QRectF(x, y, cb_width, cb_height)

    def get_play_button_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the play button overlay in high precision"""
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(
            center.x() - btn_size / 2.0, center.y() - btn_size / 2.0, btn_size, btn_size
        )

    def get_heart_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the favorite heart icon relative to the main icon"""
        heart_size = 20.0
        # Position: Top-Right of icon, same as in paint
        return QRectF(
            float(icon_rect.right() - heart_size + 5),
            float(icon_rect.top() - 5),
            float(heart_size),
            float(heart_size),
        )

    def get_info_rect(self, icon_rect: QRectF) -> QRectF:
        """Calculate the rect for the info icon"""
        info_size = 20.0
        # Position: Top-Left of icon, mirrored from heart
        return QRectF(
            float(icon_rect.left() - 5),
            float(icon_rect.top() - 5),
            float(info_size),
            float(info_size),
        )

    def _calculate_text_start_y(self, option_rect, index) -> int:
        """Calculate the starting Y coordinate for the text block to center it vertically in the option_rect"""
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            return int(option_rect.top() + self.vertical_padding)

        author = data[0] if len(data) > 0 else None
        title = data[1] if len(data) > 1 else None
        narrator = data[2] if len(data) > 2 else None
        
        file_count = data[3] if len(data) > 3 else 0
        duration = data[4] if len(data) > 4 else 0
        listened_duration = data[5] if len(data) > 5 else 0
        progress_percent = data[6] if len(data) > 6 else 0
        codec = data[7] if len(data) > 7 else None
        b_min = data[8] if len(data) > 8 else None
        b_max = data[9] if len(data) > 9 else None
        b_mode = data[10] if len(data) > 10 else None
        container = data[11] if len(data) > 11 else None
        description = data[12] if len(data) > 12 else ""
        total_size = data[13] if len(data) > 13 else 0
        language = data[14] if len(data) > 14 else None
        year_written = data[15] if len(data) > 15 else None
        year_recorded = data[16] if len(data) > 16 else None

        tags = index.data(Qt.ItemDataRole.UserRole + 4)

        total_height = 0
        elements_count = 0

        # Title
        font_title, _ = self._get_style("delegate_title")
        title_height = QFontMetrics(font_title).height()
        total_height += title_height
        elements_count += 1

        # Author
        if author:
            font_author, _ = self._get_style("delegate_author")
            author_height = QFontMetrics(font_author).height()
            total_height += author_height
            elements_count += 1

        # Narrator
        if narrator:
            font_narrator, _ = self._get_style("delegate_narrator")
            narrator_height = QFontMetrics(font_narrator).height()
            total_height += narrator_height
            elements_count += 1

        # Status info line
        info_parts = self._get_info_parts(
            progress_percent, file_count, duration, total_size,
            b_min, b_max, b_mode, codec, container,
            year_written, year_recorded, language
        )
        if info_parts and getattr(self, "show_detailed_info", True):
            font_inf, _ = self._get_style("delegate_file_count")
            info_height = QFontMetrics(font_inf).height()
            total_height += info_height
            elements_count += 1

        # Tags
        if tags:
            font_tag, _ = self._get_style("delegate_info_font")
            tag_height = QFontMetrics(font_tag).height() + 4
            total_height += tag_height
            elements_count += 1

        if elements_count > 1:
            total_height += (elements_count - 1) * self.line_spacing

        return int(option_rect.top() + (option_rect.height() - total_height) // 2)

    def _paint_audiobook(self, painter, option, index):
        """Render detailed audiobook item with cover, progress, and metadata"""
        painter.save()

        # Draw nesting lines
        chain = self._get_nesting_chain(index)
        nesting_offset = self._draw_nesting_lines(painter, option.rect, chain, index)

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_rect = self.get_icon_rect(option.rect, index)
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            painter.restore()
            return

        (
            author,
            title,
            narrator,
            file_count,
            duration,
            listened_duration,
            progress_percent,
            codec,
            b_min,
            b_max,
            b_mode,
            container,
        ) = data[:12]
        description = data[12] if len(data) > 12 else ""
        total_size = data[13] if len(data) > 13 else 0
        language = data[14] if len(data) > 14 else None
        year_written = data[15] if len(data) > 15 else None
        year_recorded = data[16] if len(data) > 16 else None

        # Unpack status data for favorites and progress tracking
        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
        is_favorite = False
        is_started = False
        is_completed = False
        if status_data and len(status_data) >= 3:
            is_started = bool(status_data[0])
            is_completed = bool(status_data[1])
            is_favorite = status_data[2]

        if icon:
            # Calculate playing status early
            playing_file = index.data(Qt.ItemDataRole.UserRole)
            is_playing_this = self.playing_path and playing_file == self.playing_path

            painter.save()
            path = QPainterPath()
            path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setClipPath(path)

            # 1. Main Cover
            icon.paint(painter, icon_rect)

            # 3. Hover Background
            if self.hovered_index == index:
                _, overlay_bg = StyleManager.get_theme_property("overlay_background")
                painter.fillRect(icon_rect, overlay_bg)

            # Draw status triangle (New / Started / Finished)
            if getattr(self, "show_status_triangle", True):
                if is_completed:
                    _, status_color = StyleManager.get_theme_property("delegate_status_completed")
                    if not status_color.isValid() or status_color == QColor():
                        status_color = QColor("#4ecca3")
                elif is_started:
                    _, status_color = StyleManager.get_theme_property("delegate_status_started")
                    if not status_color.isValid() or status_color == QColor():
                        status_color = QColor("#f9ca24")
                else:
                    _, status_color = StyleManager.get_theme_property("delegate_status_new")
                    if not status_color.isValid() or status_color == QColor():
                        status_color = QColor("#ff6b6b")

                tri_size = icon_rect.width() * 0.25
                tri_path = QPainterPath()
                tri_path.moveTo(float(icon_rect.left()), float(icon_rect.top()))
                tri_path.lineTo(float(icon_rect.left() + tri_size), float(icon_rect.top()))
                tri_path.lineTo(float(icon_rect.left()), float(icon_rect.top() + tri_size))
                tri_path.closeSubpath()

                painter.save()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(status_color))
                painter.drawPath(tri_path)
                painter.restore()

            painter.restore()

            # 4. Currently Playing Highlight Border
            if is_playing_this:
                # Dense green border for active book, enclosing both cover and progress bar
                _, accent_color = self._get_style("delegate_accent")
                pen = QPen(accent_color, 8)
                painter.setPen(pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                has_progress = (progress_percent > 0 or is_started)
                pb_h = 5
                if has_progress:
                    highlight_rect = QRectF(
                        float(icon_rect.left()),
                        float(icon_rect.top()),
                        float(icon_rect.width()),
                        float(icon_rect.height() + pb_h),
                    )
                else:
                    highlight_rect = QRectF(icon_rect)
                    
                painter.drawRoundedRect(highlight_rect.adjusted(-4, -4, 4, 4), 7, 7)

            # 2. Under-cover Progress Indicator
            if progress_percent > 0 or is_started:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                pb_h = 5
                pb_margin = 0
                pb_rect = QRectF(
                    float(icon_rect.left() + pb_margin),
                    float(icon_rect.bottom()),
                    float(icon_rect.width() - pb_margin * 2),
                    float(pb_h),
                )

                # Background
                _, bg_color = StyleManager.get_theme_property("overlay_progress_bg")
                painter.fillRect(pb_rect, bg_color)

                # Fill
                fill_w = pb_rect.width() * progress_percent / 100.0
                if fill_w > 0:
                    fill_rect = QRectF(
                        pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height()
                    )
                    _, primary_color = StyleManager.get_theme_property("theme_primary")
                    painter.fillRect(fill_rect, primary_color)

                painter.restore()

            # Draw Favorite Heart
            if is_favorite:
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Position: Top-Right of icon
                heart_rect = self.get_heart_rect(QRectF(icon_rect))

                # Check hover for heart icon
                is_over_heart = False
                if self.mouse_pos and heart_rect.contains(QPointF(self.mouse_pos)):
                    is_over_heart = True

                # Draw circle background
                prop = (
                    "icon_background" if not is_over_heart else "icon_background_hover"
                )
                _, bg_color = StyleManager.get_theme_property(prop)
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(heart_rect)

                # Draw Heart Shape
                _, accent_color = self._get_style("delegate_accent")
                painter.setBrush(accent_color)
                # Make the heart wider by reducing horizontal padding
                hr = heart_rect.adjusted(1, 2, -1, -3)

                path = QPainterPath()
                path.moveTo(hr.center().x(), hr.bottom())
                path.cubicTo(
                    hr.right(),
                    hr.center().y(),
                    hr.right(),
                    hr.top(),
                    hr.center().x(),
                    hr.top() + hr.height() * 0.2,
                )
                path.cubicTo(
                    hr.left(),
                    hr.top(),
                    hr.left(),
                    hr.center().y(),
                    hr.center().x(),
                    hr.bottom(),
                )

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

                # Background: Color from QSS
                prop = (
                    "icon_background" if not is_over_info else "icon_background_hover"
                )
                _, bg_color = StyleManager.get_theme_property(prop)

                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(info_rect)

                # Draw 'i'
                _, accent_color = self._get_style("delegate_accent")
                painter.setPen(accent_color)
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
                _, accent_color = self._get_style("delegate_accent")
                btn_color = accent_color
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
                    start_x = (
                        play_btn_rect.left() + (play_btn_rect.width() - total_w) // 2
                    )
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
                    tri_path.moveTo(
                        center_f.x() - side / 3.0 + h_offset, center_f.y() - side / 2.0
                    )
                    tri_path.lineTo(
                        center_f.x() - side / 3.0 + h_offset, center_f.y() + side / 2.0
                    )
                    tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                    tri_path.closeSubpath()

                    painter.fillPath(tri_path, Qt.GlobalColor.white)

                painter.restore()

        # Draw mass selection checkbox if mode is active
        tree = getattr(self, "tree", None) or self.parent()
        mass_mode = getattr(tree, "mass_selection_mode", False)
        if mass_mode:
            playing_file = index.data(Qt.ItemDataRole.UserRole)
            cb_rect = self.get_checkbox_rect(QRectF(icon_rect))
            
            selected_paths = getattr(tree, "selected_audiobook_paths", set())
            is_checked = playing_file in selected_paths
            
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            border_color = QColor("#555555")
            _, accent_color = self._get_style("delegate_accent")
            
            is_over_cb = False
            if self.mouse_pos and cb_rect.contains(QPointF(self.mouse_pos)):
                is_over_cb = True
            
            if is_checked:
                bg_color = accent_color
                if is_over_cb:
                    bg_color = bg_color.lighter(110)
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(cb_rect, 4.0, 4.0)
                
                checkmark_path = QPainterPath()
                w = cb_rect.width()
                h = cb_rect.height()
                checkmark_path.moveTo(cb_rect.left() + w * 0.25, cb_rect.top() + h * 0.5)
                checkmark_path.lineTo(cb_rect.left() + w * 0.45, cb_rect.top() + h * 0.75)
                checkmark_path.lineTo(cb_rect.left() + w * 0.75, cb_rect.top() + h * 0.35)
                
                pen = QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(checkmark_path)
            else:
                bg_color = QColor(Qt.GlobalColor.transparent)
                if is_over_cb:
                    border_color = border_color.lighter(130)
                painter.setBrush(bg_color)
                painter.setPen(QPen(border_color, 1.5))
                painter.drawRoundedRect(cb_rect, 4.0, 4.0)
                
            painter.restore()

        # Layout shift if mass selection mode is active
        if mass_mode:
            text_x = icon_rect.right() + 43
        else:
            text_x = icon_rect.right() + 15
        text_y = self._calculate_text_start_y(option.rect, index)
        available_width = option.rect.right() - text_x - self.horizontal_padding

        # Title field
        font, color = self._get_style("delegate_title")
        painter.setFont(font)
        painter.setPen(color)

        line_height = painter.fontMetrics().height()
        rect = QRect(text_x, text_y, available_width, line_height)

        elided_title = painter.fontMetrics().elidedText(
            title or tr("delegate.no_title"),
            Qt.TextElideMode.ElideRight,
            available_width,
        )
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_title,
        )
        text_y += line_height + self.line_spacing

        # Author field
        if author:
            font, color = self._get_style("delegate_author")
            if self.hovered_index == index and getattr(self, "hovered_field", None) == "author":
                font = QFont(font)
                font.setBold(True)
            painter.setFont(font)
            painter.setPen(color)

            line_height = painter.fontMetrics().height()
            
            author_x = text_x
            if hasattr(self, "author_icon") and not self.author_icon.isNull():
                icon_size = 14
                icon_y = text_y + (line_height - icon_size) // 2
                icon_rect = QRect(text_x, icon_y, icon_size, icon_size)
                
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.author_icon.paint(painter, icon_rect)
                painter.restore()
                
                author_x += icon_size + 3

            rect = QRect(author_x, text_y, option.rect.right() - author_x - self.horizontal_padding, line_height)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, author
            )
            text_y += line_height + self.line_spacing

        # NARRATOR Metadata
        if narrator:
            font, color = self._get_style("delegate_narrator")
            if self.hovered_index == index and getattr(self, "hovered_field", None) == "narrator":
                font = QFont(font)
                font.setBold(True)
            painter.setFont(font)
            painter.setPen(color)

            line_height = painter.fontMetrics().height()
            
            icon_drawn = False
            narrator_x = text_x
            
            if hasattr(self, "narrator_icon") and not self.narrator_icon.isNull():
                icon_size = 14
                icon_y = text_y + (line_height - icon_size) // 2
                icon_rect = QRect(text_x, icon_y, icon_size, icon_size)
                
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.narrator_icon.paint(painter, icon_rect)
                painter.restore()
                
                narrator_x += icon_size + 3
                icon_drawn = True
                
            if icon_drawn:
                narrator_text = narrator
            else:
                narrator_text = f"{tr('delegate.narrator_prefix')} {narrator}"

            rect = QRect(narrator_x, text_y, option.rect.right() - narrator_x - self.horizontal_padding, line_height)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                narrator_text,
            )
            text_y += line_height + self.line_spacing

        # STATUS INFO LINE (Files, Duration, Progress)
        info_parts = self._get_info_parts(
            progress_percent, file_count, duration, total_size,
            b_min, b_max, b_mode, codec, container,
            year_written, year_recorded, language
        )

        # Draw consolidated info line with custom formatting/spacing
        if info_parts and getattr(self, "show_detailed_info", True):
            current_x = text_x
            for i, (icon, text, font, color) in enumerate(info_parts):
                painter.setFont(font)
                painter.setPen(color)

                text_width = painter.fontMetrics().horizontalAdvance(text)
                line_height = painter.fontMetrics().height()

                # Draw graphic icon if present
                if icon and not icon.isNull():
                    icon_size = 14
                    icon_y = text_y + (line_height - icon_size) // 2
                    icon_rect = QRect(current_x, icon_y, icon_size, icon_size)

                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    icon.paint(painter, icon_rect)
                    painter.restore()

                    current_x += icon_size + 3

                rect = QRect(current_x, text_y, text_width + 10, line_height)
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    text,
                )

                current_x += text_width + 15

                # Inline separator dot
                if i < len(info_parts) - 1:
                    _, dot_color = StyleManager.get_theme_property("separator_dot")
                    painter.setPen(dot_color)
                    painter.drawText(
                        QRect(current_x - 10, text_y, 10, line_height),
                        Qt.AlignmentFlag.AlignCenter,
                        tr("delegate.separator"),
                    )

            text_y += line_height + self.line_spacing

        # Tags rendering
        tags = index.data(Qt.ItemDataRole.UserRole + 4)
        if tags:
            tag_x = text_x

            painter.save()

            for tag in tags:
                tag_name = tag["name"]
                _, accent_color = self._get_style("delegate_accent")
                tag_color = QColor(tag["color"] or accent_color.name())

                # Dynamic text color based on brightness
                text_color = (
                    Qt.GlobalColor.white
                    if tag_color.lightness() < 130
                    else Qt.GlobalColor.black
                )

                font_tag, _ = self._get_style("delegate_info_font")
                painter.setFont(font_tag)
                fm = painter.fontMetrics()
                t_w = fm.horizontalAdvance(tag_name)
                t_h = fm.height() + 4

                tag_rect = QRectF(
                    float(tag_x), float(text_y), float(t_w + 12), float(t_h)
                )

                # Check for overflow
                if tag_rect.right() > option.rect.right() - 10:
                    break

                is_hovered_tag = (
                    self.hovered_index == index
                    and getattr(self, "hovered_field", None) == f"tag:{tag['id']}"
                )
                if is_hovered_tag:
                    tag_color = tag_color.lighter(115)

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

    def get_author_rect(self, option_rect: QRect, index: QModelIndex) -> QRect:
        """Calculate bounds for the author field including icon and text width"""
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        if item_type != "audiobook":
            return QRect()

        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data or len(data) < 1:
            return QRect()

        author = data[0]
        if not author:
            return QRect()

        icon_rect = self.get_icon_rect(option_rect, index)
        tree = getattr(self, "tree", None) or self.parent()
        mass_mode = getattr(tree, "mass_selection_mode", False)
        text_x = icon_rect.right() + (43 if mass_mode else 15)
        text_y = self._calculate_text_start_y(option_rect, index)

        # Skip title
        font_title, _ = self._get_style("delegate_title")
        title_height = QFontMetrics(font_title).height()
        text_y += title_height + self.line_spacing

        font_author, _ = self._get_style("delegate_author")
        author_height = QFontMetrics(font_author).height()

        author_x = text_x
        icon_width = 0
        if hasattr(self, "author_icon") and not self.author_icon.isNull():
            icon_width = 14 + 6
            author_x += icon_width

        fm = QFontMetrics(font_author)
        text_width = fm.horizontalAdvance(author)
        available_width = option_rect.right() - author_x - self.horizontal_padding
        actual_width = min(text_width, available_width)

        return QRect(text_x, text_y, icon_width + actual_width, author_height)

    def get_narrator_rect(self, option_rect: QRect, index: QModelIndex) -> QRect:
        """Calculate bounds for the narrator field including icon and text width"""
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        if item_type != "audiobook":
            return QRect()

        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data or len(data) < 3:
            return QRect()

        author = data[0]
        narrator = data[2]
        if not narrator:
            return QRect()

        icon_rect = self.get_icon_rect(option_rect, index)
        tree = getattr(self, "tree", None) or self.parent()
        mass_mode = getattr(tree, "mass_selection_mode", False)
        text_x = icon_rect.right() + (43 if mass_mode else 15)
        text_y = self._calculate_text_start_y(option_rect, index)

        # Skip title
        font_title, _ = self._get_style("delegate_title")
        title_height = QFontMetrics(font_title).height()
        text_y += title_height + self.line_spacing

        # Skip author if present
        if author:
            font_author, _ = self._get_style("delegate_author")
            author_height = QFontMetrics(font_author).height()
            text_y += author_height + self.line_spacing

        font_narrator, _ = self._get_style("delegate_narrator")
        narrator_height = QFontMetrics(font_narrator).height()

        narrator_x = text_x
        icon_width = 0
        icon_drawn = False
        if hasattr(self, "narrator_icon") and not self.narrator_icon.isNull():
            icon_width = 14 + 6
            narrator_x += icon_width
            icon_drawn = True

        if icon_drawn:
            narrator_text = narrator
        else:
            narrator_text = f"{tr('delegate.narrator_prefix')} {narrator}"

        fm = QFontMetrics(font_narrator)
        text_width = fm.horizontalAdvance(narrator_text)
        available_width = option_rect.right() - narrator_x - self.horizontal_padding
        actual_width = min(text_width, available_width)

        return QRect(text_x, text_y, icon_width + actual_width, narrator_height)

    def get_tags_rects(self, option_rect: QRect, index: QModelIndex) -> list:
        """Calculate the rects for each tag of the given audiobook index"""
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        if item_type != "audiobook":
            return []

        tags = index.data(Qt.ItemDataRole.UserRole + 4)
        if not tags:
            return []

        icon_rect = self.get_icon_rect(option_rect, index)
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            return []

        (
            author,
            title,
            narrator,
            file_count,
            duration,
            listened_duration,
            progress_percent,
            codec,
            b_min,
            b_max,
            b_mode,
            container,
        ) = data[:12]
        description = data[12] if len(data) > 12 else ""
        total_size = data[13] if len(data) > 13 else 0
        language = data[14] if len(data) > 14 else None
        year_written = data[15] if len(data) > 15 else None
        year_recorded = data[16] if len(data) > 16 else None

        tree = getattr(self, "tree", None) or self.parent()
        mass_mode = getattr(tree, "mass_selection_mode", False)
        if mass_mode:
            text_x = icon_rect.right() + 43
        else:
            text_x = icon_rect.right() + 15
        text_y = self._calculate_text_start_y(option_rect, index)
        available_width = option_rect.right() - text_x - self.horizontal_padding

        # Title
        font_title, _ = self._get_style("delegate_title")
        title_height = QFontMetrics(font_title).height()
        text_y += title_height + self.line_spacing

        # Author
        if author:
            font_author, _ = self._get_style("delegate_author")
            author_height = QFontMetrics(font_author).height()
            text_y += author_height + self.line_spacing

        # Narrator
        if narrator:
            font_narrator, _ = self._get_style("delegate_narrator")
            narrator_height = QFontMetrics(font_narrator).height()
            text_y += narrator_height + self.line_spacing

        # Status info line (Files, Duration, Progress)
        info_parts = self._get_info_parts(
            progress_percent, file_count, duration, total_size,
            b_min, b_max, b_mode, codec, container,
            year_written, year_recorded, language
        )

        if info_parts and getattr(self, "show_detailed_info", True):
            font_inf, _ = self._get_style("delegate_file_count")
            line_height = QFontMetrics(font_inf).height()
            text_y += line_height + self.line_spacing

        # Compute tag rects
        tag_rects = []
        tag_x = text_x
        font_tag, _ = self._get_style("delegate_info_font")
        fm = QFontMetrics(font_tag)
        t_h = fm.height() + 4

        for tag in tags:
            tag_name = tag["name"]
            t_w = fm.horizontalAdvance(tag_name)
            tag_rect = QRectF(
                float(tag_x), float(text_y), float(t_w + 12), float(t_h)
            )

            # Check for overflow
            if tag_rect.right() > option_rect.right() - 10:
                break

            tag_rects.append((tag, tag_rect))
            tag_x += tag_rect.width() + 6

        return tag_rects


class LibraryTree(QTreeWidget):
    """Customized tree widget that handles hover detection and direct interaction with audiobook 'Play' buttons"""

    play_button_clicked = pyqtSignal(
        str
    )  # Emits the relative path to the selected audiobook
    favorite_clicked = pyqtSignal(str)  # Emits path when heart is clicked
    description_requested = pyqtSignal(str)  # Emits path when info icon is clicked
    settings_requested = pyqtSignal()  # Emits when placeholder settings icon is clicked
    search_requested = pyqtSignal(str)  # Emits search string when author or narrator clicked
    tag_clicked = pyqtSignal(dict)  # Emits tag dict when tag is clicked

    def __init__(self, parent=None):
        """Enable mouse tracking for fine-grained hover effects on custom-painted items"""
        super().__init__(parent)
        self.setMouseTracking(True)
        self.has_any_content = (
            False  # Track if DB has any items regardless of current filter
        )
        self.mass_selection_mode = False
        self.selected_audiobook_paths = set()
        self._last_checked_item = None
        # When True, scrollTo() calls from Qt internals (focus changes, etc.) are ignored.
        # Set to True during context menu to prevent the list from jumping.
        self._suppress_scroll = False

    def _get_all_tree_items(self) -> list:
        """Traverse the tree to get all items in pre-order traversal (visual sequence)"""
        items = []
        def traverse(item):
            items.append(item)
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            traverse(root.child(i))
        return items

    def scrollTo(self, index, hint=QTreeWidget.ScrollHint.EnsureVisible):
        """Block automatic scroll-to-current triggered by Qt focus changes during menu display"""
        if self._suppress_scroll:
            return
        super().scrollTo(index, hint)

    def wheelEvent(self, event):
        """Override wheel event to scroll by single row instead of multiple rows"""
        delta = event.angleDelta().y()

        if delta == 0:
            return

        # Get the topmost visible item
        viewport_rect = self.viewport().rect()
        top_index = self.indexAt(viewport_rect.topLeft())

        if not top_index.isValid():
            # Fallback to default behavior if no valid index
            super().wheelEvent(event)
            return

        # Determine scroll direction and get next/previous index
        if delta > 0:  # scroll up
            target_index = self.indexAbove(top_index)
        else:  # scroll down
            target_index = self.indexBelow(top_index)

        # Scroll to the target index if valid
        if target_index.isValid():
            self.scrollTo(target_index, QTreeWidget.ScrollHint.PositionAtTop)

        event.accept()

    def paintEvent(self, event):
        """Paint the tree or the placeholder if empty"""
        # If the model is empty (topLevelItemCount == 0), draw the placeholder.
        # But we must be careful: if we are Filtering, and no results, we might want a "No results" placeholder instead?
        # For now, let's stick to the request: "when list is empty".
        # We can check if topLevelItemCount is 0.

        if self.topLevelItemCount() == 0 and not self.has_any_content:
            painter = QPainter(self.viewport())
            draw_library_placeholder(painter, self.viewport().rect())
        else:
            super().paintEvent(event)

    def leaveEvent(self, event):
        """Clear hover state in the delegate when the mouse leaves the widget viewport"""
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, "hovered_index"):
            delegate.hovered_index = None
            if hasattr(delegate, "hovered_field"):
                delegate.hovered_field = None
            delegate.mouse_pos = None
            self.viewport().update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Track mouse position to detect hover over specialized UI elements like playback buttons"""
        super().mouseMoveEvent(event)

        # Check placeholder hover
        if self.topLevelItemCount() == 0 and not self.has_any_content:
            rect = get_placeholder_folder_rect(self.viewport().rect())
            if rect.contains(QPointF(event.pos())):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return

        index = self.indexAt(event.pos())

        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, "get_play_button_rect"):
            delegate.hovered_index = index if index.isValid() else None
            if hasattr(delegate, "hovered_field"):
                delegate.hovered_field = None
            delegate.mouse_pos = event.pos()

            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                rect = self.visualRect(index)
                icon_rect = delegate.get_icon_rect(rect, index)
                
                # Check checkbox hover first for both folders and audiobooks
                if self.mass_selection_mode and hasattr(delegate, "get_checkbox_rect"):
                    cb_rect = delegate.get_checkbox_rect(QRectF(icon_rect))
                    if cb_rect.contains(QPointF(event.pos())):
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.viewport().update()
                        return

                if item_type == "audiobook":
                    play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                    if play_rect.contains(QPointF(event.pos())):
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.viewport().update()
                        return

                    # Check heart hover
                    has_fav_data = False
                    status_data = index.data(Qt.ItemDataRole.UserRole + 3)
                    if status_data and len(status_data) >= 3:
                        if status_data[2]:  # is_favorite
                            has_fav_data = True

                    if has_fav_data:
                        heart_rect = delegate.get_heart_rect(QRectF(icon_rect))
                        if heart_rect.contains(QPointF(event.pos())):
                            self.setCursor(Qt.CursorShape.PointingHandCursor)
                            self.viewport().update()
                            return

                    # Check info hover
                    data = index.data(Qt.ItemDataRole.UserRole + 2)
                    description = data[12] if data and len(data) > 12 else ""
                    if description:
                        info_rect = delegate.get_info_rect(QRectF(icon_rect))
                        if info_rect.contains(QPointF(event.pos())):
                            self.setCursor(Qt.CursorShape.PointingHandCursor)
                            self.viewport().update()
                            return

                    # Check author hover
                    author_rect = delegate.get_author_rect(rect, index)
                    if not author_rect.isEmpty() and author_rect.contains(event.pos()):
                        delegate.hovered_field = "author"
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.viewport().update()
                        return

                    # Check narrator hover
                    narrator_rect = delegate.get_narrator_rect(rect, index)
                    if not narrator_rect.isEmpty() and narrator_rect.contains(event.pos()):
                        delegate.hovered_field = "narrator"
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.viewport().update()
                        return

                    # Check tags hover
                    if hasattr(delegate, "get_tags_rects"):
                        tags_rects = delegate.get_tags_rects(rect, index)
                        for tag, tag_rect in tags_rects:
                            if tag_rect.contains(QPointF(event.pos())):
                                delegate.hovered_field = f"tag:{tag['id']}"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                                self.viewport().update()
                                return

            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.viewport().update()

    def mousePressEvent(self, event):
        """Identify clicks on the custom 'Play' button to initiate playback without selecting the item"""
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.pos())
            print(f"[DEBUG RIGHT CLICK] Mouse right click event at {event.pos()}. Item: {item.text(0) if item else 'None'} | Path: {item.data(0, Qt.ItemDataRole.UserRole) if item else 'None'}", flush=True)
        if event.button() == Qt.MouseButton.LeftButton:
            # Check placeholder click
            if self.topLevelItemCount() == 0 and not self.has_any_content:
                rect = get_placeholder_folder_rect(self.viewport().rect())
                if rect.contains(QPointF(event.pos())):
                    self.settings_requested.emit()
                    return

            index = self.indexAt(event.pos())
            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                delegate = self.itemDelegate()
                if delegate and hasattr(delegate, "get_play_button_rect"):
                    rect = self.visualRect(index)
                    icon_rect = delegate.get_icon_rect(rect, index)
                    
                    # Check checkbox click first in mass selection mode
                    if self.mass_selection_mode and hasattr(delegate, "get_checkbox_rect"):
                        cb_rect = delegate.get_checkbox_rect(QRectF(icon_rect))
                        
                        should_toggle = False
                        if cb_rect.contains(QPointF(event.pos())):
                            should_toggle = True
                        elif rect.contains(event.pos()):
                            is_interactive = False
                            if item_type == "audiobook":
                                play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                                if play_rect.contains(QPointF(event.pos())):
                                    is_interactive = True
                                
                                status_data = index.data(Qt.ItemDataRole.UserRole + 3)
                                is_favorite = status_data[2] if status_data and len(status_data) >= 3 else False
                                if is_favorite:
                                    heart_rect = delegate.get_heart_rect(QRectF(icon_rect))
                                    if heart_rect.contains(QPointF(event.pos())):
                                        is_interactive = True
                                
                                data = index.data(Qt.ItemDataRole.UserRole + 2)
                                description = data[12] if data and len(data) > 12 else ""
                                if description:
                                    info_rect = delegate.get_info_rect(QRectF(icon_rect))
                                    if info_rect.contains(QPointF(event.pos())):
                                        is_interactive = True
                            if not is_interactive:
                                should_toggle = True
                                
                        if should_toggle:
                            path = index.data(Qt.ItemDataRole.UserRole)
                            item = self.itemFromIndex(index)
                            if item:
                                is_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                                if is_shift and getattr(self, "_last_checked_item", None) is not None:
                                    last_item = self._last_checked_item
                                    all_items = self._get_all_tree_items()
                                    if last_item in all_items and item in all_items:
                                        idx1 = all_items.index(last_item)
                                        idx2 = all_items.index(item)
                                        start_idx = min(idx1, idx2)
                                        end_idx = max(idx1, idx2)
                                        
                                        # Target state is the opposite of current item's selection status
                                        is_currently_checked = path in self.selected_audiobook_paths
                                        target_checked_state = not is_currently_checked
                                        
                                        for i in range(start_idx, end_idx + 1):
                                            range_item = all_items[i]
                                            range_path = range_item.data(0, Qt.ItemDataRole.UserRole)
                                            range_item_type = range_item.data(0, Qt.ItemDataRole.UserRole + 1)
                                            if range_path:
                                                if range_item_type == "folder":
                                                    self._set_item_selected_recursive(range_item, target_checked_state)
                                                else:
                                                    if target_checked_state:
                                                        self.selected_audiobook_paths.add(range_path)
                                                    else:
                                                        self.selected_audiobook_paths.discard(range_path)
                                        
                                        self._sync_all_folder_checkbox_states()
                                        self._last_checked_item = item
                                        self.viewport().update()
                                        return
                                
                                # Regular click (no Shift or no last clicked item)
                                is_checked = path in self.selected_audiobook_paths
                                if item_type == "folder":
                                    self._set_item_selected_recursive(item, not is_checked)
                                    self._update_parent_checkbox_states(item)
                                else:
                                    if is_checked:
                                        self.selected_audiobook_paths.discard(path)
                                    else:
                                        self.selected_audiobook_paths.add(path)
                                    self._update_parent_checkbox_states(item)
                                
                                self._last_checked_item = item
                            self.viewport().update()
                            return

                    if item_type == "audiobook":
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
                                # Defer callback to avoid modifying the tree while in event handler (prevents crash)
                                QTimer.singleShot(
                                    0, lambda p=path: self._emit_favorite_clicked(p)
                                )
                                event.accept()
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

                        # Check author click
                        author_rect = delegate.get_author_rect(rect, index)
                        if not author_rect.isEmpty() and author_rect.contains(event.pos()):
                            author = data[0]
                            if author:
                                self.search_requested.emit(author)
                                return

                        # Check narrator click
                        narrator_rect = delegate.get_narrator_rect(rect, index)
                        if not narrator_rect.isEmpty() and narrator_rect.contains(event.pos()):
                            narrator = data[2]
                            if narrator:
                                self.search_requested.emit(narrator)
                                return

                        # Check tag click
                        if hasattr(delegate, "get_tags_rects"):
                            tags_rects = delegate.get_tags_rects(rect, index)
                            for tag, tag_rect in tags_rects:
                                if tag_rect.contains(QPointF(event.pos())):
                                    self.tag_clicked.emit(tag)
                                    return
        super().mousePressEvent(event)

    def _emit_favorite_clicked(self, path):
        self.favorite_clicked.emit(path)

    def _set_item_selected_recursive(self, item: QTreeWidgetItem, select: bool):
        """Recursively select or deselect a tree item and all its children"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            if select:
                self.selected_audiobook_paths.add(path)
            else:
                self.selected_audiobook_paths.discard(path)
        
        # Recursively select/deselect all children
        for i in range(item.childCount()):
            child = item.child(i)
            self._set_item_selected_recursive(child, select)

    def _update_parent_checkbox_states(self, item: QTreeWidgetItem):
        """Walk up the tree and update the checked state of parent folders based on their children's checked states."""
        parent = item.parent()
        if not parent:
            return
        
        # Check if all children of the parent are in selected_audiobook_paths
        all_children_selected = True
        for i in range(parent.childCount()):
            child = parent.child(i)
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path not in self.selected_audiobook_paths:
                all_children_selected = False
                break
        
        parent_path = parent.data(0, Qt.ItemDataRole.UserRole)
        if parent_path:
            if all_children_selected:
                self.selected_audiobook_paths.add(parent_path)
            else:
                self.selected_audiobook_paths.discard(parent_path)
        
        # Continue walking up the tree
        self._update_parent_checkbox_states(parent)

    def _sync_all_folder_checkbox_states(self):
        """Traverse the tree bottom-up to sync folder checkbox states with their children."""
        def sync_item(item):
            # First sync children recursively (post-order traversal)
            for i in range(item.childCount()):
                sync_item(item.child(i))
            
            # Now sync this item if it is a folder
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "folder":
                folder_path = item.data(0, Qt.ItemDataRole.UserRole)
                if folder_path:
                    has_children = item.childCount() > 0
                    all_selected = True
                    for i in range(item.childCount()):
                        child = item.child(i)
                        child_path = child.data(0, Qt.ItemDataRole.UserRole)
                        if child_path not in self.selected_audiobook_paths:
                            all_selected = False
                            break
                    if has_children and all_selected:
                        self.selected_audiobook_paths.add(folder_path)
                    else:
                        self.selected_audiobook_paths.discard(folder_path)

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            sync_item(root.child(i))

    def focusInEvent(self, event):
        print(f"[DEBUG FOCUS] LibraryTree focusInEvent. FocusPolicy: {self.focusPolicy()}", flush=True)
        import traceback
        traceback.print_stack()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        print(f"[DEBUG FOCUS] LibraryTree focusOutEvent. FocusPolicy: {self.focusPolicy()}", flush=True)
        import traceback
        traceback.print_stack()
        super().focusOutEvent(event)

        super().changeEvent(event)


class WrapLayout(QLayout):
    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        print(f"[DEBUG WrapLayout] __init__ parent={parent}", flush=True)
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        print("[DEBUG WrapLayout] __del__ started", flush=True)
        if hasattr(self, "_items"):
            print(f"[DEBUG WrapLayout] __del__ items count: {len(self._items)}", flush=True)
            del self._items
        print("[DEBUG WrapLayout] __del__ finished", flush=True)

    def addItem(self, item):
        print(f"[DEBUG WrapLayout] addItem item={item}", flush=True)
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        print(f"[DEBUG WrapLayout] takeAt index={index}", flush=True)
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            print(f"[DEBUG WrapLayout] takeAt item={item} popped", flush=True)
            return item
        return None

    def expandingDirections(self):
        print("[DEBUG WrapLayout] expandingDirections called", flush=True)
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        print("[DEBUG WrapLayout] hasHeightForWidth called", flush=True)
        return True

    def heightForWidth(self, width):
        print(f"[DEBUG WrapLayout] heightForWidth called with width={width}", flush=True)
        res = self._do_layout(QRect(0, 0, width, 0), True)
        print(f"[DEBUG WrapLayout] heightForWidth returning {res}", flush=True)
        return res

    def setGeometry(self, rect):
        print(f"[DEBUG WrapLayout] setGeometry called with rect={rect}", flush=True)
        super().setGeometry(rect)
        self._do_layout(rect, False)
        print("[DEBUG WrapLayout] setGeometry finished", flush=True)

    def sizeHint(self):
        print("[DEBUG WrapLayout] sizeHint called", flush=True)
        res = self.minimumSize()
        print(f"[DEBUG WrapLayout] sizeHint returning {res}", flush=True)
        return res

    def minimumSize(self):
        print(f"[DEBUG WrapLayout] minimumSize started, items count={len(self._items)}", flush=True)
        size = QSize()
        for i, item in enumerate(self._items):
            widget = item.widget()
            if widget and widget.isHidden():
                continue
            print(f"[DEBUG WrapLayout] minimumSize checking item {i}: {item}", flush=True)
            min_sz = item.minimumSize()
            print(f"[DEBUG WrapLayout] minimumSize item {i} min size={min_sz}", flush=True)
            size = size.expandedTo(min_sz)
        margins = self.contentsMargins()
        print("[DEBUG WrapLayout] minimumSize margins calculation", flush=True)
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        print(f"[DEBUG WrapLayout] minimumSize returning {size}", flush=True)
        return size

    def _do_layout(self, rect, test_only):
        try:
            margins = self.contentsMargins()
            effective_rect = rect.adjusted(+margins.left(), +margins.top(), -margins.right(), -margins.bottom())
            x = effective_rect.x()
            y = effective_rect.y()
            line_height = 0

            for item in self._items:
                widget = item.widget()
                if not widget:
                    continue
                if widget.isHidden():
                    continue
                
                space_x = self._hspacing
                space_y = self._vspacing
                if space_x == -1:
                    space_x = widget.style().layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Horizontal)
                if space_y == -1:
                    space_y = widget.style().layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Vertical)

                next_x = x + item.sizeHint().width() + space_x
                if next_x - space_x > effective_rect.right() and line_height > 0:
                    x = effective_rect.x()
                    y = y + line_height + space_y
                    next_x = x + item.sizeHint().width() + space_x
                    line_height = 0

                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

                x = next_x
                line_height = max(line_height, item.sizeHint().height())

            return y + line_height - effective_rect.y() + margins.top() + margins.bottom()
        except Exception as e:
            print(f"[DEBUG WrapLayout ERROR in _do_layout]: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise e



class BookTileWidget(QWidget):
    clicked = pyqtSignal(str)
    double_clicked = pyqtSignal(str)
    play_clicked = pyqtSignal(str)
    context_menu_requested = pyqtSignal(str, QPoint)
    favorite_clicked = pyqtSignal(str)
    description_requested = pyqtSignal(str)

    def __init__(self, path, title, author, narrator, progress_percent, is_started, is_completed, is_favorite, description, pixmap, icon_size, parent=None):
        super().__init__(parent)
        self.path = path if path is not None else ""
        self.title = title if title is not None else ""
        self.author = author if author is not None else ""
        self.narrator = narrator if narrator is not None else ""
        self.progress_percent = progress_percent if progress_percent is not None else 0.0
        self.is_started = bool(is_started)
        self.is_completed = bool(is_completed)
        self.is_favorite = bool(is_favorite)
        self.description = description if description is not None else ""
        self.pixmap = pixmap
        self.icon_size = icon_size
        self.is_playing = False
        self.is_paused = True
        self.selected = False
        
        self.setObjectName("bookTile")
        self.setMouseTracking(True)
        
        self.padding = 8
        self.title_area_height = 85
        self.width_val = self.icon_size + self.padding * 2
        self.height_val = self.icon_size + self.padding * 2 + self.title_area_height
        self.setFixedSize(self.width_val, self.height_val)
        
        self.hovered = False
        self.hovered_field = None
        
        self.play_icon = get_icon("play")
        self.pause_icon = get_icon("pause")
        self.info_icon = get_icon("info_duration")
        self.author_icon = get_icon("author")
        self.narrator_icon = get_icon("narrator")
        
        self.update_texts()

    def update_texts(self):
        self.setToolTip("")

    def set_playing(self, is_playing, is_paused):
        self.is_playing = is_playing
        self.is_paused = is_paused
        self.update()

    def setSelected(self, selected):
        self.selected = selected
        self.setProperty("selected", selected)
        self.style().polish(self)
        self.update()

    def get_icon_rect(self):
        return QRect(self.padding, self.padding, self.icon_size, self.icon_size)

    def get_play_button_rect(self, icon_rect):
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(center.x() - btn_size / 2.0, center.y() - btn_size / 2.0, btn_size, btn_size)

    def get_heart_rect(self, icon_rect):
        size = 20.0
        # Position: Top-Right of icon, adjusted to stay inside tile widget boundary (padding is 4)
        return QRectF(
            float(icon_rect.right() - size + 4),
            float(icon_rect.top() - 4),
            float(size),
            float(size),
        )

    def get_info_rect(self, icon_rect):
        size = 20
        return QRect(icon_rect.right() - size - 4, icon_rect.bottom() - size - 4, size, size)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        
        icon_rect = self.get_icon_rect()
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(icon_rect, self.pixmap)
        p.restore()
        
        if self.hovered:
            _, overlay_bg = StyleManager.get_theme_property("overlay_background")
            if not overlay_bg:
                overlay_bg = QColor(0, 0, 0, 80)
            p.save()
            p.setClipPath(path)
            p.fillRect(icon_rect, overlay_bg)
            p.restore()
            
        # Draw status triangle (New / Started / Finished)
        if self.is_completed:
            _, status_color = StyleManager.get_theme_property("delegate_status_completed")
            if not status_color or not status_color.isValid() or status_color == QColor():
                status_color = QColor("#4ecca3")
        elif self.is_started:
            _, status_color = StyleManager.get_theme_property("delegate_status_started")
            if not status_color or not status_color.isValid() or status_color == QColor():
                status_color = QColor("#f9ca24")
        else:
            _, status_color = StyleManager.get_theme_property("delegate_status_new")
            if not status_color or not status_color.isValid() or status_color == QColor():
                status_color = QColor("#ff6b6b")

        tri_size = icon_rect.width() * 0.25
        tri_path = QPainterPath()
        tri_path.moveTo(float(icon_rect.left()), float(icon_rect.top()))
        tri_path.lineTo(float(icon_rect.left() + tri_size), float(icon_rect.top()))
        tri_path.lineTo(float(icon_rect.left()), float(icon_rect.top() + tri_size))
        tri_path.closeSubpath()

        p.save()
        p.setClipPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(status_color))
        p.drawPath(tri_path)
        p.restore()

        pb_y = icon_rect.bottom()
        pb_h = 5

        # 4. Currently Playing Highlight Border
        if self.is_playing:
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            p.save()
            pen = QPen(accent_color, 8)
            p.setPen(pen)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            has_progress = (self.progress_percent > 0 or self.is_started)
            if has_progress:
                highlight_rect = QRectF(
                    float(icon_rect.left()),
                    float(icon_rect.top()),
                    float(icon_rect.width()),
                    float(pb_y + pb_h - icon_rect.top()),
                )
            else:
                highlight_rect = QRectF(icon_rect)
                
            p.drawRoundedRect(highlight_rect.adjusted(-4, -4, 4, 4), 7, 7)
            p.restore()

        if self.hovered or self.is_playing:
            play_rect = self.get_play_button_rect(icon_rect)
            is_play_hovered = (self.hovered_field == "play")
            
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Button circle
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            btn_color = accent_color
            if not is_play_hovered:
                btn_color.setAlpha(200)
            else:
                btn_color = btn_color.lighter(110)

            p.setBrush(btn_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(play_rect)

            # Play/Pause Icon shapes
            p.setBrush(Qt.GlobalColor.white)
            if self.is_playing and not self.is_paused:
                # Draw Pause bars
                w = play_rect.width() // 5
                h = play_rect.height() // 2
                gap = w // 2

                total_w = w * 2 + gap
                start_x = (
                    play_rect.left() + (play_rect.width() - total_w) // 2
                )
                start_y = play_rect.top() + (play_rect.height() - h) // 2

                p.drawRect(QRectF(start_x, start_y, w, h))
                p.drawRect(QRectF(start_x + w + gap, start_y, w, h))
            else:
                # Draw Play triangle
                side = play_rect.width() // 2
                center_f = QPointF(play_rect.center())

                # Optical balancing adjustment
                h_offset = play_rect.width() / 20.0

                tri_path = QPainterPath()
                tri_path.moveTo(
                    center_f.x() - side / 3.0 + h_offset, center_f.y() - side / 2.0
                )
                tri_path.lineTo(
                    center_f.x() - side / 3.0 + h_offset, center_f.y() + side / 2.0
                )
                tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                tri_path.closeSubpath()

                p.fillPath(tri_path, Qt.GlobalColor.white)

            p.restore()

        if self.is_favorite:
            heart_rect = self.get_heart_rect(icon_rect)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_over_heart = (self.hovered_field == "heart")

            # Draw circle background
            prop = "icon_background_hover" if is_over_heart else "icon_background"
            _, bg_color = StyleManager.get_theme_property(prop)
            if not bg_color or not bg_color.isValid() or bg_color == QColor():
                bg_color = QColor(0, 0, 0, 150)
            p.setBrush(bg_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(heart_rect)

            # Draw Heart Shape
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color or not accent_color.isValid() or accent_color == QColor():
                accent_color = QColor("#018574")
            p.setBrush(accent_color)
            
            # Make the heart wider by reducing horizontal padding
            hr = heart_rect.adjusted(1, 2, -1, -3)

            path = QPainterPath()
            path.moveTo(hr.center().x(), hr.bottom())
            path.cubicTo(
                hr.right(),
                hr.center().y(),
                hr.right(),
                hr.top(),
                hr.center().x(),
                hr.top() + hr.height() * 0.2,
            )
            path.cubicTo(
                hr.left(),
                hr.top(),
                hr.left(),
                hr.center().y(),
                hr.center().x(),
                hr.bottom(),
            )

            p.drawPath(path)
            p.drawPath(path)
            p.restore()

        if self.hovered and self.description:
            info_rect = self.get_info_rect(icon_rect)
            p.save()
            pix = self.info_icon.pixmap(info_rect.size())
            p.drawPixmap(info_rect, pix)
            p.restore()

        pb_x = icon_rect.left()
        pb_w = icon_rect.width()
        
        _, border_color = StyleManager.get_theme_property("overlay_progress_bg")
        if not border_color:
            border_color = QColor("#444444")
        _, accent_color = StyleManager.get_theme_property("theme_primary")
        if not accent_color:
            accent_color = QColor("#3498db")
            
        if self.progress_percent > 0 or self.is_started:
            p.save()
            pb_rect = QRectF(float(pb_x), float(pb_y), float(pb_w), float(pb_h))
            
            # Background
            p.fillRect(pb_rect, border_color)
            
            # Fill
            if self.progress_percent > 0:
                fill_w = pb_rect.width() * self.progress_percent / 100.0
                if fill_w > 0:
                    fill_rect = QRectF(pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height())
                    p.fillRect(fill_rect, accent_color)
            p.restore()
        
        # Draw metadata block below cover
        text_y = self.icon_size + self.padding + 12
        available_width = self.width_val - self.padding * 2
        
        # 1. Title
        title_height = 0
        if self.title:
            p.save()
            font, color = StyleManager.get_theme_property("delegate_title")
            if font:
                font = QFont(font)
                font.setPixelSize(13)
                p.setFont(font)
            if color and color.isValid():
                p.setPen(color)
            else:
                p.setPen(QColor("#e0e0e0"))
            
            fm = p.fontMetrics()
            elided_title = fm.elidedText(self.title, Qt.TextElideMode.ElideRight, available_width * 2)
            
            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                elided_title
            )
            title_height = min(title_bound.height(), fm.height() * 2)
            
            title_rect = QRect(
                self.padding,
                text_y,
                available_width,
                title_height
            )
            p.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                elided_title
            )
            p.restore()
            text_y += title_height + 4
            
        # 2. Author
        if self.author:
            p.save()
            font, color = StyleManager.get_theme_property("delegate_author")
            if font:
                font = QFont(font)
                font.setPixelSize(11)
                p.setFont(font)
            if color and color.isValid():
                p.setPen(color)
            else:
                p.setPen(QColor("#a0a0a0"))
            
            fm = p.fontMetrics()
            
            author_x = self.padding
            if self.author_icon and not self.author_icon.isNull():
                author_icon_size = 14
                author_icon_y = text_y + (fm.height() - author_icon_size) // 2
                author_icon_rect = QRect(self.padding, author_icon_y, author_icon_size, author_icon_size)
                
                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.author_icon.paint(p, author_icon_rect)
                p.restore()
                
                author_x += author_icon_size + 3
                
            elided_author = fm.elidedText(self.author, Qt.TextElideMode.ElideRight, available_width - (author_x - self.padding))
            
            author_rect = QRect(
                author_x,
                text_y,
                available_width - (author_x - self.padding),
                fm.height()
            )
            p.drawText(
                author_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_author
            )
            p.restore()
            text_y += fm.height() + 2
            
        # 3. Narrator
        if self.narrator:
            p.save()
            font, color = StyleManager.get_theme_property("delegate_narrator")
            if font:
                font = QFont(font)
                font.setPixelSize(11)
                p.setFont(font)
            if color and color.isValid():
                p.setPen(color)
            else:
                p.setPen(QColor("#808080"))
            
            fm = p.fontMetrics()
            
            narrator_x = self.padding
            if self.narrator_icon and not self.narrator_icon.isNull():
                narrator_icon_size = 14
                narrator_icon_y = text_y + (fm.height() - narrator_icon_size) // 2
                narrator_icon_rect = QRect(self.padding, narrator_icon_y, narrator_icon_size, narrator_icon_size)
                
                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.narrator_icon.paint(p, narrator_icon_rect)
                p.restore()
                
                narrator_x += narrator_icon_size + 3
                
            elided_narrator = fm.elidedText(self.narrator, Qt.TextElideMode.ElideRight, available_width - (narrator_x - self.padding))
            
            narrator_rect = QRect(
                narrator_x,
                text_y,
                available_width - (narrator_x - self.padding),
                fm.height()
            )
            p.drawText(
                narrator_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_narrator
            )
            p.restore()
        
        p.end()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        icon_rect = self.get_icon_rect()
        old_hovered_field = self.hovered_field
        
        play_rect = self.get_play_button_rect(icon_rect)
        heart_rect = self.get_heart_rect(icon_rect)
        info_rect = self.get_info_rect(icon_rect)
        
        self.hovered = True
        is_over_heart = self.is_favorite and heart_rect.contains(QPointF(pos))
        is_over_info = bool(self.description) and info_rect.contains(QPointF(pos))
        
        if play_rect.contains(QPointF(pos)):
            self.hovered_field = "play"
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif is_over_heart:
            self.hovered_field = "heart"
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif is_over_info:
            self.hovered_field = "info"
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.hovered_field = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
        if self.hovered_field != old_hovered_field:
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.hovered_field = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            icon_rect = self.get_icon_rect()
            pos = event.position().toPoint()
            
            if self.hovered_field == "play":
                self.play_clicked.emit(self.path)
                event.accept()
                return
            elif self.hovered_field == "heart":
                self.favorite_clicked.emit(self.path)
                event.accept()
                return
            elif self.hovered_field == "info":
                self.description_requested.emit(self.path)
                event.accept()
                return
            
            if self.rect().contains(pos):
                self.clicked.emit(self.path)
                event.accept()
                return
                
            super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.path, event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.path)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class FolderBranchIndicator(QWidget):
    def __init__(self, expanded=True, parent=None):
        super().__init__(parent)
        self.expanded = expanded
        self.setFixedSize(12, 12)
        
    def set_expanded(self, expanded):
        if self.expanded != expanded:
            self.expanded = expanded
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        opt = QStyleOption()
        opt.initFrom(self)
        opt.rect = self.rect()
        
        # State flags matching branch indicator
        opt.state = QStyle.StateFlag.State_Enabled
        if self.expanded:
            opt.state |= QStyle.StateFlag.State_Open
            
        pe = QStyle.PrimitiveElement.PE_IndicatorArrowDown if self.expanded else QStyle.PrimitiveElement.PE_IndicatorArrowRight
        self.style().drawPrimitive(pe, opt, painter, self)


class FolderHeaderWidget(QWidget):
    toggled = pyqtSignal(str, bool)

    def __init__(self, path, display_name, depth, chain, is_last_child, is_expanded=True, parent=None):
        super().__init__(parent)
        self.path = path
        self.display_name = display_name
        self.depth = depth
        self.chain = chain
        self.is_last_child = is_last_child
        self.expanded = is_expanded
        self.is_active = False
        self.hovered = False
        
        self.setObjectName("FolderHeader")
        
        library = self.window().findChild(LibraryWidget)
        row_height = 35
        if library and hasattr(library, "delegate") and library.delegate:
            row_height = library.delegate.folder_row_height
        self.setFixedHeight(row_height)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(0)
        
        # 1. Left indent spacer
        if depth > 0:
            layout.addSpacing(depth * 12)
            
        # 2. Branch arrow widget
        self.arrow_widget = FolderBranchIndicator(self.expanded, self)
        layout.addWidget(self.arrow_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 3. Spacing between arrow column and folder icon
        layout.addSpacing(15)
        
        # 4. Folder icon label
        self.icon_label = QLabel()
        self.icon_label.setObjectName("FolderHeaderIcon")
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setScaledContents(True)
        if library and library.folder_icon:
            self.icon_label.setPixmap(library.folder_icon.pixmap(20, 20))
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 5. Spacing between icon and title text
        layout.addSpacing(8)
        
        # 6. Title label
        self.title_label = QLabel(self.display_name)
        self.title_label.setObjectName("FolderHeaderTitle")
        font, color = StyleManager.get_theme_property("delegate_folder")
        if font:
            self.title_label.setFont(font)
        if color:
            palette = self.title_label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, color)
            self.title_label.setPalette(palette)
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        layout.addStretch(1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, is_active):
        if self.is_active != is_active:
            self.is_active = is_active
            self.update()

    def update_arrow_icon(self):
        if hasattr(self, "arrow_widget"):
            self.arrow_widget.set_expanded(self.expanded)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.expanded = not self.expanded
            self.update_arrow_icon()
            self.toggled.emit(self.path, self.expanded)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Draw hover background
        if self.hovered:
            _, text_color = StyleManager.get_theme_property("delegate_folder")
            if text_color:
                hover_color = QColor(text_color.red(), text_color.green(), text_color.blue(), 15)
            else:
                hover_color = QColor(255, 255, 255, 10)
            p.fillRect(self.rect(), hover_color)
            
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        
        indent = 12
        line_width = 2
        
        library = self.window().findChild(LibraryWidget)
        show_nesting = getattr(library, "show_nesting_lines", True) if library else True
        
        if show_nesting:
            # Draw nesting lines
            for i in range(self.depth):
                if i >= len(self.chain):
                    continue
                parent_path_str, _ = self.chain[i]
                
                # If ancestor line already ended in previous folder, skip it for descendants
                if i < self.depth - 1:
                    child_is_last = self.chain[i + 1][1]
                    if child_is_last:
                        continue
                        
                path_hash = zlib.adler32(parent_path_str.encode("utf-8", errors="ignore"))
                color_index = path_hash % len(NESTING_COLORS)
                color = NESTING_COLORS[color_index]
                
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)
                
                line_x = 12 + i * indent
                
                if i == self.depth - 1:
                    # This is the folder's own nesting line/branch
                    if self.is_last_child:
                        # └ pattern
                        v_end = self.height() if self.expanded else (self.height() // 2 + line_width // 2)
                        p.drawRect(
                            QRect(
                                line_x,
                                0,
                                line_width,
                                v_end,
                            )
                        )
                        p.drawRect(
                            QRect(
                                line_x,
                                (self.height() - line_width) // 2,
                                indent,
                                line_width,
                            )
                        )
                    else:
                        # ├ pattern
                        p.drawRect(
                            QRect(line_x, 0, line_width, self.height())
                        )
                        p.drawRect(
                            QRect(
                                line_x,
                                (self.height() - line_width) // 2,
                                indent,
                                line_width,
                            )
                        )
                else:
                    # Regular full vertical line for parent levels
                    p.drawRect(QRect(line_x, 0, line_width, self.height()))
            
        # Draw active folder indicator
        if self.is_active:
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent_color)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            bar_x = self.depth * indent + 14
            bar_rect = QRectF(
                float(bar_x),
                4.0,
                3.0,
                float(self.height() - 8),
            )
            p.drawRoundedRect(bar_rect, 2.0, 2.0)
            
        # Draw horizontal line at bottom for expanded folder
        if show_nesting and self.expanded and self.depth >= 0:
            if self.path:
                path_hash = zlib.adler32(str(self.path).encode("utf-8", errors="ignore"))
                color_index = path_hash % len(NESTING_COLORS)
                line_color = NESTING_COLORS[color_index]
                
                p.setPen(QPen(line_color, line_width))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                
                start_x = 0
                if self.depth > 0:
                    gap = 4
                    start_x = self.depth * indent + 12 + line_width + gap
                
                y_pos = self.height() - 1
                p.drawLine(start_x, y_pos, self.width(), y_pos)
                
        p.end()


class BooksContainerWidget(QWidget):
    def __init__(self, chain, depth, parent=None):
        super().__init__(parent)
        self.chain = chain
        self.depth = depth
        self.setContentsMargins(depth * 12 + 12, 4, 0, 4)
        
    def paintEvent(self, event):
        library = self.window().findChild(LibraryWidget)
        show_nesting = getattr(library, "show_nesting_lines", True) if library else True
        if not show_nesting:
            return
            
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        indent = 12
        line_width = 2
        
        for i in range(self.depth):
            if i >= len(self.chain):
                continue
            parent_path_str, _ = self.chain[i]
            
            # If ancestor line already ended, skip it
            if i < self.depth - 1:
                child_is_last = self.chain[i + 1][1]
                if child_is_last:
                    continue
                    
            path_hash = zlib.adler32(parent_path_str.encode("utf-8", errors="ignore"))
            color_index = path_hash % len(NESTING_COLORS)
            color = NESTING_COLORS[color_index]
            
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            
            line_x = 12 + i * indent
            p.drawRect(QRect(line_x, 0, line_width, self.height()))
            
        p.end()


class FolderGroup:
    def __init__(self, path, header, books_container, parent=None):
        self.path = path
        self.header = header
        self.books_container = books_container
        self.parent = parent
        self.expanded = True
        self.child_groups = []
        self.books = []


class TileFlowWidget(QScrollArea):
    def __init__(self, parent_library, parent=None):
        super().__init__(parent)
        self.parent_library = parent_library
        self.config = parent_library.config
        
        self.setObjectName("libraryTileView")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        self.container = QWidget()
        self.container.setObjectName("libraryTileViewContainer")
        
        self._layout = QVBoxLayout(self.container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(0)
        
        self.setWidget(self.container)
        self.root_group = None

    def clear(self):
        print("[DEBUG TileFlowWidget] clear started", flush=True)
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.root_group = None
        print("[DEBUG TileFlowWidget] clear finished", flush=True)

    def populate(self, tree_root_item):
        print("[DEBUG TileFlowWidget] populate started", flush=True)
        self.clear()
        
        print("[DEBUG TileFlowWidget] Creating FolderGroup", flush=True)
        self.root_group = FolderGroup(path="", header=None, books_container=BooksContainerWidget(chain=[], depth=0, parent=self), parent=None)
        print("[DEBUG TileFlowWidget] Creating WrapLayout for books_container", flush=True)
        self.root_group.books_container.setLayout(WrapLayout(margin=0, hspacing=6, vspacing=6))
        
        self._expanded_paths = self.parent_library._expanded_paths_cache
        
        print("[DEBUG TileFlowWidget] Building hierarchy...", flush=True)
        self._build_hierarchy(tree_root_item, self.root_group, depth=0)
        print("[DEBUG TileFlowWidget] Adding books_container to _layout", flush=True)
        self._layout.addWidget(self.root_group.books_container)
        print("[DEBUG TileFlowWidget] Hierarchy built. Adding stretch.", flush=True)
        self._layout.addStretch(1)
        self.update_visibility()
        # Restore active-book indicator after rebuilding all widgets
        playing_path = None
        if hasattr(self.parent_library, "delegate") and self.parent_library.delegate:
            playing_path = getattr(self.parent_library.delegate, "playing_path", None)
        if not playing_path and hasattr(self.parent_library, "current_playing_item") and self.parent_library.current_playing_item:
            try:
                playing_path = self.parent_library.current_playing_item.data(0, Qt.ItemDataRole.UserRole)
            except RuntimeError:
                pass
        is_paused = self.parent_library.delegate.is_paused if (hasattr(self.parent_library, "delegate") and self.parent_library.delegate) else True
        self.update_playback_state(playing_path, is_paused)

    def _build_hierarchy(self, tree_item, parent_group, depth):
        child_count = tree_item.childCount()
        print(f"[DEBUG TileFlowWidget] _build_hierarchy depth={depth} parent={parent_group.path} child_count={child_count}", flush=True)
        for i in range(child_count):
            child = tree_item.child(i)
            if child.isHidden():
                continue
                
            item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
            path = child.data(0, Qt.ItemDataRole.UserRole)
            print(f"[DEBUG TileFlowWidget] child {i} type={item_type} path={path}", flush=True)
            
            # Get nesting chain and is_last_child for child
            chain = get_item_nesting_chain(child)
            is_last_child = is_last_visible_child(child)

            if item_type == "folder":
                display_name = child.text(0)
                is_expanded = child.isExpanded()
                
                header = FolderHeaderWidget(
                    path=path,
                    display_name=display_name,
                    depth=depth,
                    chain=chain,
                    is_last_child=is_last_child,
                    is_expanded=is_expanded,
                    parent=self
                )
                header.toggled.connect(self.on_folder_toggled)
                
                # Initial active state — resolved after all tiles are built via update_playback_state()
                # (called at the end of populate(), so no need to compute it per-header here)
                
                self._layout.addWidget(header)
                
                books_chain = chain + [(path, is_last_child)]
                books_container = BooksContainerWidget(chain=books_chain, depth=depth + 1, parent=self)
                books_container.setLayout(WrapLayout(margin=0, hspacing=6, vspacing=6))
                self._layout.addWidget(books_container)
                
                group = FolderGroup(path, header, books_container, parent=parent_group)
                group.expanded = is_expanded
                parent_group.child_groups.append(group)
                
                self._build_hierarchy(child, group, depth + 1)
                
            elif item_type == "audiobook":
                tile = self._create_tile_for_item(child)
                parent_group.books.append(tile)
                parent_group.books_container.layout().addWidget(tile)

    def _create_tile_for_item(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        print(f"[DEBUG TileFlowWidget] _create_tile_for_item path={path}", flush=True)
        data = item.data(0, Qt.ItemDataRole.UserRole + 2) or ()
        status_data = item.data(0, Qt.ItemDataRole.UserRole + 3) or ()
        icon = item.data(0, Qt.ItemDataRole.DecorationRole)
        
        author = data[0] if len(data) > 0 and data[0] is not None else ""
        title = data[1] if len(data) > 1 and data[1] is not None else ""
        narrator = data[2] if len(data) > 2 and data[2] is not None else ""
        progress_percent = data[6] if len(data) > 6 and data[6] is not None else 0
        description = data[12] if len(data) > 12 and data[12] is not None else ""
        
        is_started = status_data[0] if len(status_data) > 0 and status_data[0] is not None else False
        is_completed = status_data[1] if len(status_data) > 1 and status_data[1] is not None else False
        is_favorite = status_data[2] if len(status_data) > 2 and status_data[2] is not None else False
        
        icon_size = int(self.config.get("audiobook_icon_size", 100) * 1.5)
        
        # High-DPI support: Load high-resolution cover from stored path
        dpr = self.devicePixelRatioF()
        physical_size = int(icon_size * dpr)
        cover_path = item.data(0, Qt.ItemDataRole.UserRole + 5)
        pixmap = None
        
        if cover_path:
            cover_p = Path(cover_path)
            if not cover_p.is_absolute() and self.config.get("default_path"):
                cover_p = Path(self.config.get("default_path")) / cover_p
            if cover_p.exists() and cover_p.is_file():
                tile_cover_icon = load_icon(cover_p, physical_size, force_square=True)
                if tile_cover_icon and not tile_cover_icon.isNull():
                    pixmap = tile_cover_icon.pixmap(QSize(physical_size, physical_size))
                    pixmap.setDevicePixelRatio(dpr)
                    
        # Fallback to default cover icon
        if pixmap is None or pixmap.isNull():
            default_cover = self.config.get("default_cover_file", "resources/icons/default_cover.png")
            default_cover_path = get_base_path() / default_cover
            if default_cover_path.exists() and default_cover_path.is_file():
                tile_cover_icon = load_icon(default_cover_path, physical_size, force_square=True)
                if tile_cover_icon and not tile_cover_icon.isNull():
                    pixmap = tile_cover_icon.pixmap(QSize(physical_size, physical_size))
                    pixmap.setDevicePixelRatio(dpr)
                    
        # Ultimate fallback
        if pixmap is None or pixmap.isNull():
            if self.parent_library.default_audiobook_icon and not self.parent_library.default_audiobook_icon.isNull():
                pixmap = self.parent_library.default_audiobook_icon.pixmap(QSize(physical_size, physical_size))
                pixmap.setDevicePixelRatio(dpr)
            else:
                pixmap = QPixmap(physical_size, physical_size)
                pixmap.fill(Qt.GlobalColor.transparent)
                pixmap.setDevicePixelRatio(dpr)
            
        tile = BookTileWidget(
            path=path,
            title=title,
            author=author,
            narrator=narrator,
            progress_percent=progress_percent,
            is_started=is_started,
            is_completed=is_completed,
            is_favorite=is_favorite,
            description=description,
            pixmap=pixmap,
            icon_size=icon_size,
            parent=self
        )
        
        playing_path = None
        if hasattr(self.parent_library, "delegate") and self.parent_library.delegate:
            playing_path = getattr(self.parent_library.delegate, "playing_path", None)
        if not playing_path and hasattr(self.parent_library, "current_playing_item") and self.parent_library.current_playing_item:
            playing_path = self.parent_library.current_playing_item.data(0, Qt.ItemDataRole.UserRole)
        
        is_playing = False
        if playing_path and path:
            is_playing = (str(playing_path).replace("\\", "/") == str(path).replace("\\", "/"))
            
        is_paused = getattr(self.parent_library, "is_paused", True)
        tile.set_playing(is_playing, is_paused)
        
        selected_paths = getattr(self.parent_library.tree, "selected_audiobook_paths", set())
        tile.setSelected(path in selected_paths)
        
        tile.clicked.connect(self.on_tile_clicked)
        tile.double_clicked.connect(self.on_tile_double_clicked)
        tile.play_clicked.connect(self.on_tile_play_clicked)
        tile.context_menu_requested.connect(self.on_tile_context_menu_requested)
        tile.favorite_clicked.connect(self.on_tile_favorite_clicked)
        tile.description_requested.connect(self.on_tile_description_requested)
        
        print(f"[DEBUG TileFlowWidget] _create_tile_for_item finished path={path}", flush=True)
        return tile

    def on_tile_play_clicked(self, path):
        self.parent_library.tree.play_button_clicked.emit(path)

    def on_tile_clicked(self, path):
        item = self.parent_library.find_item_by_path(self.parent_library.tree.invisibleRootItem(), path)
        if item:
            if getattr(self.parent_library.tree, "mass_selection_mode", False):
                self.parent_library.tree.toggle_item_selection_state(item)
                self.update_selection_state(self.parent_library.tree.selected_audiobook_paths)
            else:
                self.parent_library.tree.setCurrentItem(item)
                self.parent_library.audiobook_selected.emit(path)

    def on_tile_double_clicked(self, path):
        item = self.parent_library.find_item_by_path(self.parent_library.tree.invisibleRootItem(), path)
        if item:
            self.parent_library.on_item_double_clicked(item, 0)

    def on_tile_context_menu_requested(self, path, pos):
        item = self.parent_library.find_item_by_path(self.parent_library.tree.invisibleRootItem(), path)
        if item:
            tree_pos = self.parent_library.tree.viewport().mapFromGlobal(pos)
            self.parent_library.show_context_menu(tree_pos)

    def on_tile_favorite_clicked(self, path):
        info = self.parent_library.db.get_audiobook_info(path)
        if info:
            self.parent_library.toggle_favorite(info[0], path)
            self.refresh_tile(path)

    def on_tile_description_requested(self, path):
        item = self.parent_library.find_item_by_path(self.parent_library.tree.invisibleRootItem(), path)
        if item:
            self.parent_library.show_description_dialog(item)

    def on_folder_toggled(self, path, is_expanded):
        self.parent_library.db.update_folder_expanded_state(path, is_expanded)
        self.parent_library.update_cached_folder_expanded_state(path, is_expanded)
        
        item = self.parent_library.find_item_by_path(self.parent_library.tree.invisibleRootItem(), path)
        if item:
            self.parent_library.tree.blockSignals(True)
            item.setExpanded(is_expanded)
            self.parent_library.tree.blockSignals(False)
            
        def find_and_set_expanded(group):
            if group.path == path:
                group.expanded = is_expanded
                return True
            for child in group.child_groups:
                if find_and_set_expanded(child):
                    return True
            return False
            
        if self.root_group:
            find_and_set_expanded(self.root_group)
            self.update_visibility()

    def update_visibility(self):
        print("[DEBUG TileFlowWidget] update_visibility started", flush=True)
        def update_group_visibility(group, is_ancestors_expanded):
            print(f"[DEBUG TileFlowWidget] update_group_visibility for group={group.path} expanded={is_ancestors_expanded}", flush=True)
            if group.header:
                print(f"[DEBUG TileFlowWidget] Setting header visibility to {is_ancestors_expanded} for {group.path}", flush=True)
                group.header.setVisible(is_ancestors_expanded)
                print(f"[DEBUG TileFlowWidget] Header visibility set for {group.path}", flush=True)
            is_visible = is_ancestors_expanded and group.expanded
            print(f"[DEBUG TileFlowWidget] Setting books_container visibility to {is_visible} for {group.path}", flush=True)
            group.books_container.setVisible(is_visible)
            print(f"[DEBUG TileFlowWidget] books_container visibility set for {group.path}", flush=True)
            for child in group.child_groups:
                update_group_visibility(child, is_visible)
                
        if self.root_group:
            print("[DEBUG TileFlowWidget] self.root_group exists", flush=True)
            self.root_group.books_container.setVisible(True)
            print("[DEBUG TileFlowWidget] root books_container set to visible", flush=True)
            for child in self.root_group.child_groups:
                update_group_visibility(child, is_ancestors_expanded=True)
        print("[DEBUG TileFlowWidget] update_visibility finished", flush=True)

    def update_playback_state(self, playing_path, is_paused):
        def update_group(group):
            if group.header and playing_path and group.path:
                p_path = str(playing_path).replace("\\", "/")
                f_path = str(group.path).replace("\\", "/")
                is_active = False
                if p_path.startswith(f_path):
                    if len(p_path) == len(f_path) or p_path[len(f_path)] == "/":
                        is_active = True
                group.header.set_active(is_active)
            elif group.header:
                group.header.set_active(False)

            for tile in group.books:
                is_playing = False
                if playing_path and tile.path:
                    is_playing = (str(playing_path).replace("\\", "/") == str(tile.path).replace("\\", "/"))
                tile.set_playing(is_playing, is_paused)
            for child in group.child_groups:
                update_group(child)
        if self.root_group:
            update_group(self.root_group)

    def update_selection_state(self, selected_paths):
        def update_group(group):
            for tile in group.books:
                tile.setSelected(tile.path in selected_paths)
            for child in group.child_groups:
                update_group(child)
        if self.root_group:
            update_group(self.root_group)

    def update_texts(self):
        def update_group(group):
            for tile in group.books:
                tile.update_texts()
            for child in group.child_groups:
                update_group(child)
        if self.root_group:
            update_group(self.root_group)

    def refresh_tile(self, path):
        def find_tile(group):
            for tile in group.books:
                if tile.path == path:
                    return tile
            for child in group.child_groups:
                t = find_tile(child)
                if t:
                    return t
            return None
            
        tile = find_tile(self.root_group) if self.root_group else None
        if tile:
            data = self.parent_library.db.get_audiobook_by_path(path)
            if data:
                tile.progress_percent = data["progress_percent"] if data["progress_percent"] is not None else 0.0
                tile.is_started = bool(data["is_started"])
                tile.is_completed = bool(data["is_completed"])
                tile.is_favorite = bool(data["is_favorite"])
                tile.description = data.get("description", "") or ""
                
                # Update cover pixmap in case it changed
                cover_p_str = data.get("cached_cover_path")
                if not cover_p_str:
                    cover_p_str = data.get("cover_path")
                
                pixmap = None
                dpr = self.devicePixelRatioF()
                physical_size = int(tile.icon_size * dpr)
                
                if cover_p_str:
                    cover_p = Path(cover_p_str)
                    if not cover_p.is_absolute() and self.config.get("default_path"):
                        cover_p = Path(self.config.get("default_path")) / cover_p
                    if cover_p.exists() and cover_p.is_file():
                        load_icon.cache_clear()
                        tile_cover_icon = load_icon(cover_p, physical_size, force_square=True)
                        if tile_cover_icon and not tile_cover_icon.isNull():
                            pixmap = tile_cover_icon.pixmap(QSize(physical_size, physical_size))
                            pixmap.setDevicePixelRatio(dpr)
                
                # Fallback to default cover icon
                if pixmap is None or pixmap.isNull():
                    default_cover = self.config.get("default_cover_file", "resources/icons/default_cover.png")
                    default_cover_path = get_base_path() / default_cover
                    if default_cover_path.exists() and default_cover_path.is_file():
                        tile_cover_icon = load_icon(default_cover_path, physical_size, force_square=True)
                        if tile_cover_icon and not tile_cover_icon.isNull():
                            pixmap = tile_cover_icon.pixmap(QSize(physical_size, physical_size))
                            pixmap.setDevicePixelRatio(dpr)
                            
                if pixmap is not None and not pixmap.isNull():
                    tile.pixmap = pixmap
                    
                tile.update_texts()
                tile.update()


class LibraryWidget(QWidget):
    """Container for the audiobook tree, search filters, and status-based navigation buttons"""

    audiobook_selected = pyqtSignal(
        str
    )  # Emits the relative path of the selected audiobook
    show_folders_toggled = pyqtSignal(bool)  # Emits the new state of the folders toggle
    delete_requested = pyqtSignal(int, str, bool)  # Emits (audiobook_id, rel_path, delete_from_disk)
    folder_delete_requested = pyqtSignal(str)  # Emits folder relative path
    scan_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()  # Propagate settings request
    sort_order_changed = pyqtSignal(str, str, str)  # Emits (filter_mode, sort_order, sort_field)

    # Internal configuration for status filtering
    FILTER_CONFIG = {
        "all": {"label": "library.filter_all", "icon": "filter_all"},
        "not_started": {
            "label": "library.filter_not_started",
            "icon": "filter_not_started",
        },
        "in_progress": {
            "label": "library.filter_in_progress",
            "icon": "filter_in_progress",
        },
        "completed": {"label": "library.filter_completed", "icon": "filter_completed"},
    }

    def __init__(
        self,
        db_manager: DatabaseManager,
        config: dict,
        delegate=None,
        show_folders: bool = False,
        show_filter_labels: bool = True,
    ):
        """Initialize library managers, styling preferences, and default state"""
        super().__init__()
        self.db = db_manager
        self.config = config
        self.delegate = delegate
        self.default_audiobook_icon = None
        self.folder_icon = None
        self.current_playing_item = None
        _, self.highlight_color = StyleManager.get_theme_property("delegate_accent")
        self.highlight_text_color = Qt.GlobalColor.white
        self.current_filter = self.config.get("filter_mode", "all")
        self.remember_filter_folders = self.config.get("remember_filter_folders", True)
        self.show_folders_by_filter = self.config.get("show_folders_by_filter", {
            "all": show_folders,
            "not_started": show_folders,
            "in_progress": show_folders,
            "completed": show_folders,
        })
        if self.remember_filter_folders:
            self.show_folders = self.show_folders_by_filter.get(self.current_filter, show_folders)
        else:
            self.show_folders = show_folders
        self.show_filter_labels = show_filter_labels
        self.cached_library_data = None  # Cache for fast reconstruction
        self.tag_filter_ids = self.config.get("tag_filter_ids", set())
        self.is_tag_filter_active = self.config.get("tag_filter_active", False)
        self.is_favorites_filter_active = self.config.get("favorites_active", False)
        self.is_meta_filter_active = self.config.get("meta_filter_active", False)
        self.current_meta_filter = self.config.get("current_meta_filter", "no_cover")
        self.sort_orders = self.config.get("sort_orders", {
            "all": "asc",
            "not_started": "desc",
            "in_progress": "desc",
            "completed": "desc"
        })
        # Migrate from old single sort_order if present
        if "sort_orders" not in self.config and "sort_order" in self.config:
            old_sort = self.config["sort_order"]
            for k in self.sort_orders:
                self.sort_orders[k] = old_sort

        self.sort_fields = self.config.get("sort_fields", {
            "all": "name",
            "not_started": "time_added",
            "in_progress": "last_updated",
            "completed": "time_finished"
        })
        self.is_tile_view = self.config.get("tile_view", False)
        self.show_nesting_lines = self.config.get("show_nesting_lines", True)
        self._expanded_paths_cache = set()
        self.setup_ui()
        self.load_icons()
        self.set_tile_view_active(self.is_tile_view)

    @property
    def sort_order(self):
        return self.sort_orders.get(self.current_filter, "asc")

    @sort_order.setter
    def sort_order(self, value):
        self.sort_orders[self.current_filter] = value

    @property
    def sort_field(self):
        return self.sort_fields.get(self.current_filter, "name")

    @sort_field.setter
    def sort_field(self, value):
        self.sort_fields[self.current_filter] = value

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

        # Tile View Toggle
        self.btn_tile_view = QPushButton("")
        self.btn_tile_view.setObjectName("filterBtn")
        self.btn_tile_view.setCheckable(True)
        self.btn_tile_view.setChecked(self.is_tile_view)
        self.btn_tile_view.setIcon(get_icon("layout-grid"))
        self.btn_tile_view.setFixedWidth(40)
        self.btn_tile_view.setToolTip(tr("library.tooltip_tile_view"))
        self.btn_tile_view.clicked.connect(self.on_tile_view_toggled)
        filter_layout.addWidget(self.btn_tile_view)

        # Mass Selection Sub-Layout (flush group)
        mass_layout = QHBoxLayout()
        mass_layout.setSpacing(0)
        mass_layout.setContentsMargins(0, 0, 0, 0)

        # Mass Selection Toggle
        self.btn_mass_select = QPushButton("")
        self.btn_mass_select.setObjectName("filterBtn")
        self.btn_mass_select.setCheckable(True)
        self.btn_mass_select.setChecked(False)
        self.btn_mass_select.setIcon(get_icon("square-check"))
        self.btn_mass_select.setFixedWidth(40)
        self.btn_mass_select.setToolTip(tr("library.tooltip_mass_select"))
        self.btn_mass_select.clicked.connect(self.on_mass_select_toggled)
        mass_layout.addWidget(self.btn_mass_select)

        # Mass Selection Dropdown Arrow Button
        self.btn_mass_select_arrow = QPushButton("")
        self.btn_mass_select_arrow.setObjectName("filterBtnArrow")
        self.btn_mass_select_arrow.setFixedWidth(20)
        self.btn_mass_select_arrow.setIcon(get_icon("chevron-down"))
        self.btn_mass_select_arrow.setIconSize(QSize(12, 12))
        self.btn_mass_select_arrow.setToolTip(tr("library.tooltip_mass_select"))
        self.btn_mass_select_arrow.clicked.connect(self.show_mass_select_menu)
        mass_layout.addWidget(self.btn_mass_select_arrow)

        filter_layout.addLayout(mass_layout)

        # Create a layout to keep metadata filter toggle and dropdown in one flush button group
        meta_filter_layout = QHBoxLayout()
        meta_filter_layout.setSpacing(0)
        meta_filter_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_meta_filter = QPushButton("")
        self.btn_meta_filter.setObjectName("filterBtn")
        self.btn_meta_filter.setCheckable(True)
        self.btn_meta_filter.setChecked(self.is_meta_filter_active)
        self.btn_meta_filter.setIcon(get_icon("filter"))
        self.btn_meta_filter.setFixedWidth(40)
        self.btn_meta_filter.setToolTip(tr("library.tooltip_filter_metadata"))
        self.btn_meta_filter.clicked.connect(self.toggle_meta_filter)
        meta_filter_layout.addWidget(self.btn_meta_filter)

        self.btn_meta_filter_arrow = QPushButton("")
        self.btn_meta_filter_arrow.setObjectName("filterBtnArrow")
        self.btn_meta_filter_arrow.setFixedWidth(20)
        self.btn_meta_filter_arrow.setIcon(get_icon("chevron-down"))
        self.btn_meta_filter_arrow.setIconSize(QSize(12, 12))
        self.btn_meta_filter_arrow.setToolTip(tr("library.tooltip_filter_metadata"))
        self.btn_meta_filter_arrow.clicked.connect(self.show_meta_filter_menu)
        meta_filter_layout.addWidget(self.btn_meta_filter_arrow)

        filter_layout.addLayout(meta_filter_layout)

        # Favorites Filter (Icon-only)
        self.btn_favorites = QPushButton("")
        self.btn_favorites.setObjectName("filterBtn")
        self.btn_favorites.setCheckable(True)
        self.btn_favorites.setChecked(self.is_favorites_filter_active)
        self.btn_favorites.setFixedWidth(40)
        self.btn_favorites.setIcon(get_icon("favorites"))
        self.btn_favorites.setToolTip(tr("library.filter_favorites"))
        self.btn_favorites.clicked.connect(self.on_favorites_filter_toggled)
        # self.btn_favorites.setProperty('filter_type', 'favorites') # No longer an exclusive type
        filter_layout.addWidget(self.btn_favorites)

        # Tags Filter
        self.btn_tags = QPushButton("")
        self.btn_tags.setObjectName("filterBtn")
        self.btn_tags.setCheckable(True)
        self.btn_tags.setChecked(self.is_tag_filter_active)
        self.btn_tags.setFixedWidth(40)
        self.btn_tags.setIcon(get_icon("context_tags"))
        self.btn_tags.setToolTip(tr("library.tooltip_filter_tags"))
        self.btn_tags.clicked.connect(self.on_tag_filter_toggled)
        self.btn_tags.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.btn_tags.customContextMenuRequested.connect(self.show_tag_filter_menu)
        filter_layout.addWidget(self.btn_tags)

        filter_layout.addSpacing(5)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        self.filter_buttons = {}
        for filter_id, config in self.FILTER_CONFIG.items():
            btn = QPushButton(tr(config["label"]))
            btn.setObjectName("filterBtn")
            btn.setCheckable(True)
            btn.setProperty("filter_type", filter_id)

            if "icon" in config:
                btn.setIcon(get_icon(config["icon"]))

            btn.setToolTip(tr(f"library.tooltip_filter_{filter_id}"))
            btn.clicked.connect(lambda checked, f=filter_id: self.apply_filter(f))
            self.filter_group.addButton(btn)
            self.filter_buttons[filter_id] = btn

            filter_layout.addWidget(btn)

        # Add favorites to group and dictionary for state management
        # self.filter_group.addButton(self.btn_favorites) # Removed from exclusive group
        self.filter_buttons["favorites"] = self.btn_favorites
        self.filter_buttons["tags"] = self.btn_tags

        last_btn = self.filter_buttons.get(self.current_filter)
        if last_btn:
            last_btn.setChecked(True)

        filter_layout.addStretch(1)

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





        # Create a layout to keep sorting toggle and dropdown in one flush button group
        sort_layout = QHBoxLayout()
        sort_layout.setSpacing(0)
        sort_layout.setContentsMargins(0, 0, 0, 0)

        # Sort Order Toggle (A-Z / Z-A) - positioned at the far right
        self.btn_sort = QPushButton("")
        self.btn_sort.setObjectName("filterBtn")
        self.btn_sort.setFixedWidth(40)
        self.btn_sort.setIcon(
            get_icon("arrow-up-narrow-wide")
            if self.sort_order == "asc"
            else get_icon("arrow-down-wide-narrow")
        )
        self.btn_sort.setToolTip(
            tr("library.tooltip_sort_asc")
            if self.sort_order == "asc"
            else tr("library.tooltip_sort_desc")
        )
        self.btn_sort.clicked.connect(self.toggle_sort_order)
        sort_layout.addWidget(self.btn_sort)

        # Sort Field Dropdown Button (arrow down) - positioned immediately after self.btn_sort
        self.btn_sort_field = QPushButton("")
        self.btn_sort_field.setObjectName("filterBtnArrow")
        self.btn_sort_field.setFixedWidth(20)
        self.btn_sort_field.setIcon(get_icon("chevron-down"))
        self.btn_sort_field.setIconSize(QSize(12, 12))
        self.btn_sort_field.setToolTip(tr("library.tooltip_sort_field"))
        self.btn_sort_field.clicked.connect(self.show_sort_field_menu)
        sort_layout.addWidget(self.btn_sort_field)

        filter_layout.addLayout(sort_layout)

        layout.addLayout(filter_layout)

        self.stack = QStackedWidget()

        self.tree = LibraryTree()
        self.tree.setObjectName("bookTree")
        self.tree.setHeaderHidden(True)
        self.tree.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )  # Disable focus to avoid intercepting hotkeys
        self.tree.setIconSize(
            QSize(
                self.config.get("audiobook_icon_size", 100),
                self.config.get("audiobook_icon_size", 100),
            )
        )
        self.tree.setIndentation(12)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.favorite_clicked.connect(self.on_tree_favorite_clicked)
        self.tree.description_requested.connect(self.show_description_dialog)
        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.itemCollapsed.connect(self.on_item_collapsed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.settings_requested.connect(self.settings_requested.emit)
        self.tree.search_requested.connect(self.search_edit.setText)
        self.tree.tag_clicked.connect(self.on_tree_tag_clicked)

        if self.delegate:
            self.delegate.tree = self.tree
            self.tree.setItemDelegate(self.delegate)

        self.stack.addWidget(self.tree)

        self.tile_view = TileFlowWidget(parent_library=self)
        self.stack.addWidget(self.tile_view)

        layout.addWidget(self.stack)

    def set_tile_view_active(self, active: bool):
        self.is_tile_view = active
        self.config["tile_view"] = active
        
        if hasattr(self, "btn_tile_view") and self.btn_tile_view:
            self.btn_tile_view.setChecked(active)
            
        if active:
            self.stack.setCurrentWidget(self.tile_view)
            self.tile_view.populate(self.tree.invisibleRootItem())
            self.update_tile_playback_state()
        else:
            self.stack.setCurrentWidget(self.tree)

    def on_tile_view_toggled(self, checked):
        self.set_tile_view_active(checked)
        window = self.window()
        if hasattr(window, "save_settings"):
            window.save_settings()

    def update_tile_playback_state(self):
        if self.is_tile_view and hasattr(self, "tile_view"):
            playing_path = self.delegate.playing_path if self.delegate else None
            is_paused = self.delegate.is_paused if self.delegate else True
            self.tile_view.update_playback_state(playing_path, is_paused)

    def resizeEvent(self, event):
        """Update button labels when the widget is resized to avoid layout overflow"""
        super().resizeEvent(event)
        self.update_filter_labels()

    def update_filter_labels(self):
        """Toggle text visibility on filter buttons based on current widget width"""
        if not hasattr(self, "filter_buttons"):
            return

        # Threshold for hiding text (only icons shown below this width)
        show_text = (self.width() >= 450) if self.show_filter_labels else False

        # Standard filters
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                btn = self.filter_buttons[filter_id]
                self._update_btn_label(btn, config["label"], show_text)

        # Tag filter
        if hasattr(self, "btn_tags") and self.btn_tags:
            self._update_btn_label(self.btn_tags, "library.filter_tags", show_text)

    def _update_btn_label(self, btn, label_key, show_text):
        if show_text:
            label = tr(label_key)
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
            btn.setMinimumWidth(
                0
            )  # Reset min width allow shrinking to icon size (or rely on style)

    def load_icons(self):
        """Load and scale standard icons for folders and audiobook covers from resources"""
        # Save scroll bar position
        scroll_val = None
        if hasattr(self, "tree") and self.tree:
            scroll_val = self.tree.verticalScrollBar().value()

        # Determine the default cover icon
        default_cover = self.config.get(
            "default_cover_file", "resources/icons/default_cover.png"
        )
        self.default_audiobook_icon = load_icon(
            get_base_path() / default_cover, self.config.get("audiobook_icon_size", 100)
        )

        if not self.default_audiobook_icon:
            self.default_audiobook_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )

        # Determine the folder representation icon
        folder_cover = self.config.get(
            "folder_cover_file", "resources/icons/folder_cover.png"
        )
        self.folder_icon = load_icon(
            get_base_path() / folder_cover, self.config.get("folder_icon_size", 35)
        )

        if not self.folder_icon:
            self.folder_icon = resize_icon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                self.config.get("folder_icon_size", 35),
            )

        # Reload delegate icons
        if hasattr(self, "delegate") and self.delegate:
            self.delegate.load_icons()

        # Reload filter panel button icons
        if hasattr(self, "btn_mass_select") and self.btn_mass_select:
            self.btn_mass_select.setIcon(get_icon("square-check"))
        if hasattr(self, "btn_mass_select_arrow") and self.btn_mass_select_arrow:
            self.btn_mass_select_arrow.setIcon(get_icon("chevron-down"))
        if hasattr(self, "btn_favorites") and self.btn_favorites:
            self.btn_favorites.setIcon(get_icon("favorites"))
        if hasattr(self, "btn_tags") and self.btn_tags:
            self.btn_tags.setIcon(get_icon("context_tags"))
        if hasattr(self, "btn_meta_filter") and self.btn_meta_filter:
            self.btn_meta_filter.setIcon(get_icon("filter"))
        if hasattr(self, "btn_meta_filter_arrow") and self.btn_meta_filter_arrow:
            self.btn_meta_filter_arrow.setIcon(get_icon("chevron-down"))

        if hasattr(self, "filter_buttons") and self.filter_buttons:
            for filter_id, btn in self.filter_buttons.items():
                if filter_id in self.FILTER_CONFIG:
                    config = self.FILTER_CONFIG[filter_id]
                    if "icon" in config:
                        btn.setIcon(get_icon(config["icon"]))

        if hasattr(self, "btn_show_folders") and self.btn_show_folders:
            self.btn_show_folders.setIcon(get_icon("folder_cover"))
        if hasattr(self, "btn_tile_view") and self.btn_tile_view:
            self.btn_tile_view.setIcon(get_icon("layout-grid"))
        if hasattr(self, "btn_sort") and self.btn_sort:
            self.btn_sort.setIcon(
                get_icon("arrow-up-narrow-wide")
                if self.sort_order == "asc"
                else get_icon("arrow-down-wide-narrow")
            )
        if hasattr(self, "btn_sort_field") and self.btn_sort_field:
            self.btn_sort_field.setIcon(get_icon("chevron-down"))

        # Rebuild tree using existing cache so we re-render items with the new icons
        if hasattr(self, "tree") and self.tree and self.tree.topLevelItemCount() > 0:
            # Save selected path
            selected_path = None
            selected_items = self.tree.selectedItems()
            if selected_items:
                selected_path = selected_items[0].data(0, Qt.ItemDataRole.UserRole)

            # Rebuild tree using cache
            self.load_audiobooks(use_cache=True)

            # Restore selected item
            if selected_path:
                def select_item(item):
                    if item.data(0, Qt.ItemDataRole.UserRole) == selected_path:
                        self.tree.setCurrentItem(item)
                        return True
                    for i in range(item.childCount()):
                        if select_item(item.child(i)):
                            return True
                    return False

                root = self.tree.invisibleRootItem()
                if root:
                    for i in range(root.childCount()):
                        if select_item(root.child(i)):
                            break

            # Restore scroll position
            if scroll_val is not None:
                self.tree.verticalScrollBar().setValue(scroll_val)

    def on_tag_filter_toggled(self, checked):
        """Toggle tag filtering on/off"""
        self.is_tag_filter_active = checked
        if checked and not self.tag_filter_ids:
            QToolTip.showText(
                self.btn_tags.mapToGlobal(QPoint(0, self.btn_tags.height())),
                tr("library.no_tags_selected"),
                self.btn_tags,
            )
        self.load_audiobooks(use_cache=False)

    def show_tag_filter_menu(self, pos):
        """Show popup for selecting tags to filter by"""
        # Close existing popup if open? (Qt handles Popup focus loss close usually)

        all_tags = self.db.get_all_tags()

        self.tag_popup = TagFilterPopup(all_tags, self.tag_filter_ids, self)
        self.tag_popup.filter_changed.connect(self.on_tag_selection_changed)

        # Position under the button
        global_pos = self.btn_tags.mapToGlobal(QPoint(0, self.btn_tags.height()))
        self.tag_popup.move(global_pos)
        self.tag_popup.show()

    def on_tag_selection_changed(self, selected_ids):
        """Update the set of selected tag IDs for filtering"""
        self.tag_filter_ids = selected_ids

        if self.is_tag_filter_active:
            self.load_audiobooks(use_cache=False)

    def on_tree_tag_clicked(self, tag: dict):
        """Handle clicking a tag in the tree: enable filtering by this tag"""
        tag_id = tag.get("id")
        if tag_id is None:
            return

        self.tag_filter_ids = {tag_id}
        self.is_tag_filter_active = True
        if hasattr(self, "btn_tags") and self.btn_tags:
            self.btn_tags.setChecked(True)
        self.load_audiobooks(use_cache=False)

    def on_tree_favorite_clicked(self, path: str):
        """Handle click on the favorite heart icon in the tree"""
        if self.is_favorites_filter_active:
            return

        # Find ID for path
        info = self.db.get_audiobook_info(path)
        if not info:
            return

        audiobook_id = info[0]
        # Check current status to prevent accidental reset (unfavoriting)
        # We want this action to: Ensure Favorite AND/OR Go To Favorites
        data = self.db.get_audiobook_by_path(path)
        if data and not data.get("is_favorite"):
            self.toggle_favorite(audiobook_id, path)

        # Activate Favorites filter if not already active
        if not self.is_favorites_filter_active:
            if hasattr(self, "btn_favorites") and self.btn_favorites:
                self.btn_favorites.setChecked(True)
                self.on_favorites_filter_toggled(True)
        else:
            # Refresh current view to reflect change (e.g. remove item if unfavorited)
            self.refresh_audiobook_item(path)
            if not self.db.is_favorite(audiobook_id):
                # actually, refresh_audiobook_item updates data. But if filter active and item NOT favorite,
                # we should hide it.
                # The simplest is full reload if we are removing from active favorites filter.
                self.load_audiobooks(use_cache=False)

    def on_favorites_filter_toggled(self, checked):
        """Toggle favorites filtering on/off"""
        self.is_favorites_filter_active = checked
        self.load_audiobooks(use_cache=False)

    def show_description_dialog(self, path: str):
        """Show a dialog with the audiobook description"""
        info = self.db.get_audiobook_by_path(path)
        if not info or not info.get("description"):
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("library.description_title"))
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Title
        title_label = QLabel(info.get("title", ""))
        font = title_label.font()
        font.setBold(True)
        font.setPointSize(12)
        title_label.setFont(font)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Text
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(info.get("description", ""))
        layout.addWidget(text_edit)

        # Close button
        close_btn = QPushButton(tr("dialog.close"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

        dialog.exec()

    def apply_filter(self, filter_type: str):
        """Switch the current library view filter and refresh the audiobook listing"""
        self.current_filter = filter_type
        self.update_sort_button_ui()
        self.update_sort_field_button_ui()
        if self.remember_filter_folders:
            new_state = self.show_folders_by_filter.get(filter_type, False)
            if self.show_folders != new_state:
                self.show_folders = new_state
                if hasattr(self, "btn_show_folders"):
                    self.btn_show_folders.setChecked(new_state)
                self.show_folders_toggled.emit(new_state)
        # When switching filters, reload from DB to apply correct sorting and subset
        self.load_audiobooks(use_cache=False)

    def on_show_folders_toggled(self, checked):
        """Toggle folder visibility and refresh the library"""
        self.show_folders = checked
        if self.remember_filter_folders:
            self.show_folders_by_filter[self.current_filter] = checked
        self.show_folders_toggled.emit(checked)
        self.load_audiobooks(use_cache=False)

    def on_mass_select_toggled(self, checked):
        """Toggle mass selection mode and refresh viewport"""
        self.tree.mass_selection_mode = checked
        if not checked:
            self.tree.selected_audiobook_paths.clear()
            self.tree._last_checked_item = None
        self.tree.viewport().update()

    def refresh_library(self):
        """Force a database reload and refresh the UI"""
        self.load_audiobooks(use_cache=False)

    def get_expanded_folder_paths(self):
        """Recursively retrieve the paths of all currently expanded folders in the tree"""
        expanded_paths = set()
        if not hasattr(self, "tree") or self.tree is None:
            return expanded_paths

        def traverse(item):
            if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
                if item.isExpanded():
                    path = item.data(0, Qt.ItemDataRole.UserRole)
                    if path:
                        expanded_paths.add(path)
            for i in range(item.childCount()):
                traverse(item.child(i))

        root = self.tree.invisibleRootItem()
        if root:
            for i in range(root.childCount()):
                traverse(root.child(i))
        return expanded_paths

    def load_audiobooks(self, use_cache: bool = True):
        """Retrieve and display audiobooks from the database according to the active filter"""
        if not use_cache:
            load_icon.cache_clear()
        self.current_playing_item = None
        self._expanded_paths_cache = self.get_expanded_folder_paths()
        self.tree.clear()
        data_to_display = {}

        # Helper to generate the key for client-side sorting
        def make_sort_key(field, reverse):
            def key_fn(x):
                is_folder = x.get("is_folder", False)
                if is_folder:
                    if field == "name":
                        val = (x.get("name") or "").lower()
                        return (1, val) if reverse else (0, val)
                    
                    # For other fields, determine folder value based on books inside it
                    books_inside = []
                    visited = set()
                    def recurse(path):
                        if path in visited:
                            return
                        visited.add(path)
                        for item in data_to_display.get(path, []):
                            if item.get("is_folder"):
                                recurse(item["path"])
                            else:
                                books_inside.append(item)
                    recurse(x["path"])
                    
                    if not books_inside:
                        return (0, "") if reverse else (1, "")
                    
                    # Extract values for each book
                    book_vals = []
                    for b in books_inside:
                        b_val = b.get(field)
                        if b_val is not None and b_val != "":
                            if field in ("author", "language"):
                                book_vals.append(str(b_val).lower())
                            else:
                                if isinstance(b_val, (int, float)):
                                    book_vals.append(b_val)
                                else:
                                    try:
                                        book_vals.append(float(b_val))
                                    except (ValueError, TypeError):
                                        book_vals.append(str(b_val))
                    
                    if not book_vals:
                        return (0, "") if reverse else (1, "")
                    
                    try:
                        val = max(book_vals) if reverse else min(book_vals)
                    except TypeError:
                        str_vals = [str(v) for v in book_vals]
                        val = max(str_vals) if reverse else min(str_vals)
                    
                    return (1, val) if reverse else (0, val)
                
                if field == "name":
                    val = x.get("title") or x.get("name")
                else:
                    val = x.get(field)
                is_empty = (val is None or val == "")
                
                if is_empty:
                    # Empty values always go to the end of the list, regardless of sort order
                    return (0, "") if reverse else (1, "")
                
                if field in ("name", "author", "language"):
                    val = str(val).lower()
                else:
                    # Keep numeric type if possible for proper numeric sorting, fallback to str
                    if isinstance(val, (int, float)):
                        pass
                    else:
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            val = str(val)
                
                return (1, val) if reverse else (0, val)
            return key_fn

        # Check cache or force reload
        # Always load all audiobooks to enable fast client-side filtering
        if not use_cache or self.cached_library_data is None:
            self.cached_library_data = self.db.load_audiobooks_from_db(
                self.current_filter
            )

        # Update global content flag based on DB count (independent of filter)
        total_count = self.db.get_audiobook_count()
        self.tree.has_any_content = total_count > 0

        # Pre-fetch all tags logic
        all_tags = self.db.get_all_audiobook_tags()

        # Optimize tree population by disabling repaints and sorting
        self.tree.setUpdatesEnabled(False)
        self.tree.blockSignals(True)
        try:
            # If folders are hidden and we are in a non-'all' filter,
            # we should populate as a flat list to guarantee the SQL sort order
            # is visually preserved across the entire library.
            if not self.show_folders:
                all_items = []
                for parent_path, items in self.cached_library_data.items():
                    for item_data in items:
                        if item_data["is_folder"]:
                            continue

                        # Attach tags
                        item_tags = all_tags.get(item_data["id"], [])
                        if "id" in item_data:
                            item_data["tags"] = item_tags

                        # Apply Status Filter — must happen here so sorting is
                        # applied only to the books that will actually be shown.
                        # (filter_tree_items handles text search afterward)
                        if self.current_filter == "not_started":
                            if item_data.get("is_started"):
                                continue
                        elif self.current_filter == "in_progress":
                            if not (item_data.get("is_started") and not item_data.get("is_completed")):
                                continue
                        elif self.current_filter == "completed":
                            if not item_data.get("is_completed"):
                                continue

                        # Apply Tag Filter
                        if self.is_tag_filter_active and self.tag_filter_ids:
                            item_tag_ids = {t["id"] for t in item_tags}
                            if not self.tag_filter_ids.intersection(item_tag_ids):
                                continue

                        # Apply Favorites Filter
                        if self.is_favorites_filter_active:
                            if not item_data.get("is_favorite"):
                                continue

                        # Apply Metadata Filter
                        if not self._matches_meta_filter(item_data):
                            continue

                        all_items.append(item_data)

                # Global flat sort — ignores folder hierarchy entirely.
                # Two-pass stable sort: first by name (secondary, always asc, tie-breaker),
                # then by primary field (stable — preserves name order within ties).
                # This prevents folder-grouped clustering when multiple books share the
                # same primary sort key value (e.g. same time_added after a batch scan).
                reverse_sort = (self.sort_order == "desc")
                all_items.sort(key=lambda x: (x.get("title") or x.get("name") or "").lower())
                all_items.sort(
                    key=make_sort_key(self.sort_field, reverse_sort),
                    reverse=reverse_sort
                )

                # Batch add to avoid recursion overhead
                self.add_flat_items(self.tree.invisibleRootItem(), all_items)
            else:
                # Prepare data for recursive add, potentially filtering
                data_to_display = self.cached_library_data

                if self.is_tag_filter_active or True:  # always attach tags first
                    # We need to reconstruct if we filter, to avoid modifying the cache in a way that loses data permanently?
                    # No, cached_library_data is a dict of lists of dicts.
                    # We create a NEW dict structure pointing to the same item dicts (checking tags).

                    filtered_data = {}
                    for parent_path, items in self.cached_library_data.items():
                        filtered_items = []
                        for item_data in items:
                            # Attach tags logic
                            if not item_data["is_folder"] and "id" in item_data:
                                item_data["tags"] = all_tags.get(item_data["id"], [])

                            # Filtering logic
                            if (
                                self.is_tag_filter_active
                                and not item_data["is_folder"]
                                and self.tag_filter_ids
                            ):
                                item_tags = item_data.get("tags", [])
                                item_tag_ids = {t["id"] for t in item_tags}
                                item_tag_ids = {t["id"] for t in item_tags}
                                if not self.tag_filter_ids.intersection(item_tag_ids):
                                    continue

                            if (
                                self.is_favorites_filter_active
                                and not item_data["is_folder"]
                            ):
                                if not item_data.get("is_favorite"):
                                    continue

                            if (
                                self.is_meta_filter_active
                                and not item_data["is_folder"]
                            ):
                                if not self._matches_meta_filter(item_data):
                                    continue

                            filtered_items.append(item_data)

                        if filtered_items:
                            filtered_data[parent_path] = filtered_items

                    data_to_display = filtered_data

                # Sort within each parent group (folders first, then books)
                sorted_data = {}
                for parent_path, items in data_to_display.items():
                    folders = [x for x in items if x.get("is_folder")]
                    books = [x for x in items if not x.get("is_folder")]
                    
                    reverse_sort = (self.sort_order == "desc")
                    # Sort folders strictly alphabetically by name, honoring the sorting direction
                    folders.sort(key=lambda x: (x.get("name") or "").lower(), reverse=reverse_sort)
                    # Two-pass sort for consistent tie-breaking within book group
                    books.sort(key=lambda x: (x.get("title") or x.get("name") or "").lower())
                    books.sort(key=make_sort_key(self.sort_field, reverse_sort), reverse=reverse_sort)
                    
                    sorted_data[parent_path] = folders + books
                data_to_display = sorted_data

                # Root path can be represented as '' or None in the database map
                self.add_items_from_db(
                    self.tree.invisibleRootItem(), "", data_to_display
                )
                if None in data_to_display:
                    self.add_items_from_db(
                        self.tree.invisibleRootItem(), None, data_to_display
                    )
        finally:
            self.tree.blockSignals(False)
            self.tree.setUpdatesEnabled(True)

        # Apply current filter immediately after loading
        self.filter_audiobooks()

    def add_flat_items(self, parent_item, items_list: list):
        """Populate the tree with a flat list of audiobooks, ignoring hierarchy"""
        for data in items_list:
            self._create_item_from_data(parent_item, data)

    def add_items_from_db(self, parent_item, parent_path, data_by_parent: dict):
        """Recursively populate the tree widget with folders and audiobooks from the database map"""
        if parent_path not in data_by_parent:
            return

        for data in data_by_parent[parent_path]:
            if data["is_folder"]:
                if not self.show_folders:
                    # If folders are hidden by default, recursively add children to the SAME parent
                    self.add_items_from_db(parent_item, data["path"], data_by_parent)
                    continue

                item = QTreeWidgetItem(parent_item)
                item.setData(0, Qt.ItemDataRole.UserRole, data["path"])
                item.setText(0, data["name"])
                item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
                item.setData(0, Qt.ItemDataRole.UserRole + 5, data["name"])
                item.setIcon(0, self.folder_icon)
                # Restore the expansion state of the folder from previous sessions or cache
                if data.get("is_expanded") or data["path"] in self._expanded_paths_cache:
                    item.setExpanded(True)

                # Sub-items traversal
                self.add_items_from_db(item, data["path"], data_by_parent)

                # Prune empty folders (if no children were added or all were filtered out)
                if item.childCount() == 0:
                    parent_item.removeChild(item)
                else:
                    # Calculate and add statistics to the folder name
                    books_count, total_seconds = self._get_folder_stats(item)
                    if books_count > 0:
                        duration_str = format_duration(total_seconds)
                        books_str = self._format_books_count(books_count)
                        item.setText(0, f"{data['name']} ({books_str}, {duration_str})")
            else:
                self._create_item_from_data(parent_item, data)

    def _create_item_from_data(self, parent_item, data):
        """Shared helper to create a tree item for an audiobook with all its metadata and icons"""
        item = QTreeWidgetItem(parent_item)
        item.setData(0, Qt.ItemDataRole.UserRole, data["path"])
        # Audiobooks are custom-painted by the delegate
        # Set text to empty so the delegate has full control over the item's visual area
        item.setText(0, "")
        item.setData(0, Qt.ItemDataRole.UserRole + 1, "audiobook")
        item.setData(
            0,
            Qt.ItemDataRole.UserRole + 2,
            (
                data["author"],
                data["title"],
                data["narrator"],
                data["file_count"],
                data["duration"],
                data["listened_duration"],
                data["progress_percent"],
                data["codec"],
                data["bitrate_min"],
                data["bitrate_max"],
                data["bitrate_mode"],
                data["container"],
                data.get("description", ""),
                data.get("total_size", 0),
                data.get("language"),
                data.get("year_written"),
                data.get("year_recorded"),
            ),
        )
        # Store status flags for client-side filtering
        item.setData(
            0,
            Qt.ItemDataRole.UserRole + 3,
            (data["is_started"], data["is_completed"], data["is_favorite"]),
        )

        # Fetch and scale the audiobook cover
        cover_icon = None

        # Prioritize cached cover (fastest access)
        cover_p_str = data.get("cached_cover_path")
        if not cover_p_str:
            cover_p_str = data.get("cover_path")

        if cover_p_str:
            cover_p = Path(cover_p_str)
            # For relative paths (legacy or uncached), resolve them against the library's root directory
            if not cover_p.is_absolute() and self.config.get("default_path"):
                cover_p = Path(self.config.get("default_path")) / cover_p

            cover_icon = load_icon(
                cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
            )
        item.setIcon(0, cover_icon or self.default_audiobook_icon)
        item.setData(0, Qt.ItemDataRole.UserRole + 5, cover_p_str)

        # Store tags
        if "tags" in data:
            item.setData(0, Qt.ItemDataRole.UserRole + 4, data["tags"])

        return item

    def _get_folder_stats(self, folder_item: QTreeWidgetItem) -> tuple[int, float]:
        """Recursively calculate the number of audiobooks and total duration under this folder item"""
        books_count = 0
        total_seconds = 0.0

        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "audiobook":
                books_count += 1
                data = child.data(0, Qt.ItemDataRole.UserRole + 2)
                if data and len(data) >= 5:
                    total_seconds += (data[4] or 0.0)
            elif item_type == "folder":
                sub_count, sub_seconds = self._get_folder_stats(child)
                books_count += sub_count
                total_seconds += sub_seconds

        return books_count, total_seconds

    def _format_books_count(self, count: int) -> str:
        """Format the number of books in a folder with proper language-specific rules"""
        from translations import get_language, trf
        lang = get_language()
        if lang == "ru":
            if count % 10 == 1 and count % 100 != 11:
                return f"{count} книга"
            elif count % 10 in (2, 3, 4) and not (count % 100 in (12, 13, 14)):
                return f"{count} книги"
            else:
                return f"{count} книг"
        elif lang == "en":
            return f"{count} book" if count == 1 else f"{count} books"

        # Fallback to general translations if defined, or English default
        val = trf("library.folder_books_count", count=count)
        if val == "library.folder_books_count":
            return f"{count} book" if count == 1 else f"{count} books"
        return val

    def filter_audiobooks(self):
        """Handle real-time search queries by filtering tree items based on text matching"""
        search_text = self.search_edit.text().lower().strip()

        if not search_text and self.current_filter == "all":
            self.show_all_items(self.tree.invisibleRootItem())
            if self.is_tile_view:
                self.tile_view.populate(self.tree.invisibleRootItem())
                self.update_tile_playback_state()
            return

        self.filter_tree_items(self.tree.invisibleRootItem(), search_text)
        if self.is_tile_view:
            self.tile_view.populate(self.tree.invisibleRootItem())
            self.update_tile_playback_state()

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

            if item_type == "folder":
                has_visible_children = self.filter_tree_items(child, search_text)
                folder_name = child.text(0).lower()

                if search_text:
                    fn_matches = search_text in folder_name
                    child.setHidden(not (fn_matches or has_visible_children))
                else:
                    child.setHidden(not has_visible_children)

                if not child.isHidden():
                    has_visible = True

            elif item_type == "audiobook":
                # 1. Check Status Filter
                status_data = child.data(0, Qt.ItemDataRole.UserRole + 3)
                status_match = True
                if status_data and len(status_data) >= 2:
                    is_started = status_data[0]
                    is_completed = status_data[1]
                    if self.current_filter == "not_started":
                        status_match = not is_started
                    elif self.current_filter == "in_progress":
                        status_match = is_started and not is_completed
                    elif self.current_filter == "completed":
                        status_match = is_completed

                # 2. Check Text Search
                text_match = True
                if search_text:
                    data = child.data(0, Qt.ItemDataRole.UserRole + 2)

                    if data:
                        # author, title, narrator, file_count, duration, listened_duration, progress_percent, codec, b_min, b_max, b_mode, container
                        author, title, narrator = data[0:3]
                        codec, b_min, b_max, b_mode, container = data[7:12]

                    # Tag Search
                    tags = child.data(0, Qt.ItemDataRole.UserRole + 4)
                    tag_names = []
                    if tags and isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict) and "name" in tag:
                                tag_names.append(tag["name"])

                    # Bitrate search
                    search_min = str(b_min // 1000) if b_min > 5000 else str(b_min)
                    search_max = str(b_max // 1000) if b_max > 5000 else str(b_max)

                    searchables = [
                        author,
                        title,
                        narrator,
                        codec,
                        container,
                        b_mode,
                        search_min,
                        search_max,
                    ] + tag_names
                    # filter out None and empty strings
                    searchables = [s for s in searchables if s]
                    combined_search_text = " ".join(searchables)

                    text_match = smart_search(search_text, combined_search_text)

                child.setHidden(not (status_match and text_match))
                if not child.isHidden():
                    has_visible = True

        return has_visible

    def update_cached_folder_expanded_state(self, path: str, is_expanded: bool):
        """Update the is_expanded state in the cached library data structure"""
        if not self.cached_library_data:
            return
        for parent_path, items in self.cached_library_data.items():
            for item in items:
                if item.get("is_folder") and item.get("path") == path:
                    item["is_expanded"] = is_expanded
                    return

    def on_item_expanded(self, item):
        """Persist the folder expansion state to the database and cache when a branch is opened"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, True)
                self.update_cached_folder_expanded_state(path, True)

    def on_item_collapsed(self, item):
        """Persist the folder collapse state to the database and cache when a branch is closed"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, False)
                self.update_cached_folder_expanded_state(path, False)

    def show_context_menu(self, pos):
        """Construct and display a context menu for items in the library tree"""
        item = self.tree.itemAt(pos)
        if not item:
            return

        # Freeze scroll for the entire context-menu lifetime so that Qt's internal
        # focus-change machinery (menu open / hover / close) cannot scroll the list.
        vbar = self.tree.verticalScrollBar()
        saved_scroll = vbar.value()
        self.tree._suppress_scroll = True
        try:
            self.tree.setCurrentItem(item)
            vbar.setValue(saved_scroll)

            role = item.data(0, Qt.ItemDataRole.UserRole + 1)
            path = item.data(0, Qt.ItemDataRole.UserRole)

            if role == "audiobook":
                # Audiobook context menu (existing logic)
                info = self.db.get_audiobook_info(path)
                if not info:
                    return
                audiobook_id = info[0]

                selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
                mass_mode = getattr(self.tree, "mass_selection_mode", False)
                is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

                if is_batch:
                    batch_books = []
                    for p in selected_paths:
                        info_b = self.db.get_audiobook_info(p)
                        if info_b:
                            batch_books.append((info_b[0], p))

                # Fetch fresh favorite status
                if is_batch:
                    is_favorite = True
                    for bid, bp in batch_books:
                        book_data = self.db.get_audiobook_by_path(bp)
                        if book_data and not book_data.get("is_favorite", False):
                            is_favorite = False
                            break
                else:
                    is_favorite = False
                    status_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
                    if status_data and len(status_data) >= 3:
                        is_favorite = status_data[2]

                duration = item.data(0, Qt.ItemDataRole.UserRole + 2)[4]

                menu = QMenu(self.tree)
                menu.setObjectName("libraryContextMenu")

                play_action = QAction(tr("library.context_play"), self)
                play_action.setIcon(get_icon("context_play"))
                play_action.setEnabled(not is_batch)
                play_action.triggered.connect(
                    lambda _: self.on_item_double_clicked(item, 0)
                )
                menu.addAction(play_action)
                menu.addSeparator()

                # Favorites Action (Batch compatible)
                fav_text = (
                    tr("library.menu_remove_favorite")
                    if is_favorite
                    else tr("library.menu_add_favorite")
                )
                fav_icon = get_icon(
                    "context_favorite_on" if is_favorite else "context_favorite_off"
                )

                # Fallback icons if resource not present
                if not fav_icon or fav_icon.isNull():
                    fav_icon = self.style().standardIcon(
                        QStyle.StandardPixmap.SP_DialogYesButton
                    )

                fav_action = QAction(fav_text, self)
                fav_action.setIcon(fav_icon)
                fav_action.triggered.connect(
                    lambda _: self.toggle_favorite(audiobook_id, path)
                )
                menu.addAction(fav_action)

                # Tags Submenu (Batch compatible)
                tags_menu = menu.addMenu(tr("tags.menu_title"))
                tags_menu.setObjectName("libraryContextMenu")
                tags_menu.setIcon(
                    get_icon("context_tags")
                )  # Ensure icon exists or fallback logic if needed

                # Populate with existing tags
                all_tags = self.db.get_all_tags()
                if is_batch:
                    common_tag_ids = None
                    for bid, bp in batch_books:
                        tags = self.db.get_tags_for_audiobook(bid)
                        tids = {t["id"] for t in tags}
                        if common_tag_ids is None:
                            common_tag_ids = tids
                        else:
                            common_tag_ids.intersection_update(tids)
                    current_tag_ids = common_tag_ids if common_tag_ids is not None else set()
                else:
                    current_tags = self.db.get_tags_for_audiobook(audiobook_id)
                    current_tag_ids = {t["id"] for t in current_tags}

                if all_tags:
                    for tag in all_tags:
                        # Create checkable action for each tag
                        tag_action = QAction(tag["name"], self)
                        tag_action.setCheckable(True)
                        tag_action.setChecked(tag["id"] in current_tag_ids)

                        # Set color icon if available
                        if tag.get("color"):
                            pixmap = QPixmap(14, 14)
                            pixmap.fill(Qt.GlobalColor.transparent)

                            painter = QPainter(pixmap)
                            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                            # Draw colored rounded rect background
                            painter.setBrush(QColor(tag["color"]))
                            painter.setPen(Qt.PenStyle.NoPen)
                            painter.drawRoundedRect(0, 0, 14, 14, 3, 3)

                            # Draw an accent-colored dot in the middle if the tag is checked
                            if tag["id"] in current_tag_ids:
                                _, accent_color = StyleManager.get_theme_property("theme_primary")
                                painter.setBrush(accent_color)
                                painter.drawEllipse(5, 5, 4, 4)

                            painter.end()
                            tag_action.setIcon(QIcon(pixmap))

                        # Connect signal
                        tag_action.triggered.connect(
                            lambda checked,
                            tid=tag["id"],
                            p=path: self.toggle_tag_from_context_menu(
                                audiobook_id, tid, p, checked
                            )
                        )
                        tags_menu.addAction(tag_action)

                    tags_menu.addSeparator()

                assign_action = QAction(tr("tags.menu_assign"), self)
                assign_action.triggered.connect(
                    lambda _: self.open_tag_assignment(audiobook_id, path)
                )
                tags_menu.addAction(assign_action)

                clear_tags_action = QAction(tr("tags.menu_clear_all"), self)
                clear_tags_action.triggered.connect(
                    lambda _: self.clear_all_tags(audiobook_id, path)
                )
                if is_batch:
                    has_any_tags = False
                    for bid, bp in batch_books:
                        if self.db.get_tags_for_audiobook(bid):
                            has_any_tags = True
                            break
                    clear_tags_action.setEnabled(has_any_tags)
                else:
                    clear_tags_action.setEnabled(bool(current_tag_ids))
                tags_menu.addAction(clear_tags_action)

                menu.addSeparator()

                # Mark Read/Unread Actions (Batch compatible)
                mark_read_action = QAction(tr("library.menu_mark_read"), self)
                mark_read_action.setIcon(get_icon("context_mark_read"))
                mark_read_action.triggered.connect(
                    lambda _: self.mark_as_read(audiobook_id, duration, path)
                )
                menu.addAction(mark_read_action)

                mark_unread_action = QAction(tr("library.menu_mark_unread"), self)
                mark_unread_action.setIcon(get_icon("context_mark_unread"))
                mark_unread_action.triggered.connect(
                    lambda _: self.mark_as_unread(audiobook_id, path)
                )
                menu.addAction(mark_unread_action)
                menu.addSeparator()

                # Convert to Opus Action (Batch compatible)
                convert_opus_action = QAction(tr("library.menu_convert_opus"), self)
                opus_icon = get_icon("opus")
                if opus_icon.isNull():
                    opus_icon = get_icon("context_edit_metadata")
                convert_opus_action.setIcon(opus_icon)
                convert_opus_action.triggered.connect(
                    lambda _, p=path: self.open_opus_converter(p)
                )
                menu.addAction(convert_opus_action)

                # 3. Non-batch operations / other
                # Edit Metadata
                edit_metadata_action = QAction(tr("library.menu_edit_metadata"), self)
                edit_metadata_action.setIcon(get_icon("context_edit_metadata"))
                edit_metadata_action.triggered.connect(
                    lambda _: self.open_metadata_editor(audiobook_id, path)
                )
                menu.addAction(edit_metadata_action)
                menu.addSeparator()

                # Copy Path
                copy_path_action = QAction(tr("library.menu_copy_path", "Copy Path"), self)
                copy_path_action.setIcon(get_icon("clipboard-copy"))
                copy_path_action.triggered.connect(lambda _, p=path: self.copy_paths_to_clipboard(p))
                menu.addAction(copy_path_action)

                # Open Folder
                open_folder_action = QAction(tr("library.menu_open_folder"), self)
                open_folder_action.setIcon(get_icon("context_open_folder"))
                open_folder_action.setEnabled(not is_batch)
                open_folder_action.triggered.connect(lambda _: self.open_folder(path))
                menu.addAction(open_folder_action)
                menu.addSeparator()

                # 4. Delete Action (Last line, single book only)
                delete_action = QAction(tr("library.menu_delete"), self)
                delete_action.setIcon(get_icon("delete"))
                delete_action.setEnabled(not is_batch)
                delete_action.triggered.connect(
                    lambda _: self.confirm_delete(audiobook_id, path)
                )
                menu.addAction(delete_action)

                menu.exec(self.tree.viewport().mapToGlobal(pos))

            elif role == "folder":
                # Folder context menu
                menu = QMenu(self.tree)
                menu.setObjectName("libraryContextMenu")

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
                merge_action.triggered.connect(
                    lambda _: self.on_merge_folders_requested(path)
                )
                menu.addAction(merge_action)

                menu.exec(self.tree.viewport().mapToGlobal(pos))

        finally:
            self.tree._suppress_scroll = False
            vbar.setValue(saved_scroll)


    def open_opus_converter(self, clicked_path: str):
        """Open Opus conversion dialog for the clicked book (or all selected in batch mode)"""
        print(f"[DEBUG] open_opus_converter called for clicked_path: {clicked_path}")
        from pathlib import Path

        library_root = Path(self.config.get("default_path", ""))
        ffprobe_raw = self.config.get("ffprobe_path", "resources/bin/ffprobe.exe")
        ffprobe_str = str(ffprobe_raw)
        ffmpeg_str  = ffprobe_str.replace("ffprobe", "ffmpeg")
        print(f"[DEBUG] library_root: {library_root}, ffprobe_path: {ffprobe_str}, ffmpeg_path: {ffmpeg_str}")

        # Determine which paths to convert
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and clicked_path in selected_paths and len(selected_paths) > 1
        print(f"[DEBUG] mass_mode: {mass_mode}, selected_paths: {selected_paths}, is_batch: {is_batch}")

        if is_batch:
            paths_to_convert = list(selected_paths)
        else:
            paths_to_convert = [clicked_path]
        print(f"[DEBUG] paths_to_convert: {paths_to_convert}")

        # Resolve to absolute paths
        abs_paths = []
        for p in paths_to_convert:
            abs_p = Path(p) if Path(p).is_absolute() else library_root / p
            exists = abs_p.exists()
            print(f"[DEBUG] Checking path: {p} -> Absolute: {abs_p} (exists: {exists})")
            if exists:
                abs_paths.append(str(abs_p))

        print(f"[DEBUG] abs_paths final list: {abs_paths}")
        if not abs_paths:
            print("[DEBUG] abs_paths is empty, returning without dialog")
            return

        # Blur parent window
        window = self.window()
        if hasattr(window, "apply_blur"):
            print("[DEBUG] Applying window blur")
            window.apply_blur()

        try:
            print("[DEBUG] Initializing OpusConversionDialog")
            dialog = OpusConversionDialog(
                parent=self,
                library_paths=abs_paths,
                ffmpeg_path=ffmpeg_str,
                ffprobe_path=ffprobe_str,
                max_workers=self.config.get("opus_workers", 0)
            )
            print("[DEBUG] Connecting dialog signals")
            dialog.file_converted.connect(
                lambda old, new, br: self.db.update_file_extension(old, new, br)
            )
            dialog.conversion_complete.connect(lambda: self.scan_requested.emit(""))
            print("[DEBUG] Executing dialog")
            dialog.exec()
            print("[DEBUG] Dialog finished")
        except Exception as e:
            print(f"[DEBUG] Error showing OpusConversionDialog: {e}")
            import traceback
            traceback.print_exc()

        if hasattr(window, "remove_blur"):
            print("[DEBUG] Removing window blur")
            window.remove_blur()

    def mark_as_read(self, audiobook_id, duration, path):
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            batch_books = []
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    batch_books.append((info_b[0], info_b[6] or 0.0, p))
            
            for bid, bdur, bp in batch_books:
                self.db.mark_audiobook_completed(bid, bdur)
                self.update_cache_item_status(bp, is_started=True, is_completed=True)
                item = self.find_item_by_path(self.tree.invisibleRootItem(), bp)
                if item:
                    current_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
                    is_favorite = False
                    if current_data and len(current_data) >= 3:
                        is_favorite = current_data[2]
                    item.setData(0, Qt.ItemDataRole.UserRole + 3, (True, True, is_favorite))
                    self.refresh_audiobook_item(bp)
            
            self.filter_audiobooks()
            window = self.window()
            if hasattr(window, "playback_controller"):
                current_id = window.playback_controller.current_audiobook_id
                if current_id in [b[0] for b in batch_books]:
                    window.update_ui_for_audiobook()
        else:
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
            if (
                hasattr(window, "playback_controller")
                and window.playback_controller.current_audiobook_id == audiobook_id
            ):
                window.update_ui_for_audiobook()

    def mark_as_unread(self, audiobook_id, path):
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            batch_books = []
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    batch_books.append((info_b[0], p))
            
            for bid, bp in batch_books:
                self.db.reset_audiobook_status(bid)
                self.update_cache_item_status(bp, is_started=False, is_completed=False)
                item = self.find_item_by_path(self.tree.invisibleRootItem(), bp)
                if item:
                    current_data = item.data(0, Qt.ItemDataRole.UserRole + 3)
                    is_favorite = False
                    if current_data and len(current_data) >= 3:
                        is_favorite = current_data[2]
                    item.setData(0, Qt.ItemDataRole.UserRole + 3, (False, False, is_favorite))
                    self.refresh_audiobook_item(bp)
            
            self.filter_audiobooks()
            window = self.window()
            if hasattr(window, "playback_controller"):
                current_id = window.playback_controller.current_audiobook_id
                if current_id in [b[0] for b in batch_books]:
                    window.playback_controller.saved_file_index = 0
                    window.playback_controller.saved_position = 0
                    window.update_ui_for_audiobook()
        else:
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
            if (
                hasattr(window, "playback_controller")
                and window.playback_controller.current_audiobook_id == audiobook_id
            ):
                window.playback_controller.saved_file_index = 0
                window.playback_controller.saved_position = 0
                window.update_ui_for_audiobook()

    def toggle_favorite(self, audiobook_id: int, path: str):
        """Toggle favorite status and refresh item"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            any_not_fav = False
            batch_books = []
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    batch_books.append((info_b[0], p))
                    book_data = self.db.get_audiobook_by_path(p)
                    if book_data and not book_data.get("is_favorite", False):
                        any_not_fav = True
            
            target_state = any_not_fav
            any_removed = False
            
            for bid, bp in batch_books:
                book_data = self.db.get_audiobook_by_path(bp)
                if book_data:
                    curr_fav = book_data.get("is_favorite", False)
                    if curr_fav != target_state:
                        self.db.toggle_favorite(bid)
                        if not target_state:
                            any_removed = True
                self.refresh_audiobook_item(bp)
            
            if self.is_favorites_filter_active and any_removed:
                self.load_audiobooks(use_cache=False)
        else:
            new_state = self.db.toggle_favorite(audiobook_id)
            self.refresh_audiobook_item(path)

            # If we are in Favorites filter mode and we removed it, reload to hide it
            if self.is_favorites_filter_active and not new_state:
                self.load_audiobooks(use_cache=False)

    def open_tag_assignment(self, audiobook_id, path):
        """Open dialog to assign tags to audiobook"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            audiobook_ids = []
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    audiobook_ids.append(info_b[0])
            dialog = TagManagerDialog(self.db, self, audiobook_ids)
        else:
            dialog = TagManagerDialog(self.db, self, audiobook_id)

        if dialog.exec():
            # Refresh items to show new tags
            if is_batch:
                for p in selected_paths:
                    self.refresh_audiobook_item(p)
            else:
                self.refresh_audiobook_item(path)

    def toggle_tag_from_context_menu(
        self, audiobook_id: int, tag_id: int, path: str, checked: bool
    ):
        """Handle toggling a tag directly from the context menu"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    bid = info_b[0]
                    if checked:
                        self.db.add_tag_to_audiobook(bid, tag_id)
                    else:
                        self.db.remove_tag_from_audiobook(bid, tag_id)
                    self.refresh_audiobook_item(p)
        else:
            if checked:
                self.db.add_tag_to_audiobook(audiobook_id, tag_id)
            else:
                self.db.remove_tag_from_audiobook(audiobook_id, tag_id)
            self.refresh_audiobook_item(path)

    def clear_all_tags(self, audiobook_id: int, path: str):
        """Remove all tags from an audiobook"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    bid = info_b[0]
                    self.db.remove_all_tags_from_audiobook(bid)
                    self.refresh_audiobook_item(p)
        else:
            self.db.remove_all_tags_from_audiobook(audiobook_id)
            # Refresh the UI for this item
            self.refresh_audiobook_item(path)

    def open_metadata_editor(self, audiobook_id: int, path: str):
        """Open dialog to edit audiobook metadata (author, title, narrator, language, year_written, year_recorded)"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and path in selected_paths and len(selected_paths) > 1

        if is_batch:
            batch_books = []
            for p in selected_paths:
                info_b = self.db.get_audiobook_info(p)
                if info_b:
                    batch_books.append((info_b[0], p))
            audiobook_ids = [b[0] for b in batch_books]
            dialog = MetadataEditDialog(self.db, audiobook_ids, self)
        else:
            dialog = MetadataEditDialog(self.db, audiobook_id, self)

        self.apply_blur()
        if dialog.exec():
            if is_batch:
                fields = dialog.get_enabled_fields()
                if fields:
                    self.db.update_multiple_audiobooks_metadata_fields(audiobook_ids, fields)
                    for bid, bp in batch_books:
                        self.refresh_audiobook_item(bp)
            else:
                # Get updated data
                author, title, narrator, language, year_written, year_recorded = dialog.get_data()

                # Update database
                self.db.update_audiobook_metadata(audiobook_id, author, title, narrator, language, year_written, year_recorded)

                # Refresh UI item
                self.refresh_audiobook_item(path)

            # If currently filtered by text, re-apply filter in case metadata changed visibility
            if self.search_edit.text():
                self.filter_audiobooks()
        self.remove_blur()

    def confirm_delete(self, audiobook_id: int, path: str):
        """Ask for user confirmation before proceeding with book deletion"""
        display_path = os.path.basename(path)
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(tr("library.confirm_delete_title"))
        msg_box.setText(trf("library.confirm_delete_msg", path=display_path))
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        checkbox = QCheckBox(tr("library.delete_from_disk_checkbox"))
        msg_box.setCheckBox(checkbox)
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        self.apply_blur()
        try:
            reply = msg_box.exec()
        finally:
            self.remove_blur()

        if reply == QMessageBox.StandardButton.Yes:
            delete_from_disk = checkbox.isChecked()
            self.delete_requested.emit(audiobook_id, path, delete_from_disk)

    def remove_audiobook_from_ui(self, path: str):
        """Cleanly remove an audiobook from the library tree and internal cache"""
        # 1. Synchronize the in-memory cache
        if self.cached_library_data:
            found = False
            for parent, items in self.cached_library_data.items():
                for i, item in enumerate(items):
                    if item["path"] == path:
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
            self._recalculate_ancestors_stats(parent)

        # 3. Refresh status metrics in the main window
        window = self.window()
        total_count = self.db.get_audiobook_count()
        # Update placeholder state
        self.tree.has_any_content = total_count > 0
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                trf("status.library_count", count=total_count)
            )

    def _recalculate_ancestors_stats(self, parent_item: QTreeWidgetItem):
        """Recursively update folder stats up to the root, removing folders if they become empty"""
        if not parent_item or parent_item == self.tree.invisibleRootItem():
            return

        item_type = parent_item.data(0, Qt.ItemDataRole.UserRole + 1)
        if item_type != "folder":
            return

        books_count, total_seconds = self._get_folder_stats(parent_item)
        if books_count == 0:
            # If folder is empty now, remove it and update its parent
            grandparent = parent_item.parent() or self.tree.invisibleRootItem()
            grandparent.removeChild(parent_item)
            self._recalculate_ancestors_stats(grandparent)
        else:
            # Update folder text
            folder_name = parent_item.data(0, Qt.ItemDataRole.UserRole + 5) or parent_item.text(0)
            if " (" in folder_name and folder_name.endswith(")"):
                folder_name = folder_name.rsplit(" (", 1)[0]
                
            duration_str = format_duration(total_seconds)
            books_str = self._format_books_count(books_count)
            parent_item.setText(0, f"{folder_name} ({books_str}, {duration_str})")
            
            # Propagate upwards
            self._recalculate_ancestors_stats(parent_item.parent())

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
            trf(
                "library.confirm_delete_folder_msg", path=display_path, items=items_str
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.perform_virtual_merge(path)

    def perform_virtual_merge(self, path: str):
        """Mark folder as merged in DB and trigger rescan"""
        try:
            self.db.set_folder_merged(path, True)
            # Trigger a rescan to update the library structure
            self.scan_requested.emit(path)
        except Exception as e:
            QMessageBox.critical(
                self, tr("window.title"), f"Error merging folders: {str(e)}"
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
                        item for item in items if item["path"] != path
                    ]

            # Recursive removal of nested paths from cache
            prefix = path + os.sep
            for parent in list(self.cached_library_data.keys()):
                if parent.startswith(prefix):
                    del self.cached_library_data[parent]
                else:
                    self.cached_library_data[parent] = [
                        item
                        for item in self.cached_library_data[parent]
                        if not item["path"].startswith(prefix)
                    ]

        # 2. Prune the visual tree
        item = self.find_item_by_path(self.tree.invisibleRootItem(), path)
        if item:
            parent = item.parent() or self.tree.invisibleRootItem()
            parent.removeChild(item)

        # 3. Synchronize status metrics
        window = self.window()
        total_count = self.db.get_audiobook_count()
        # Update placeholder state
        self.tree.has_any_content = total_count > 0
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                trf("status.library_count", count=total_count)
            )

    def open_folder(self, path: str):
        if not path:
            return
        try:
            default_path = self.config.get("default_path", "")
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
                if sys.platform == "win32":
                    import ctypes

                    ctypes.windll.shell32.ShellExecuteW(
                        None, "open", folder_path_str, None, None, 1
                    )
                elif sys.platform == "darwin":
                    subprocess.run(["open", folder_path_str], check=False)
                else:
                    subprocess.run(["xdg-open", folder_path_str], check=False)
            else:
                QMessageBox.warning(
                    self, tr("window.title"), f"Path not found: {folder_path}"
                )
        except Exception as e:
            QMessageBox.critical(self, tr("window.title"), f"Error opening folder: {e}")

    def copy_paths_to_clipboard(self, clicked_path: str):
        """Copy resolved absolute paths of selected audiobooks to the clipboard"""
        selected_paths = getattr(self.tree, "selected_audiobook_paths", set())
        mass_mode = getattr(self.tree, "mass_selection_mode", False)
        is_batch = mass_mode and clicked_path in selected_paths and len(selected_paths) > 1

        if is_batch:
            paths_to_copy = list(selected_paths)
        else:
            paths_to_copy = [clicked_path]

        library_root = Path(self.config.get("default_path", ""))
        resolved_paths = []
        for p in paths_to_copy:
            abs_p = Path(p) if Path(p).is_absolute() else library_root / p
            resolved_paths.append(str(abs_p.resolve()))

        # Join paths with a newline
        clipboard_text = "\n".join(resolved_paths)

        # Copy to clipboard
        QApplication.clipboard().setText(clipboard_text)

        # Show status feedback
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                trf("status.copy_complete", count=len(resolved_paths))
            )

    def on_item_double_clicked(self, item, column):
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "audiobook":
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

        if self.delegate:
            self.delegate.playing_path = audiobook_path
        self.update_tile_playback_state()

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
        if self.current_filter == "in_progress":
            self.load_audiobooks(use_cache=False)
            return

        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
        data = self.db.get_audiobook_by_path(audiobook_path)
        if data:
            item.setData(
                0,
                Qt.ItemDataRole.UserRole + 2,
                (
                    data["author"],
                    data["title"],
                    data["narrator"],
                    data["file_count"],
                    data["duration"],
                    data["listened_duration"],
                    data["progress_percent"],
                    data["codec"],
                    data["bitrate_min"],
                    data["bitrate_max"],
                    data["bitrate_mode"],
                    data["container"],
                    data.get("description", ""),
                    data.get("total_size", 0),
                    data.get("language"),
                    data.get("year_written"),
                    data.get("year_recorded"),
                ),
            )
            if "is_started" in data and "is_completed" in data:
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole + 3,
                    (data["is_started"], data["is_completed"], data["is_favorite"]),
                )

            # Refresh tags
            info = self.db.get_audiobook_info(audiobook_path)
            if info:
                tags = self.db.get_tags_for_audiobook(info[0])
                item.setData(0, Qt.ItemDataRole.UserRole + 4, tags)

            # Refresh and scale the audiobook cover
            cover_icon = None
            cover_p_str = data.get("cached_cover_path")
            if not cover_p_str:
                cover_p_str = data.get("cover_path")

            if cover_p_str:
                cover_p = Path(cover_p_str)
                if not cover_p.is_absolute() and self.config.get("default_path"):
                    cover_p = Path(self.config.get("default_path")) / cover_p

                from utils import load_icon
                # Clear LRU cache of load_icon to force reload of the potentially updated/overwritten image
                load_icon.cache_clear()
                cover_icon = load_icon(
                    cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
                )
            item.setIcon(0, cover_icon or self.default_audiobook_icon)
            item.setData(0, Qt.ItemDataRole.UserRole + 5, cover_p_str)

            item.setText(0, item.text(0))
            self.update_cache_item_status(
                audiobook_path, data["is_started"], data["is_completed"]
            )
            self.tree.viewport().update()
            if self.is_tile_view and hasattr(self, "tile_view"):
                self.tile_view.refresh_tile(audiobook_path)

    def update_item_progress(
        self, audiobook_path: str, listened_duration: float, progress_percent: int
    ):
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
            if self.is_tile_view and hasattr(self, "tile_view"):
                self.tile_view.refresh_tile(audiobook_path)

    def update_cache_item_status(self, path: str, is_started: bool, is_completed: bool):
        if not self.cached_library_data:
            return
        found = False
        for parent, items in self.cached_library_data.items():
            for item in items:
                if item["path"] == path:
                    item["is_started"] = is_started
                    item["is_completed"] = is_completed
                    # is_favorite is not cached here for now, as it requires a DB reload for full consistency
                    # but we could add it if needed.
                    found = True
                    break
            if found:
                break

    def reveal_current_audiobook(self, audiobook_path: str):
        """Clear search filter and scroll to the specified audiobook"""
        # Clear search filter to ensure the audiobook is visible
        self.search_edit.clear()

        # Scroll to the audiobook (it's already highlighted by the delegate)
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
            self.tree.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)

    def update_texts(self):
        if hasattr(self, "btn_show_folders"):
            self.btn_show_folders.setToolTip(tr("library.tooltip_show_folders"))
        if hasattr(self, "btn_tile_view"):
            self.btn_tile_view.setToolTip(tr("library.tooltip_tile_view"))
        if hasattr(self, "btn_mass_select"):
            self.btn_mass_select.setToolTip(tr("library.tooltip_mass_select"))
        if hasattr(self, "btn_mass_select_arrow"):
            self.btn_mass_select_arrow.setToolTip(tr("library.tooltip_mass_select"))
        if hasattr(self, "btn_favorites"):
            self.btn_favorites.setToolTip(tr("library.tooltip_favorites"))
        if hasattr(self, "btn_tags"):
            self.btn_tags.setToolTip(tr("library.tooltip_tags"))
        if hasattr(self, "btn_meta_filter"):
            self.btn_meta_filter.setToolTip(tr("library.tooltip_filter_metadata"))
        if hasattr(self, "btn_meta_filter_arrow"):
            self.btn_meta_filter_arrow.setToolTip(tr("library.tooltip_filter_metadata"))
        self.update_sort_button_ui()
        self.update_sort_field_button_ui()
            
        self.update_filter_labels()
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                self.filter_buttons[filter_id].setToolTip(
                    tr(f"library.tooltip_filter_{filter_id}")
                )
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))
        if hasattr(self, "tile_flow") and self.tile_flow:
            self.tile_flow.update_texts()

    def apply_blur(self):
        """Walk parent chain to find and call apply_blur on the main window"""
        p = self.parent()
        while p:
            if hasattr(p, 'apply_blur'):
                p.apply_blur()
                return
            p = p.parent()

    def remove_blur(self):
        """Walk parent chain to find and call remove_blur on the main window"""
        p = self.parent()
        while p:
            if hasattr(p, 'remove_blur'):
                p.remove_blur()
                return
            p = p.parent()

    def collapse_all_folders(self):
        """Collapse all folders in the library tree"""
        self.tree.collapseAll()

    def expand_all_folders(self):
        """Expand all folders in the library tree"""
        self.tree.expandAll()

    def update_sort_button_ui(self):
        """Update the sort button icon and tooltip based on the current sort order"""
        if hasattr(self, "btn_sort"):
            if self.sort_order == "asc":
                self.btn_sort.setIcon(get_icon("arrow-up-narrow-wide"))
                self.btn_sort.setToolTip(tr("library.tooltip_sort_asc"))
            else:
                self.btn_sort.setIcon(get_icon("arrow-down-wide-narrow"))
                self.btn_sort.setToolTip(tr("library.tooltip_sort_desc"))

    def toggle_sort_order(self):
        """Toggle alphabetical sorting direction and refresh library"""
        self.sort_order = "desc" if self.sort_order == "asc" else "asc"
        self.update_sort_button_ui()
        self.sort_order_changed.emit(self.current_filter, self.sort_order, self.sort_field)
        self.load_audiobooks(use_cache=True)

    def show_sort_field_menu(self):
        """Display a popup menu to select the active sort field"""
        menu = QMenu(self)
        menu.setObjectName("sortFieldMenu")
        
        options = [
            ("name", "library.sort_by_name"),
            ("author", "library.sort_by_author"),
            ("duration", "library.sort_by_duration"),
            ("time_added", "library.sort_by_date_added"),
            ("last_updated", "library.sort_by_last_read"),
            ("time_finished", "library.sort_by_date_finished"),
            ("progress_percent", "library.sort_by_progress"),
            ("year_written", "library.sort_by_year_written"),
            ("year_recorded", "library.sort_by_year_recorded"),
            ("language", "library.sort_by_language")
        ]
        
        current = self.sort_field
        for field_key, loc_key in options:
            action = menu.addAction(tr(loc_key))
            action.setCheckable(True)
            action.setChecked(field_key == current)
            action.triggered.connect(lambda checked, fk=field_key: self._on_sort_field_selected(fk))
            
        global_pos = self.btn_sort_field.mapToGlobal(QPoint(0, self.btn_sort_field.height()))
        menu.exec(global_pos)

    def _on_sort_field_selected(self, field_key):
        self.sort_field = field_key
        self.update_sort_field_button_ui()
        self.sort_order_changed.emit(self.current_filter, self.sort_order, self.sort_field)
        self.load_audiobooks(use_cache=True)

    def update_sort_field_button_ui(self):
        """Update the sort field button tooltip based on the current sort field"""
        if hasattr(self, "btn_sort_field"):
            field_map = {
                "name": "sort_by_name",
                "author": "sort_by_author",
                "duration": "sort_by_duration",
                "time_added": "sort_by_date_added",
                "last_updated": "sort_by_last_read",
                "time_finished": "sort_by_date_finished",
                "progress_percent": "sort_by_progress",
                "year_written": "sort_by_year_written",
                "year_recorded": "sort_by_year_recorded",
                "language": "sort_by_language"
            }
            loc_key = field_map.get(self.sort_field, "sort_by_name")
            field_name = tr(f"library.{loc_key}")
            self.btn_sort_field.setToolTip(f"{tr('library.tooltip_sort_field')} ({field_name})")

    def toggle_meta_filter(self):
        """Toggle the active state of metadata filter"""
        self.is_meta_filter_active = self.btn_meta_filter.isChecked()
        self.load_audiobooks(use_cache=True)

    def show_meta_filter_menu(self):
        """Display a popup menu to select the active metadata filter"""
        menu = QMenu(self)
        menu.setObjectName("metaFilterMenu")
        
        options = [
            ("no_cover", "library.filter_no_cover"),
            ("no_author", "library.filter_no_author"),
            ("no_narrator", "library.filter_no_narrator")
        ]
        
        current = self.current_meta_filter
        for filter_key, loc_key in options:
            translated = tr(loc_key)
            if translated == loc_key:
                fallbacks = {
                    "library.filter_no_cover": "No cover",
                    "library.filter_no_author": "No author",
                    "library.filter_no_narrator": "No narrator"
                }
                translated = fallbacks.get(loc_key, loc_key)
                
            action = menu.addAction(translated)
            action.setCheckable(True)
            action.setChecked(filter_key == current)
            action.triggered.connect(lambda checked, fk=filter_key: self._on_meta_filter_selected(fk))
            
        menu.addSeparator()
        
        # "Without language" option
        translated_none = tr("library.language_none")
        if translated_none == "library.language_none":
            translated_none = "Without Language"
        act_none = menu.addAction(translated_none)
        act_none.setCheckable(True)
        act_none.setChecked(current == "lang:none")
        act_none.triggered.connect(lambda checked: self._on_meta_filter_selected("lang:none"))
        
        # List of unique languages
        langs = self.get_available_languages()
        if langs:
            for lang in langs:
                filter_key = f"lang:{lang}"
                action = menu.addAction(lang)
                action.setCheckable(True)
                action.setChecked(filter_key == current)
                action.triggered.connect(lambda checked, fk=filter_key: self._on_meta_filter_selected(fk))
            
        global_pos = self.btn_meta_filter_arrow.mapToGlobal(QPoint(0, self.btn_meta_filter_arrow.height()))
        menu.exec(global_pos)

    def _on_meta_filter_selected(self, filter_key):
        self.current_meta_filter = filter_key
        self.is_meta_filter_active = True
        if hasattr(self, "btn_meta_filter"):
            self.btn_meta_filter.setChecked(True)
        self.load_audiobooks(use_cache=True)

    def _matches_meta_filter(self, item_data) -> bool:
        """Check if an item matches the active metadata/language filter requirements"""
        if not self.is_meta_filter_active:
            return True
            
        if item_data.get("is_folder"):
            return True
            
        if self.current_meta_filter == "no_cover":
            cover_p_str = item_data.get("cached_cover_path") or item_data.get("cover_path")
            has_cover = False
            if cover_p_str:
                try:
                    cover_p = Path(cover_p_str)
                    if not cover_p.is_absolute() and self.config.get("default_path"):
                        cover_p = Path(self.config.get("default_path")) / cover_p
                    if cover_p.exists():
                        has_cover = True
                except Exception:
                    pass
            return not has_cover
            
        elif self.current_meta_filter == "no_author":
            author = item_data.get("author")
            is_empty_author = (
                not author
                or not author.strip()
                or author.strip() == "(unknown author)"
                or author.strip() == "(неизвестный автор)"
                or author.strip() == tr("scanner.unknown_author")
            )
            return is_empty_author
            
        elif self.current_meta_filter == "no_narrator":
            narrator = item_data.get("narrator")
            is_empty_narrator = (
                not narrator
                or not narrator.strip()
                or narrator.strip().lower() in ("(unknown narrator)", "(неизвестный чтец)", "(без чтеца)")
            )
            return is_empty_narrator

        elif self.current_meta_filter == "lang:none":
            lang = item_data.get("language")
            return not (lang and lang.strip())

        elif self.current_meta_filter.startswith("lang:"):
            target_lang = self.current_meta_filter[5:]
            lang = item_data.get("language")
            if not lang or not lang.strip():
                return False
            return lang.strip().lower() == target_lang.lower()
            
        return True

    def get_available_languages(self):
        """Scan cached library for unique book languages"""
        langs = set()
        if self.cached_library_data:
            for parent_path, items in self.cached_library_data.items():
                for item in items:
                    if not item.get("is_folder"):
                        lang = item.get("language")
                        if lang and lang.strip():
                            langs.add(lang.strip())
        # Sort case-insensitively
        return sorted(list(langs), key=lambda s: s.lower())

    def show_mass_select_menu(self):
        """Display a popup menu for mass selection actions (select all, deselect all)"""
        menu = QMenu(self)
        menu.setObjectName("massSelectMenu")
        
        select_all_action = menu.addAction(tr("library.menu_select_all"))
        select_all_action.triggered.connect(self.select_all_audiobooks)
        
        deselect_all_action = menu.addAction(tr("library.menu_deselect_all"))
        deselect_all_action.triggered.connect(self.deselect_all_audiobooks)
        
        global_pos = self.btn_mass_select_arrow.mapToGlobal(QPoint(0, self.btn_mass_select_arrow.height()))
        menu.exec(global_pos)

    def get_all_visible_audiobook_paths(self):
        """Recursively collect paths of all visible audiobook items in the tree"""
        paths = []
        def traverse(item):
            if item.isHidden():
                return
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "audiobook":
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if path:
                    paths.append(path)
            for i in range(item.childCount()):
                traverse(item.child(i))

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            traverse(root.child(i))
        return paths

    def select_all_audiobooks(self):
        """Enable mass selection mode and select all currently visible audiobooks"""
        if not self.tree.mass_selection_mode:
            self.btn_mass_select.setChecked(True)
            self.on_mass_select_toggled(True)
        
        visible_paths = self.get_all_visible_audiobook_paths()
        self.tree.selected_audiobook_paths.update(visible_paths)
        self.tree._sync_all_folder_checkbox_states()
        self.tree.viewport().update()

    def deselect_all_audiobooks(self):
        """Clear all selected audiobook paths"""
        self.tree.selected_audiobook_paths.clear()
        self.tree.viewport().update()
