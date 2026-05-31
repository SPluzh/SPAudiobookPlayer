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
    QStackedWidget,
    QListView,
    QAbstractItemView,
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
    QFontMetrics,
    QTextCursor,
    QCursor,
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
        # Styles moved to dark.qss (#TagPopupFrame, #popupTagList, #popupSeparator)

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
            count = scanner.scan_directory(self.root_path)

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

        # UI state for interaction
        self.hovered_index = None
        self.mouse_pos = None

        # Nesting lines color palette
        self.NESTING_COLORS = [
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

    @lru_cache(maxsize=32)
    def _get_style(self, style_name: str) -> tuple[QFont, QColor]:
        """Fetch font and color settings from the style manager mapped to the given name"""
        return StyleManager.get_theme_property(style_name)

    def update_styles(self):
        """Force a refresh of style properties from the loaded QSS"""
        self._get_style.cache_clear()
        # Proxy widgets in StyleManager handle themselves when ensurePolished is called

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
        tree = self.parent()
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
        tree = self.parent()
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

        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_rect = QRect(
            icon_rect.right() + 8,
            option.rect.top(),
            option.rect.right() - icon_rect.right() - 18,
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
        if item_type != "audiobook":
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

        # Unpack status data for favorites and progress tracking
        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
        is_favorite = False
        is_started = False
        if status_data and len(status_data) >= 3:
            is_started = bool(status_data[0])
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

        text_x = icon_rect.right() + 15
        text_y = option.rect.top() + self.vertical_padding
        available_width = option.rect.right() - text_x - self.horizontal_padding

        # Author field
        if author:
            font, color = self._get_style("delegate_author")
            painter.setFont(font)
            painter.setPen(color)

            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, author
            )
            text_y += line_height + self.line_spacing

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

        # NARRATOR Metadata
        if narrator:
            font, color = self._get_style("delegate_narrator")
            painter.setFont(font)
            painter.setPen(color)

            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            narrator_text = f"{tr('delegate.narrator_prefix')} {narrator}"
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                narrator_text,
            )
            text_y += line_height + self.line_spacing

        # STATUS INFO LINE (Files, Duration, Progress)
        info_parts = []

        # Listening progress percentage
        font_prog, color_prog = self._get_style("delegate_progress")
        progress_text = trf("delegate.progress", percent=int(progress_percent))
        info_parts.append((progress_text, font_prog, color_prog))

        # File list count
        if file_count:
            font_fc, color_fc = self._get_style("delegate_file_count")
            files_text = f"{tr('delegate.files_prefix')} {file_count}"
            info_parts.append((files_text, font_fc, color_fc))

        # Overall duration
        if duration:
            font_dur, color_dur = self._get_style("delegate_duration")
            duration_text = (
                f"{tr('delegate.duration_prefix')} {format_duration(duration)}"
            )
            info_parts.append((duration_text, font_dur, color_dur))

        # Total size metadata
        if total_size:
            font_sz, color_sz = self._get_style("delegate_file_count")
            size_prefix = tr("delegate.size_prefix", default="💾")
            size_text = f"{size_prefix} {format_size(total_size)}"
            info_parts.append((size_text, font_sz, color_sz))

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
                font_tech, color_tech = self._get_style("delegate_file_count")
                info_parts.append((full_tech_text, font_tech, color_tech))

        # Draw consolidated info line with custom formatting/spacing
        if info_parts and getattr(self, "show_detailed_info", True):
            current_x = text_x
            for i, (text, font, color) in enumerate(info_parts):
                painter.setFont(font)
                painter.setPen(color)

                text_width = painter.fontMetrics().horizontalAdvance(text)
                line_height = painter.fontMetrics().height()

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



class TileDelegate(QStyledItemDelegate):
    def __init__(self, config, parent_list):
        super().__init__(parent_list)
        self.config = config
        self.parent_list = parent_list
        
    def get_icon_rect(self, rect: QRectF) -> QRectF:
        icon_size = self.config.get("audiobook_icon_size", 100)
        icon_y = rect.top() + (rect.height() - icon_size) / 2.0
        return QRectF(
            rect.left() + (rect.width() - icon_size) / 2.0,
            icon_y,
            icon_size,
            icon_size
        )

    def get_play_rect(self, rect: QRectF) -> QRectF:
        icon_rect = self.get_icon_rect(rect)
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(
            center.x() - btn_size / 2.0,
            center.y() - btn_size / 2.0,
            btn_size,
            btn_size
        )

    def get_fav_rect(self, rect: QRectF) -> QRectF:
        icon_rect = self.get_icon_rect(rect)
        heart_size = 18.0
        return QRectF(
            icon_rect.right() - heart_size - 4,
            icon_rect.top() + 4,
            heart_size,
            heart_size
        )

    def paint(self, painter, option, index):
        try:
            item_type = index.data(Qt.ItemDataRole.UserRole + 1)
            if item_type == "audiobook":
                self._paint_audiobook(painter, option, index)
            else:
                super().paint(painter, option, index)
        except Exception as e:
            import traceback
            print(f"ERROR: Exception in TileDelegate.paint: {e}")
            traceback.print_exc()

    def _paint_audiobook(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(option.rect)
        
        # Deduce status from library delegate
        tree_delegate = self.parent_list.library.delegate
        playing_path = tree_delegate.playing_path if tree_delegate else None
        is_paused = tree_delegate.is_paused if tree_delegate else False
        
        path = index.data(Qt.ItemDataRole.UserRole)
        is_playing_this = playing_path and path == playing_path
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        
        is_hovered = (self.parent_list.hovered_item and self.parent_list.hovered_item == self.parent_list.itemFromIndex(index))
        
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        progress_percent = 0
        if data and len(data) >= 7:
            progress_percent = data[6]
            
        status_data = index.data(Qt.ItemDataRole.UserRole + 3)
        is_started = False
        is_completed = False
        is_favorite = False
        if status_data and len(status_data) >= 3:
            is_started = bool(status_data[0])
            is_completed = bool(status_data[1])
            is_favorite = bool(status_data[2])
            
        icon_size = self.config.get("audiobook_icon_size", 100)
        has_progress = (progress_percent > 0 or is_started)
        pb_h = 5.0
        
        # Center icon (with progress bar) vertically within the actual rect height
        total_content_height = icon_size + (pb_h if has_progress else 0)
        icon_y = rect.top() + (rect.height() - total_content_height) / 2.0
        
        icon_rect = QRectF(
            rect.left() + (rect.width() - icon_size) / 2.0,
            icon_y,
            icon_size,
            icon_size
        )
        
        # Draw rounded cover with clipping (matching 3px list view rounding)
        if icon:
            painter.save()
            path_clipper = QPainterPath()
            path_clipper.addRoundedRect(icon_rect, 3.0, 3.0)
            painter.setClipPath(path_clipper)
            icon.paint(painter, icon_rect.toRect())
            
            # Hover overlay (semi-transparent gray tint)
            if is_hovered:
                _, overlay_bg = StyleManager.get_theme_property("overlay_background")
                painter.fillRect(icon_rect, overlay_bg)
                
            painter.restore()
            
        # Draw Active Highlight Border (matching list view glowing border)
        if is_playing_this:
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            pen = QPen(accent_color, 8)
            painter.save()
            painter.setPen(pen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            if has_progress:
                highlight_rect = QRectF(
                    icon_rect.left(),
                    icon_rect.top(),
                    icon_rect.width(),
                    icon_rect.height() + pb_h,
                )
            else:
                highlight_rect = QRectF(icon_rect)
                
            painter.drawRoundedRect(highlight_rect.adjusted(-4, -4, 4, 4), 7.0, 7.0)
            painter.restore()
            
        # Draw Progress Bar at the bottom (matching list view flat bar below cover)
        if has_progress:
            painter.save()
            pb_rect = QRectF(
                icon_rect.left(),
                icon_rect.bottom(),
                icon_rect.width(),
                pb_h
            )
            
            # Background
            _, bg_color = StyleManager.get_theme_property("overlay_progress_bg")
            painter.fillRect(pb_rect, bg_color)
            
            # Fill progress
            fill_w = pb_rect.width() * progress_percent / 100.0
            if fill_w > 0:
                fill_rect = QRectF(
                    pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height()
                )
                _, primary_color = StyleManager.get_theme_property("theme_primary")
                painter.fillRect(fill_rect, primary_color)
                
            painter.restore()
            
        # Draw Favorite (Heart) in top-right corner
        if is_favorite:
            painter.save()
            heart_size = 18.0
            heart_rect = QRectF(
                icon_rect.right() - heart_size - 4,
                icon_rect.top() + 4,
                heart_size,
                heart_size
            )
            _, bg_color = StyleManager.get_theme_property("icon_background")
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(heart_rect)
            
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            painter.setBrush(accent_color)
            hr = heart_rect.adjusted(1, 2, -1, -2)
            
            path_heart = QPainterPath()
            path_heart.moveTo(hr.center().x(), hr.bottom())
            path_heart.cubicTo(hr.right(), hr.center().y(), hr.right(), hr.top(), hr.center().x(), hr.top() + hr.height() * 0.2)
            path_heart.cubicTo(hr.left(), hr.top(), hr.left(), hr.center().y(), hr.center().x(), hr.bottom())
            
            painter.drawPath(path_heart)
            painter.restore()
            
        # Draw Completed checkmark in top-left corner
        if is_completed:
            painter.save()
            check_size = 18.0
            check_rect = QRectF(
                icon_rect.left() + 4,
                icon_rect.top() + 4,
                check_size,
                check_size
            )
            _, bg_color = StyleManager.get_theme_property("icon_background")
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(check_rect)
            
            painter.setPen(QPen(QColor("#2ecc71"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            cx = check_rect.left() + check_size * 0.25
            cy = check_rect.top() + check_size * 0.5
            painter.drawLine(QPointF(cx, cy), QPointF(cx + check_size * 0.2, cy + check_size * 0.2))
            painter.drawLine(QPointF(cx + check_size * 0.2, cy + check_size * 0.2), QPointF(cx + check_size * 0.55, cy - check_size * 0.15))
            painter.restore()
            
        # Draw Play/Pause Overlay in center when hovered or active
        if is_hovered or is_playing_this:
            play_btn_rect = self.get_play_rect(rect)

            # Precise mouse hover check
            is_over_btn = False
            mouse_pos = getattr(self.parent_list, "mouse_pos", None)
            if mouse_pos and play_btn_rect.contains(QPointF(mouse_pos)):
                is_over_btn = True

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Button circle
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            btn_color = QColor(accent_color)
            if not is_over_btn:
                btn_color.setAlpha(200)
            else:
                btn_color = btn_color.lighter(110)

            painter.setBrush(btn_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(play_btn_rect)

            # Play/Pause Icon shapes
            painter.setBrush(Qt.GlobalColor.white)
            painter.setPen(Qt.PenStyle.NoPen)
            if is_playing_this and not is_paused:
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
            
        painter.restore()


class BookGridList(QListWidget):
    def __init__(self, books, library, parent_item, parent=None):
        super().__init__(parent)
        self.books = books
        self.library = library
        self.parent_item = parent_item
        self.hovered_item = None
        self.mouse_pos = None
        
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWrapping(True)
        self.setWordWrap(False)
        self.setSpacing(8)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._updating_height = False
        self.setObjectName("folderGridList")
        
        self.setItemDelegate(TileDelegate(self.library.config, self))
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)
        
        self.itemClicked.connect(self.on_item_clicked)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.itemEntered.connect(self.on_item_entered)
        
        self.populate_books()

    def populate_books(self):
        self.clear()
        for data in self.books:
            item = QListWidgetItem(self)
            item.setData(Qt.ItemDataRole.UserRole, data["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1, "audiobook")
            item.setData(
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
                )
            )
            item.setData(
                Qt.ItemDataRole.UserRole + 3,
                (data["is_started"], data["is_completed"], data["is_favorite"])
            )
            if "tags" in data:
                item.setData(Qt.ItemDataRole.UserRole + 4, data["tags"])
                
            cover_icon = None
            cover_p_str = data.get("cached_cover_path") or data.get("cover_path")
            if cover_p_str:
                cover_p = Path(str(cover_p_str))
                if not cover_p.is_absolute() and self.library.config.get("default_path"):
                    cover_p = Path(self.library.config.get("default_path")) / cover_p
                cover_icon = load_icon(
                    cover_p, self.library.config.get("audiobook_icon_size", 100), force_square=True
                )
            item.setIcon(cover_icon or self.library.default_audiobook_icon)
            
            icon_size = self.library.config.get("audiobook_icon_size", 100)
            item.setSizeHint(QSize(icon_size, icon_size + 10))

    def doItemsLayout(self):
        super().doItemsLayout()
        self.update_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.update_height()

    def update_height(self):
        if self._updating_height:
            return
        self._updating_height = True
        try:
            width = self.library.tree.viewport().width() - 24
            if width <= 0:
                width = self.width() or self.library.tree.width() or 300

            max_bottom = 0
            for i in range(self.count()):
                if not self.item(i).isHidden():
                    r = self.visualItemRect(self.item(i))
                    if r.bottom() > max_bottom:
                        max_bottom = r.bottom()

            new_height = max_bottom + self.spacing() if max_bottom > 0 else 0

            if self.height() != int(new_height):
                self.setFixedHeight(int(new_height))
                self.setMinimumHeight(int(new_height))
                self.setMaximumHeight(int(new_height))
                self.parent_item.setSizeHint(0, QSize(width, int(new_height)))
                self.library.tree.scheduleDelayedItemsLayout()
        finally:
            self._updating_height = False

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hovered_item = None
        self.mouse_pos = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.viewport().update()
        
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.mouse_pos = event.position().toPoint()
        item = self.itemAt(self.mouse_pos)
        if item != self.hovered_item:
            self.hovered_item = item
        self.viewport().update()
        
        # Cursor shape update
        cursor_set = False
        if item:
            delegate = self.itemDelegate()
            if isinstance(delegate, TileDelegate):
                rect = self.visualItemRect(item)
                play_rect = delegate.get_play_rect(rect)
                fav_rect = delegate.get_fav_rect(rect)
                if play_rect.contains(QPointF(self.mouse_pos)) or fav_rect.contains(QPointF(self.mouse_pos)):
                    self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                    cursor_set = True
        
        if not cursor_set:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            
    def wheelEvent(self, event):
        """Forward mouse wheel events to the parent tree widget"""
        if self.library and self.library.tree:
            self.library.tree.wheelEvent(event)
        else:
            super().wheelEvent(event)
            
    def on_item_entered(self, item):
        self.hovered_item = item
        self.viewport().update()
        
    def on_item_clicked(self, item):
        try:
            self.library.clear_other_grid_selections(self)
            
            path = item.data(Qt.ItemDataRole.UserRole)
            delegate = self.itemDelegate()
            if isinstance(delegate, TileDelegate):
                event_pos = self.viewport().mapFromGlobal(QCursor.pos())
                rect = self.visualItemRect(item)
                
                # Check Play button
                play_rect = delegate.get_play_rect(rect)
                if play_rect.contains(QPointF(event_pos)):
                    self.library.tree.play_button_clicked.emit(path)
                    return
                    
                # Check Favorite button
                fav_rect = delegate.get_fav_rect(rect)
                if fav_rect.contains(QPointF(event_pos)):
                    status_data = item.data(Qt.ItemDataRole.UserRole + 3)
                    if status_data:
                        is_fav = status_data[2]
                        audiobook_id = None
                        for p, items in (self.library.cached_library_data or {}).items():
                            for it in items:
                                if it["path"] == path:
                                    audiobook_id = it["id"]
                                    break
                            if audiobook_id:
                                break
                        if audiobook_id:
                            self.library.toggle_favorite(audiobook_id, path)
                    return
        except Exception as e:
            import traceback
            traceback.print_exc()
        
    def on_item_double_clicked(self, item):
        try:
            path = item.data(Qt.ItemDataRole.UserRole)
            delegate = self.itemDelegate()
            if isinstance(delegate, TileDelegate):
                event_pos = self.viewport().mapFromGlobal(QCursor.pos())
                rect = self.visualItemRect(item)
                if delegate.get_play_rect(rect).contains(QPointF(event_pos)) or delegate.get_fav_rect(rect).contains(QPointF(event_pos)):
                    return
            self.library.audiobook_selected.emit(path)
        except Exception as e:
            import traceback
            traceback.print_exc()
        
    def on_context_menu_requested(self, pos):
        try:
            item = self.itemAt(pos)
            if item:
                path = item.data(Qt.ItemDataRole.UserRole)
                self.library.show_context_menu_for_path(path, self.viewport().mapToGlobal(pos))
        except Exception as e:
            import traceback
            traceback.print_exc()


class LibraryTree(QTreeWidget):
    """Customized tree widget that handles hover detection and direct interaction with audiobook 'Play' buttons"""

    play_button_clicked = pyqtSignal(
        str
    )  # Emits the relative path to the selected audiobook
    favorite_clicked = pyqtSignal(str)  # Emits path when heart is clicked
    description_requested = pyqtSignal(str)  # Emits path when info icon is clicked
    settings_requested = pyqtSignal()  # Emits when placeholder settings icon is clicked

    def __init__(self, parent=None):
        """Enable mouse tracking for fine-grained hover effects on custom-painted items"""
        super().__init__(parent)
        self.setMouseTracking(True)
        self.has_any_content = (
            False  # Track if DB has any items regardless of current filter
        )

    def resizeEvent(self, event):
        """Recursively update height for all nested grid lists when the tree width changes"""
        super().resizeEvent(event)
        
        def traverse(item):
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "grid_placeholder":
                widget = self.itemWidget(item, 0)
                if isinstance(widget, BookGridList):
                    widget.update_height()
            for i in range(item.childCount()):
                traverse(item.child(i))
                
        traverse(self.invisibleRootItem())

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
            delegate.mouse_pos = event.pos()
            self.viewport().update()

            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                if item_type == "audiobook":
                    rect = self.visualRect(index)
                    icon_rect = delegate.get_icon_rect(rect, index)
                    play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                    if play_rect.contains(QPointF(event.pos())):
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
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
            # Check placeholder click
            if self.topLevelItemCount() == 0 and not self.has_any_content:
                rect = get_placeholder_folder_rect(self.viewport().rect())
                if rect.contains(QPointF(event.pos())):
                    self.settings_requested.emit()
                    return

            index = self.indexAt(event.pos())
            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                if item_type == "audiobook":
                    delegate = self.itemDelegate()
                    if delegate and hasattr(delegate, "get_play_button_rect"):
                        rect = self.visualRect(index)
                        icon_rect = delegate.get_icon_rect(rect, index)
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
        super().mousePressEvent(event)

    def _emit_favorite_clicked(self, path):
        self.favorite_clicked.emit(path)


class LibraryWidget(QWidget):
    """Container for the audiobook tree, search filters, and status-based navigation buttons"""

    audiobook_selected = pyqtSignal(
        str
    )  # Emits the relative path of the selected audiobook
    show_folders_toggled = pyqtSignal(bool)  # Emits the new state of the folders toggle
    show_grid_toggled = pyqtSignal(bool)  # Emits the new state of the grid toggle
    delete_requested = pyqtSignal(int, str)  # Emits (audiobook_id, rel_path)
    folder_delete_requested = pyqtSignal(str)  # Emits folder relative path
    scan_requested = pyqtSignal()
    settings_requested = pyqtSignal()  # Propagate settings request

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
        self.show_folders = show_folders
        self.show_grid = self.config.get("show_grid", False)
        self.show_filter_labels = show_filter_labels
        self.cached_library_data = None  # Cache for fast reconstruction
        self.tag_filter_ids = self.config.get("tag_filter_ids", set())
        self.is_tag_filter_active = self.config.get("tag_filter_active", False)
        self.is_favorites_filter_active = self.config.get("favorites_active", False)
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

        # Grid View Toggle
        self.btn_show_grid = QPushButton("")
        self.btn_show_grid.setObjectName("filterBtn")
        self.btn_show_grid.setCheckable(True)
        self.btn_show_grid.setChecked(self.show_grid)
        self.btn_show_grid.setIcon(get_icon("view_grid"))
        self.btn_show_grid.setFixedWidth(40)
        self.btn_show_grid.setToolTip(tr("library.tooltip_tile_view"))
        self.btn_show_grid.clicked.connect(self.on_show_grid_toggled)
        filter_layout.addWidget(self.btn_show_grid)

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
        layout.addLayout(filter_layout)

        self.stacked_widget = QStackedWidget()

        self.tree = LibraryTree()
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

        if self.delegate:
            self.tree.setItemDelegate(self.delegate)

        # Clear other selections when clicking on tree
        self.tree.itemClicked.connect(lambda item: self.clear_other_grid_selections(self.tree))

        # Flat Grid View
        self.tile_view = QListWidget()
        self.tile_view.setObjectName("libraryTileView")
        self.tile_view.library = self
        self.tile_view.hovered_item = None
        self.tile_view.mouse_pos = None
        self.tile_view.setViewMode(QListView.ViewMode.IconMode)
        self.tile_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.tile_view.setMovement(QListView.Movement.Static)
        self.tile_view.setWrapping(True)
        self.tile_view.setWordWrap(False)
        self.tile_view.setSpacing(15)
        self.tile_view.setMouseTracking(True)
        self.tile_view.setItemDelegate(TileDelegate(self.config, self.tile_view))
        
        self.tile_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tile_view.customContextMenuRequested.connect(self.on_tile_view_context_menu)
        self.tile_view.itemClicked.connect(self.on_tile_view_item_clicked)
        self.tile_view.itemDoubleClicked.connect(self.on_tile_view_item_double_clicked)
        
        self.tile_view.leaveEvent = lambda event, tv=self.tile_view: self.on_tile_view_leave(tv, event)
        self.tile_view.mouseMoveEvent = lambda event, tv=self.tile_view: self.on_tile_view_mouse_move(tv, event)

        self.stacked_widget.addWidget(self.tree)
        self.stacked_widget.addWidget(self.tile_view)

        # Update initial stack display
        if self.show_grid and not self.show_folders:
            self.stacked_widget.setCurrentWidget(self.tile_view)
        else:
            self.stacked_widget.setCurrentWidget(self.tree)

        layout.addWidget(self.stacked_widget)

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
            updated_data = self.db.get_audiobook_by_path(path)
            if updated_data and not updated_data.get("is_favorite"):
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
        # When switching filters, reload from DB to apply correct sorting and subset
        self.load_audiobooks(use_cache=False)

    def on_show_folders_toggled(self, checked):
        """Toggle folder visibility and refresh the library"""
        self.show_folders = checked
        self.show_folders_toggled.emit(checked)
        
        # Adjust stacked widget view based on new folder and grid state
        if self.show_grid and not self.show_folders:
            self.stacked_widget.setCurrentWidget(self.tile_view)
        else:
            self.stacked_widget.setCurrentWidget(self.tree)
            
        self.load_audiobooks(use_cache=True)

    def on_show_grid_toggled(self, checked):
        """Toggle grid/tile view and refresh the library"""
        self.show_grid = checked
        self.show_grid_toggled.emit(checked)
        
        # Adjust stacked widget view based on new folder and grid state
        if self.show_grid and not self.show_folders:
            self.stacked_widget.setCurrentWidget(self.tile_view)
        else:
            self.stacked_widget.setCurrentWidget(self.tree)
            
        self.load_audiobooks(use_cache=True)

    def refresh_library(self):
        """Force a database reload and refresh the UI"""
        self.load_audiobooks(use_cache=False)

    def load_audiobooks(self, use_cache: bool = True):
        """Retrieve and display audiobooks from the database according to the active filter"""
        self.current_playing_item = None
        self.tree.clear()
        self.tile_view.clear()

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
            if self.show_grid and not self.show_folders:
                all_items = []
                for parent_path, items in self.cached_library_data.items():
                    for item_data in items:
                        if not item_data["is_folder"]:
                            # Get tags
                            item_tags = all_tags.get(item_data["id"], [])
                            if "id" in item_data:
                                item_data["tags"] = item_tags

                            # Apply Tag Filter
                            if self.is_tag_filter_active and self.tag_filter_ids:
                                item_tag_ids = {t["id"] for t in item_tags}
                                if not self.tag_filter_ids.intersection(item_tag_ids):
                                    continue

                            # Apply Favorites Filter
                            if self.is_favorites_filter_active:
                                if not item_data.get("is_favorite"):
                                    continue

                            all_items.append(item_data)

                # Re-sort at client side to ensure absolute order
                sort_key = "name"
                if self.current_filter == "in_progress":
                    sort_key = "last_updated"
                elif self.current_filter == "completed":
                    sort_key = "time_finished"
                elif self.current_filter == "not_started":
                    sort_key = "time_added"

                all_items.sort(
                    key=lambda x: (x.get(sort_key) or "", x.get("name") or ""),
                    reverse=(sort_key != "name"),
                )

                # Populate self.tile_view
                for data in all_items:
                    item = QListWidgetItem(self.tile_view)
                    item.setData(Qt.ItemDataRole.UserRole, data["path"])
                    item.setData(Qt.ItemDataRole.UserRole + 1, "audiobook")
                    item.setData(
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
                        )
                    )
                    item.setData(
                        Qt.ItemDataRole.UserRole + 3,
                        (data["is_started"], data["is_completed"], data["is_favorite"]),
                    )
                    if "tags" in data:
                        item.setData(Qt.ItemDataRole.UserRole + 4, data["tags"])

                    # Fetch and scale cover
                    cover_icon = None
                    cover_p_str = data.get("cached_cover_path") or data.get("cover_path")
                    if cover_p_str:
                        cover_p = Path(str(cover_p_str))
                        default_path = self.config.get("default_path")
                        if not cover_p.is_absolute() and default_path:
                            cover_p = Path(str(default_path)) / cover_p
                        cover_icon = load_icon(
                            cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
                        )
                    
                    item.setIcon(cover_icon or self.default_audiobook_icon)
                    
                    icon_size = self.config.get("audiobook_icon_size", 100)
                    item.setSizeHint(QSize(icon_size, icon_size + 14))
            
            # If folders are hidden and we are in a non-'all' filter,
            # we should populate as a flat list to guarantee the SQL sort order
            # is visually preserved across the entire library.
            elif not self.show_folders and self.current_filter != "all":
                all_items = []
                for parent_path, items in self.cached_library_data.items():
                    for item_data in items:
                        if not item_data["is_folder"]:
                            # Get tags
                            item_tags = all_tags.get(item_data["id"], [])
                            if "id" in item_data:
                                item_data["tags"] = item_tags

                            # Apply Tag Filter
                            if self.is_tag_filter_active and self.tag_filter_ids:
                                item_tag_ids = {t["id"] for t in item_tags}
                                if not self.tag_filter_ids.intersection(item_tag_ids):
                                    continue

                            # Apply Favorites Filter
                            if self.is_favorites_filter_active:
                                if not item_data.get("is_favorite"):
                                    continue

                            all_items.append(item_data)

                # Re-sort at client side to ensure absolute order (SQL order might be fragmented in the map)
                sort_key = "name"
                if self.current_filter == "in_progress":
                    sort_key = "last_updated"
                elif self.current_filter == "completed":
                    sort_key = "time_finished"
                elif self.current_filter == "not_started":
                    sort_key = "time_added"
                # favorites sort key removed as it's no longer a main mode

                all_items.sort(
                    key=lambda x: (x.get(sort_key) or "", x.get("name") or ""),
                    reverse=(sort_key != "name"),
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

                            filtered_items.append(item_data)

                        if filtered_items:
                            filtered_data[parent_path] = filtered_items

                    data_to_display = filtered_data

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

        # Separate items into folders and audiobooks
        folders_list = []
        books_list = []
        for data in data_by_parent[parent_path]:
            if data["is_folder"]:
                folders_list.append(data)
            else:
                books_list.append(data)

        # 1. Process Folders
        for data in folders_list:
            if not self.show_folders:
                # If folders are hidden by default, recursively add children to the SAME parent
                self.add_items_from_db(parent_item, data["path"], data_by_parent)
                continue

            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, data["path"])
            item.setText(0, data["name"])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
            item.setIcon(0, self.folder_icon)
            # Restore the expansion state of the folder from previous sessions
            if data.get("is_expanded"):
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

        # 2. Process Books: if show_grid is enabled, put all direct child books inside a single nested list widget
        if books_list:
            if self.show_grid:
                placeholder_item = QTreeWidgetItem(parent_item)
                placeholder_item.setData(0, Qt.ItemDataRole.UserRole + 1, "grid_placeholder")
                
                # Create BookGridList widget
                grid_widget = BookGridList(books_list, self, placeholder_item)
                self.tree.setItemWidget(placeholder_item, 0, grid_widget)
                
                # Set initial size hint
                grid_widget.update_height()
            else:
                # Standard rows
                for data in books_list:
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
            cover_p = Path(str(cover_p_str))
            # For relative paths (legacy or uncached), resolve them against the library's root directory
            default_path = self.config.get("default_path")
            if not cover_p.is_absolute() and default_path:
                cover_p = Path(str(default_path)) / cover_p

            cover_icon = load_icon(
                cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
            )
        item.setIcon(0, cover_icon or self.default_audiobook_icon)

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
            elif item_type == "grid_placeholder":
                widget = self.tree.itemWidget(child, 0)
                if isinstance(widget, BookGridList):
                    for b in widget.books:
                        books_count += 1
                        total_seconds += (b.get("duration") or 0.0)
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

        # If flat tile view is active
        if self.show_grid and not self.show_folders:
            for i in range(self.tile_view.count()):
                t_item = self.tile_view.item(i)
                
                # Apply Status Filter
                status_data = t_item.data(Qt.ItemDataRole.UserRole + 3)
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

                # Apply Text Search
                text_match = True
                if search_text:
                    data = t_item.data(Qt.ItemDataRole.UserRole + 2)
                    author, title, narrator = "", "", ""
                    codec, b_min, b_max, b_mode, container = "", 0, 0, "", ""
                    if data:
                        author, title, narrator = data[0:3]
                        codec, b_min, b_max, b_mode, container = data[7:12]

                    # Tag Search
                    tags = t_item.data(Qt.ItemDataRole.UserRole + 4)
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
                    searchables = [s for s in searchables if s]
                    combined_search_text = " ".join(searchables)
                    text_match = smart_search(search_text, combined_search_text)

                t_item.setHidden(not (status_match and text_match))
            return

        if not search_text and self.current_filter == "all":
            self.show_all_items(self.tree.invisibleRootItem())
            return

        self.filter_tree_items(self.tree.invisibleRootItem(), search_text)

    def show_all_items(self, parent_item):
        """Reset the visibility of all items within the tree to visible"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == "grid_placeholder":
                widget = self.tree.itemWidget(child, 0)
                if isinstance(widget, BookGridList):
                    for k in range(widget.count()):
                        widget.item(k).setHidden(False)
                    widget.update_height()
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

            elif item_type == "grid_placeholder":
                widget = self.tree.itemWidget(child, 0)
                if isinstance(widget, BookGridList):
                    vis_in_grid = 0
                    for k in range(widget.count()):
                        t_item = widget.item(k)
                        
                        # 1. Check Status Filter
                        status_data = t_item.data(Qt.ItemDataRole.UserRole + 3)
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
                            data = t_item.data(Qt.ItemDataRole.UserRole + 2)
                            author, title, narrator = "", "", ""
                            codec, b_min, b_max, b_mode, container = "", 0, 0, "", ""
                            if data:
                                author, title, narrator = data[0:3]
                                codec, b_min, b_max, b_mode, container = data[7:12]

                            # Tag Search
                            tags = t_item.data(Qt.ItemDataRole.UserRole + 4)
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
                            searchables = [s for s in searchables if s]
                            combined_search_text = " ".join(searchables)
                            text_match = smart_search(search_text, combined_search_text)

                        t_item.setHidden(not (status_match and text_match))
                        if not t_item.isHidden():
                            vis_in_grid += 1

                    widget.update_height()
                    child.setHidden(vis_in_grid == 0)
                    if vis_in_grid > 0:
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
                    author, title, narrator = "", "", ""
                    codec, b_min, b_max, b_mode, container = "", 0, 0, "", ""

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

    def on_item_expanded(self, item):
        """Persist the folder expansion state to the database when a branch is opened"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, True)
            
            # Recalculate heights of nested grid widgets in this expanded folder
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList):
                        widget.update_height()

    def on_item_collapsed(self, item):
        """Persist the folder collapse state to the database when a branch is closed"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
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

        if role == "audiobook":
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
            menu.setObjectName("libraryContextMenu")

            play_action = QAction(tr("library.context_play"), self)
            play_action.setIcon(get_icon("context_play"))
            play_action.triggered.connect(
                lambda _: self.on_item_double_clicked(item, 0)
            )
            menu.addAction(play_action)

            # Favorites Action
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

            # Tags Submenu
            menu.addSeparator()
            tags_menu = menu.addMenu(tr("tags.menu_title"))
            tags_menu.setObjectName("libraryContextMenu")
            tags_menu.setIcon(
                get_icon("context_tags")
            )  # Ensure icon exists or fallback logic if needed

            # Populate with existing tags
            all_tags = self.db.get_all_tags()
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
            clear_tags_action.setEnabled(bool(current_tag_ids))
            tags_menu.addAction(clear_tags_action)

            menu.addSeparator()

            edit_metadata_action = QAction(tr("library.menu_edit_metadata"), self)
            edit_metadata_action.setIcon(get_icon("context_edit_metadata"))
            edit_metadata_action.triggered.connect(
                lambda _: self.open_metadata_editor(audiobook_id, path)
            )
            menu.addAction(edit_metadata_action)

            menu.addSeparator()

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

            open_folder_action = QAction(tr("library.menu_open_folder"), self)
            open_folder_action.setIcon(get_icon("context_open_folder"))
            open_folder_action.triggered.connect(lambda _: self.open_folder(path))
            menu.addAction(open_folder_action)

            menu.addSeparator()

            delete_action = QAction(tr("library.menu_delete"), self)
            delete_action.setIcon(get_icon("delete"))
            delete_action.triggered.connect(
                lambda _: self.confirm_delete(audiobook_id, path)
            )
            menu.addAction(delete_action)

            menu.exec(self.tree.viewport().mapToGlobal(pos))

        elif role == "folder":
            # Folder context menu
            menu = QMenu()
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
        if (
            hasattr(window, "playback_controller")
            and window.playback_controller.current_audiobook_id == audiobook_id
        ):
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
        if (
            hasattr(window, "playback_controller")
            and window.playback_controller.current_audiobook_id == audiobook_id
        ):
            window.playback_controller.saved_file_index = 0
            window.playback_controller.saved_position = 0
            window.update_ui_for_audiobook()

    def toggle_favorite(self, audiobook_id: int, path: str):
        """Toggle favorite status and refresh item"""
        new_state = self.db.toggle_favorite(audiobook_id)
        self.refresh_audiobook_item(path)

        # If we are in Favorites filter mode and we removed it, reload to hide it
        if self.is_favorites_filter_active and not new_state:
            self.load_audiobooks(use_cache=False)

    def open_tag_assignment(self, audiobook_id, path):
        """Open dialog to assign tags to audiobook"""
        # Unified dialog handling both assignment and management
        dialog = TagManagerDialog(self.db, self, audiobook_id)
        if dialog.exec():
            # Refresh this item to show new tags
            self.refresh_audiobook_item(path)

    def toggle_tag_from_context_menu(
        self, audiobook_id: int, tag_id: int, path: str, checked: bool
    ):
        """Handle toggling a tag directly from the context menu"""
        if checked:
            self.db.add_tag_to_audiobook(audiobook_id, tag_id)
        else:
            self.db.remove_tag_from_audiobook(audiobook_id, tag_id)

        # Refresh the UI for this item
        self.refresh_audiobook_item(path)

    def clear_all_tags(self, audiobook_id: int, path: str):
        """Remove all tags from an audiobook"""
        self.db.remove_all_tags_from_audiobook(audiobook_id)
        # Refresh the UI for this item
        self.refresh_audiobook_item(path)

    def open_metadata_editor(self, audiobook_id: int, path: str):
        """Open dialog to edit audiobook metadata (author, title, narrator)"""
        dialog = MetadataEditDialog(self.db, audiobook_id, self)
        self.apply_blur()
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
        self.remove_blur()

    def confirm_delete(self, audiobook_id: int, path: str):
        """Ask for user confirmation before proceeding with book deletion"""
        display_path = os.path.basename(path)
        reply = QMessageBox.question(
            self,
            tr("library.confirm_delete_title"),
            trf("library.confirm_delete_msg", path=display_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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

        # 3. Refresh status metrics in the main window
        window = self.window()
        total_count = self.db.get_audiobook_count()
        # Update placeholder state
        self.tree.has_any_content = total_count > 0
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(
                trf("status.library_count", count=total_count)
            )

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
            self.scan_requested.emit()
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

    def on_item_double_clicked(self, item, column=0):
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

        data = self.db.get_audiobook_by_path(audiobook_path)
        if not data:
            return

        # Fetch tags
        tags = []
        info = self.db.get_audiobook_info(audiobook_path)
        if info:
            tags = self.db.get_tags_for_audiobook(info[0])

        self.update_cache_item_status(
            audiobook_path, data["is_started"], data["is_completed"]
        )

        # Helper to refresh grid/list item
        def refresh_grid_item_fields(t_item, b_data, b_tags):
            t_item.setData(
                Qt.ItemDataRole.UserRole + 2,
                (
                    b_data["author"],
                    b_data["title"],
                    b_data["narrator"],
                    b_data["file_count"],
                    b_data["duration"],
                    b_data["listened_duration"],
                    b_data["progress_percent"],
                    b_data["codec"],
                    b_data["bitrate_min"],
                    b_data["bitrate_max"],
                    b_data["bitrate_mode"],
                    b_data["container"],
                    b_data.get("description", ""),
                    b_data.get("total_size", 0),
                ),
            )
            t_item.setData(
                Qt.ItemDataRole.UserRole + 3,
                (b_data["is_started"], b_data["is_completed"], b_data["is_favorite"]),
            )
            t_item.setData(Qt.ItemDataRole.UserRole + 4, b_tags)
            
            cover_icon = None
            cover_p_str = b_data.get("cached_cover_path") or b_data.get("cover_path")
            if cover_p_str:
                cover_p = Path(str(cover_p_str))
                default_path = self.config.get("default_path")
                if not cover_p.is_absolute() and default_path:
                    cover_p = Path(str(default_path)) / cover_p
                
                from utils import load_icon
                load_icon.cache_clear()
                cover_icon = load_icon(
                    cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
                )
            t_item.setIcon(cover_icon or self.default_audiobook_icon)

        # 1. Update Flat Grid (self.tile_view)
        for i in range(self.tile_view.count()):
            t_item = self.tile_view.item(i)
            if t_item.data(Qt.ItemDataRole.UserRole) == audiobook_path:
                refresh_grid_item_fields(t_item, data, tags)

        # 2. Update Hybrid Grid (BookGridList inside tree)
        def traverse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList):
                        # Update underlying books list inside widget
                        for b_idx, b in enumerate(widget.books):
                            if b["path"] == audiobook_path:
                                widget.books[b_idx].update(data)
                                widget.books[b_idx]["tags"] = tags
                        for k in range(widget.count()):
                            w_item = widget.item(k)
                            if w_item.data(Qt.ItemDataRole.UserRole) == audiobook_path:
                                refresh_grid_item_fields(w_item, data, tags)
                traverse(child)
        traverse(self.tree.invisibleRootItem())

        # 3. Update Standard Tree Item
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
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
                ),
            )
            if "is_started" in data and "is_completed" in data:
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole + 3,
                    (data["is_started"], data["is_completed"], data["is_favorite"]),
                )
            item.setData(0, Qt.ItemDataRole.UserRole + 4, tags)

            # Refresh and scale the audiobook cover
            cover_icon = None
            cover_p_str = data.get("cached_cover_path") or data.get("cover_path")
            if cover_p_str:
                cover_p = Path(str(cover_p_str))
                default_path = self.config.get("default_path")
                if not cover_p.is_absolute() and default_path:
                    cover_p = Path(str(default_path)) / cover_p

                from utils import load_icon
                load_icon.cache_clear()
                cover_icon = load_icon(
                    cover_p, self.config.get("audiobook_icon_size", 100), force_square=True
                )
            item.setIcon(0, cover_icon or self.default_audiobook_icon)
            item.setText(0, item.text(0))

        self.trigger_viewport_update()

    def update_item_progress(
        self, audiobook_path: str, listened_duration: float, progress_percent: int
    ):
        # 1. Update Flat Grid (self.tile_view)
        for i in range(self.tile_view.count()):
            t_item = self.tile_view.item(i)
            if t_item.data(Qt.ItemDataRole.UserRole) == audiobook_path:
                data = t_item.data(Qt.ItemDataRole.UserRole + 2)
                if data and len(data) >= 7:
                    new_data = list(data)
                    new_data[5] = listened_duration
                    new_data[6] = progress_percent
                    t_item.setData(Qt.ItemDataRole.UserRole + 2, tuple(new_data))

        # 2. Update Hybrid Grid (BookGridList inside tree)
        def traverse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList):
                        for k in range(widget.count()):
                            w_item = widget.item(k)
                            if w_item.data(Qt.ItemDataRole.UserRole) == audiobook_path:
                                data = w_item.data(Qt.ItemDataRole.UserRole + 2)
                                if data and len(data) >= 7:
                                    new_data = list(data)
                                    new_data[5] = listened_duration
                                    new_data[6] = progress_percent
                                    w_item.setData(Qt.ItemDataRole.UserRole + 2, tuple(new_data))
                traverse(child)
        traverse(self.tree.invisibleRootItem())

        # 3. Update Standard Tree Item
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole + 2)
            if data and len(data) >= 7:
                new_data = list(data)
                new_data[5] = listened_duration
                new_data[6] = progress_percent
                item.setData(0, Qt.ItemDataRole.UserRole + 2, tuple(new_data))

        self.trigger_viewport_update()

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

        # Scroll to the audiobook
        if self.show_grid and not self.show_folders:
            # Scroll flat grid
            for i in range(self.tile_view.count()):
                t_item = self.tile_view.item(i)
                if t_item.data(Qt.ItemDataRole.UserRole) == audiobook_path:
                    self.tile_view.scrollToItem(t_item, QAbstractItemView.ScrollHint.PositionAtCenter)
                    break
        else:
            # Scroll tree / hybrid grid
            def find_and_reveal(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
                    if item_type == "folder":
                        if find_and_reveal(child):
                            child.setExpanded(True)
                            return True
                    elif item_type == "grid_placeholder":
                        widget = self.tree.itemWidget(child, 0)
                        if isinstance(widget, BookGridList):
                            for k in range(widget.count()):
                                if widget.item(k).data(Qt.ItemDataRole.UserRole) == audiobook_path:
                                    parent_item.setExpanded(True)
                                    self.tree.scrollToItem(child, QTreeWidget.ScrollHint.PositionAtCenter)
                                    widget.setCurrentRow(k)
                                    widget.scrollToItem(widget.item(k), QAbstractItemView.ScrollHint.PositionAtCenter)
                                    return True
                    elif item_type == "audiobook":
                        if child.data(0, Qt.ItemDataRole.UserRole) == audiobook_path:
                            self.tree.scrollToItem(child, QTreeWidget.ScrollHint.PositionAtCenter)
                            return True
                return False
            find_and_reveal(self.tree.invisibleRootItem())

    def clear_other_grid_selections(self, active_grid):
        """Deselect all item selections in other grid components across the tree"""
        # Block signals temporarily to prevent loop
        if active_grid != self.tree:
            self.tree.blockSignals(True)
            self.tree.clearSelection()
            self.tree.blockSignals(False)
            
        if active_grid != self.tile_view:
            self.tile_view.blockSignals(True)
            self.tile_view.clearSelection()
            self.tile_view.blockSignals(False)

        def traverse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList) and widget != active_grid:
                        widget.blockSignals(True)
                        widget.clearSelection()
                        widget.blockSignals(False)
                traverse(child)

        traverse(self.tree.invisibleRootItem())

    def trigger_viewport_update(self):
        """Force paint event across tree and list components"""
        self.tree.viewport().update()
        self.tile_view.viewport().update()
        def traverse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList):
                        widget.viewport().update()
                traverse(child)
        traverse(self.tree.invisibleRootItem())

    def update_all_grid_heights(self):
        """Iterate all active BookGridList widgets and update their layout heights"""
        def traverse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole + 1) == "grid_placeholder":
                    widget = self.tree.itemWidget(child, 0)
                    if isinstance(widget, BookGridList):
                        widget.update_height()
                traverse(child)
        traverse(self.tree.invisibleRootItem())

    def on_tile_view_leave(self, tile_view, event):
        """Handle mouse leaving the grid list widget to clear button hover states"""
        tile_view.hovered_item = None
        tile_view.mouse_pos = None
        tile_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        tile_view.viewport().update()

    def on_tile_view_mouse_move(self, tile_view, event):
        """Handle hover state updates when mouse moves over list items"""
        pos = event.pos()
        tile_view.mouse_pos = pos
        item = tile_view.itemAt(pos)
        if item != tile_view.hovered_item:
            tile_view.hovered_item = item
        tile_view.viewport().update()
        
        # Cursor shape update
        cursor_set = False
        if item:
            delegate = tile_view.itemDelegate()
            if isinstance(delegate, TileDelegate):
                rect = tile_view.visualItemRect(item)
                play_rect = delegate.get_play_rect(rect)
                fav_rect = delegate.get_fav_rect(rect)
                if play_rect.contains(QPointF(pos)) or fav_rect.contains(QPointF(pos)):
                    tile_view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                    cursor_set = True
        
        if not cursor_set:
            tile_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            
        QListWidget.mouseMoveEvent(tile_view, event)

    def on_tile_view_item_clicked(self, item):
        """Handle clicking an item inside a grid list widget"""
        try:
            self.clear_other_grid_selections(self.tile_view)
            
            path = item.data(Qt.ItemDataRole.UserRole)
            # Check if the click was exactly on the action buttons (Favorite or Play/Pause)
            delegate = self.tile_view.itemDelegate()
            if isinstance(delegate, TileDelegate):
                event_pos = self.tile_view.viewport().mapFromGlobal(QCursor.pos())
                rect = self.tile_view.visualItemRect(item)
                
                # Check Play button
                play_rect = delegate.get_play_rect(rect)
                if play_rect.contains(QPointF(event_pos)):
                    # Trigger Play action
                    self.tree.play_button_clicked.emit(path)
                    return
                    
                # Check Favorite button
                fav_rect = delegate.get_fav_rect(rect)
                if fav_rect.contains(QPointF(event_pos)):
                    # Toggle favorite status
                    status_data = item.data(Qt.ItemDataRole.UserRole + 3)
                    if status_data:
                        is_fav = status_data[2]
                        audiobook_id = None
                        for p, items in (self.cached_library_data or {}).items():
                            for it in items:
                                if it["path"] == path:
                                    audiobook_id = it["id"]
                                    break
                            if audiobook_id:
                                break
                        if audiobook_id:
                            self.toggle_favorite(audiobook_id, path)
                    return

            self.audiobook_selected.emit(path)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def on_tile_view_item_double_clicked(self, item):
        """Handle double-clicking an item to start playback"""
        try:
            path = item.data(Qt.ItemDataRole.UserRole)
            delegate = self.tile_view.itemDelegate()
            if isinstance(delegate, TileDelegate):
                event_pos = self.tile_view.viewport().mapFromGlobal(QCursor.pos())
                rect = self.tile_view.visualItemRect(item)
                if delegate.get_play_rect(rect).contains(QPointF(event_pos)) or delegate.get_fav_rect(rect).contains(QPointF(event_pos)):
                    return
            
            window = self.window()
            if hasattr(window, "playback_controller"):
                window.playback_controller.play_audiobook(path)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def on_tile_view_context_menu(self, pos):
        """Display standard context menu for audiobook item"""
        try:
            item = self.tile_view.itemAt(pos)
            if not item:
                return
                
            path = item.data(Qt.ItemDataRole.UserRole)
            self.show_context_menu_for_path(path, self.tile_view.viewport().mapToGlobal(pos))
        except Exception as e:
            import traceback
            traceback.print_exc()

    def show_context_menu_for_path(self, path: str, global_pos):
        """Unified helper to trigger custom context menu for a specific book path"""
        try:
            audiobook = None
            for p, items in (self.cached_library_data or {}).items():
                for it in items:
                    if it["path"] == path:
                        audiobook = it
                        break
                if audiobook:
                    break
            
            # Fallback: query DB directly if not found in cached data
            if not audiobook:
                db_data = self.db.get_audiobook_by_path(path)
                if db_data:
                    audiobook = db_data

            if not audiobook:
                return

            from PyQt6.QtGui import QAction
            from PyQt6.QtWidgets import QMenu, QStyle

            menu = QMenu(self)
            menu.setObjectName("libraryContextMenu")

            audiobook_id = audiobook.get("id")
            if not audiobook_id:
                info = self.db.get_audiobook_info(path)
                if info:
                    audiobook_id = info[0]
            if not audiobook_id:
                return

            # 1. Play / Pause Action
            window = self.window()
            is_playing = False
            if hasattr(window, "playback_controller"):
                is_playing = window.playback_controller.current_audiobook_path == path and window.playback_controller.player.is_playing()

            play_action = QAction(tr("library.context_pause") if is_playing else tr("library.context_play"), self)
            play_action.setIcon(get_icon("pause" if is_playing else "context_play"))
            play_action.triggered.connect(lambda p=path: self.tree.play_button_clicked.emit(p))
            menu.addAction(play_action)

            menu.addSeparator()

            # 2. Add to Favorites / Remove
            is_favorite = audiobook.get("is_favorite", False)
            fav_text = tr("library.menu_remove_favorite") if is_favorite else tr("library.menu_add_favorite")
            fav_icon = get_icon("context_favorite_on" if is_favorite else "context_favorite_off")
            if not fav_icon or fav_icon.isNull():
                fav_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)

            fav_action = QAction(fav_text, self)
            fav_action.setIcon(fav_icon)
            fav_action.triggered.connect(lambda aid=audiobook_id, p=path: self.toggle_favorite(aid, p))
            menu.addAction(fav_action)

            # 3. Mark Completed / Not Completed
            is_completed = audiobook.get("is_completed", False)
            
            mark_read_action = QAction(tr("library.menu_mark_read"), self)
            mark_read_action.setIcon(get_icon("context_mark_read"))
            mark_read_action.triggered.connect(
                lambda aid=audiobook_id, dur=audiobook.get("duration", 0), p=path: self.mark_as_read(aid, dur, p)
            )
            menu.addAction(mark_read_action)

            mark_unread_action = QAction(tr("library.menu_mark_unread"), self)
            mark_unread_action.setIcon(get_icon("context_mark_unread"))
            mark_unread_action.triggered.connect(
                lambda aid=audiobook_id, p=path: self.mark_as_unread(aid, p)
            )
            menu.addAction(mark_unread_action)

            menu.addSeparator()

            # 4. Edit Metadata
            edit_action = QAction(tr("library.menu_edit_metadata"), self)
            edit_action.setIcon(get_icon("context_edit_metadata"))
            edit_action.triggered.connect(lambda aid=audiobook_id, p=path: self.open_metadata_editor(aid, p))
            menu.addAction(edit_action)

            # Tags Submenu
            tags_menu = menu.addMenu(tr("tags.menu_title"))
            tags_menu.setObjectName("libraryContextMenu")
            tags_menu.setIcon(get_icon("context_tags"))

            all_tags = self.db.get_all_tags()
            assigned_tags = self.db.get_tags_for_audiobook(audiobook_id)
            assigned_tag_ids = {t["id"] for t in assigned_tags}

            for tag in all_tags:
                tag_action = QAction(tag["name"], self)
                tag_action.setCheckable(True)
                tag_action.setChecked(tag["id"] in assigned_tag_ids)
                
                if tag.get("color"):
                    pixmap = QPixmap(14, 14)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setBrush(QColor(tag["color"]))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(0, 0, 14, 14, 3, 3)
                    if tag["id"] in assigned_tag_ids:
                        _, accent_color = StyleManager.get_theme_property("theme_primary")
                        painter.setBrush(accent_color)
                        painter.drawEllipse(5, 5, 4, 4)
                    painter.end()
                    tag_action.setIcon(QIcon(pixmap))

                tag_action.triggered.connect(
                    lambda checked, t_id=tag["id"], aid=audiobook_id, p=path: self.toggle_tag_from_context_menu(
                        aid, t_id, p, checked
                    )
                )
                tags_menu.addAction(tag_action)

            tags_menu.addSeparator()
            
            assign_action = QAction(tr("tags.menu_assign"), self)
            assign_action.triggered.connect(
                lambda aid=audiobook_id, p=path: self.open_tag_assignment(aid, p)
            )
            tags_menu.addAction(assign_action)

            clear_tags_action = QAction(tr("tags.menu_clear_all"), self)
            clear_tags_action.triggered.connect(
                lambda aid=audiobook_id, p=path: self.clear_all_tags(aid, p)
            )
            clear_tags_action.setEnabled(bool(assigned_tag_ids))
            tags_menu.addAction(clear_tags_action)

            menu.addSeparator()

            # 5. Open Folder
            open_folder_action = QAction(tr("library.menu_open_folder"), self)
            open_folder_action.setIcon(get_icon("context_open_folder"))
            open_folder_action.triggered.connect(lambda p=path: self.open_folder(p))
            menu.addAction(open_folder_action)

            # 6. Delete Book
            delete_action = QAction(tr("library.menu_delete"), self)
            delete_action.setIcon(get_icon("delete"))
            delete_action.triggered.connect(lambda aid=audiobook_id, p=path: self.confirm_delete(aid, p))
            menu.addAction(delete_action)

            menu.exec(global_pos)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def update_texts(self):
        if hasattr(self, "btn_show_folders"):
            self.btn_show_folders.setToolTip(tr("library.tooltip_show_folders"))
        if hasattr(self, "btn_show_grid"):
            self.btn_show_grid.setToolTip(tr("library.tooltip_tile_view"))
        if hasattr(self, "btn_favorites"):
            self.btn_favorites.setToolTip(tr("library.tooltip_favorites"))
        if hasattr(self, "btn_tags"):
            self.btn_tags.setToolTip(tr("library.tooltip_tags"))
            
        self.update_filter_labels()
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                self.filter_buttons[filter_id].setToolTip(
                    tr(f"library.tooltip_filter_{filter_id}")
                )
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))

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
