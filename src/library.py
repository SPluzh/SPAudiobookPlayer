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
import math
import queue
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
    QImage,
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
from library_utils import (
    NESTING_COLORS,
    get_placeholder_folder_rect,
    draw_library_placeholder,
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

from library_list import MultiLineDelegate, LibraryTree
from library_tile import (
    WrapLayout,
    BookTileWidget,
    FolderBranchIndicator,
    FolderHeaderWidget,
    BooksContainerWidget,
    FolderGroup,
    CoverLoader,
    VirtualTileCanvas,
    TileFlowWidget,
)

TileScrollArea = TileFlowWidget

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
        self.current_meta_filters = set()
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
        self.nesting_lines_single_color = self.config.get("nesting_lines_single_color", False)
        self.nesting_lines_color = self.config.get("nesting_lines_color", "#808080")
        self._expanded_paths_cache = set()
        self.setup_ui()
        self.load_icons()
        self.set_tile_view_active(self.is_tile_view)

    @property
    def current_meta_filter(self) -> str:
        return ",".join(sorted(self.current_meta_filters))

    @current_meta_filter.setter
    def current_meta_filter(self, value: str):
        self.current_meta_filters = {f.strip() for f in value.split(",") if f.strip()}

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

        # Create a layout to keep tags filter toggle and dropdown in one flush button group
        tag_filter_layout = QHBoxLayout()
        tag_filter_layout.setSpacing(0)
        tag_filter_layout.setContentsMargins(0, 0, 0, 0)

        # Tags Filter
        self.btn_tags = QPushButton("")
        self.btn_tags.setObjectName("filterBtn")
        self.btn_tags.setCheckable(True)
        self.btn_tags.setChecked(self.is_tag_filter_active)
        self.btn_tags.setFixedWidth(40)
        self.btn_tags.setIcon(get_icon("context_tags"))
        self.btn_tags.setToolTip(tr("library.tooltip_filter_tags"))
        self.btn_tags.clicked.connect(self.on_tag_filter_toggled)
        tag_filter_layout.addWidget(self.btn_tags)


        # Tags Filter Dropdown Arrow Button
        self.btn_tags_arrow = QPushButton("")
        self.btn_tags_arrow.setObjectName("filterBtnArrow")
        self.btn_tags_arrow.setFixedWidth(20)
        self.btn_tags_arrow.setIcon(get_icon("chevron-down"))
        self.btn_tags_arrow.setIconSize(QSize(12, 12))
        self.btn_tags_arrow.setToolTip(tr("library.tooltip_filter_tags"))
        self.btn_tags_arrow.clicked.connect(lambda: self.show_tag_filter_menu())
        tag_filter_layout.addWidget(self.btn_tags_arrow)

        filter_layout.addLayout(tag_filter_layout)

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
            btn.setMaximumWidth(16777215)
        else:
            btn.setText("")
            btn.setMinimumWidth(0)  # Reset min width allow shrinking to icon size (or rely on style)
            if btn == self.btn_tags:
                btn.setFixedWidth(40)

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
        if hasattr(self, "btn_tags_arrow") and self.btn_tags_arrow:
            self.btn_tags_arrow.setIcon(get_icon("chevron-down"))
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

    def show_tag_filter_menu(self, pos=None):
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
        if self.is_tile_view and hasattr(self, "tile_view"):
            self.tile_view.canvas.update_selection_state(self.tree.selected_audiobook_paths)
            self.tile_view.canvas.update()

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
            def coerce_field_value(fld, val):
                if val is None or val == "":
                    return None
                
                # Fields that should be compared as numbers
                numeric_fields = {
                    "duration", "listened_duration", "progress_percent", 
                    "file_count", "bitrate_min", "bitrate_max", "total_size",
                    "is_favorite", "is_completed", "is_started", "is_available", "is_merged"
                }
                
                if fld in numeric_fields:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0
                else:
                    # String fields (including timestamps)
                    return str(val).lower()

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
                        return (0, None) if reverse else (1, None)
                    
                    # Extract values for each book
                    book_vals = []
                    for b in books_inside:
                        b_val = coerce_field_value(field, b.get(field))
                        if b_val is not None:
                            book_vals.append(b_val)
                    
                    if not book_vals:
                        return (0, None) if reverse else (1, None)
                    
                    val = max(book_vals) if reverse else min(book_vals)
                    return (1, val) if reverse else (0, val)
                
                if field == "name":
                    val = x.get("title") or x.get("name")
                else:
                    val = x.get(field)
                
                coerced_val = coerce_field_value(field, val)
                if coerced_val is None:
                    # Empty values always go to the end of the list, regardless of sort order
                    return (0, None) if reverse else (1, None)
                
                return (1, coerced_val) if reverse else (0, coerced_val)
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
                    search_min = str(b_min // 1000) if (b_min is not None and b_min > 5000) else (str(b_min) if b_min is not None else "")
                    search_max = str(b_max // 1000) if (b_max is not None and b_max > 5000) else (str(b_max) if b_max is not None else "")

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

    def show_context_menu(self, pos, item=None):
        """Construct and display a context menu for items in the library tree"""
        if item is None:
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
            # Expand all parent folders to ensure it's visible in both views
            parent = item.parent()
            parents_to_expand = []
            while parent:
                parents_to_expand.insert(0, parent)
                parent = parent.parent()

            for p in parents_to_expand:
                if not p.isExpanded():
                    p.setExpanded(True)

            # Scroll list view
            self.tree.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)

            # Scroll tile view
            if self.is_tile_view and hasattr(self, "tile_view"):
                # Repopulate the tile view so the newly expanded items are rendered
                self.tile_view.populate(self.tree.invisibleRootItem())
                
                # Scroll to the corresponding tile in the tile view
                found_rect = None
                if hasattr(self.tile_view, "canvas") and self.tile_view.canvas:
                    for block in self.tile_view.canvas.blocks:
                        if block["type"] == "books":
                            for book in block["books"]:
                                if book["path"] == audiobook_path:
                                    found_rect = book["rect"]
                                    break
                            if found_rect:
                                break
                if found_rect:
                    QTimer.singleShot(0, lambda r=found_rect: self.tile_view.ensureVisible(
                        r.center().x(),
                        r.center().y(),
                        r.width() // 2,
                        r.height() // 2
                    ))

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
        if hasattr(self, "btn_tags_arrow"):
            self.btn_tags_arrow.setToolTip(tr("library.tooltip_tags"))
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
        if self.is_tile_view and hasattr(self, "tile_view"):
            self.tile_view.populate(self.tree.invisibleRootItem())

    def expand_all_folders(self):
        """Expand all folders in the library tree"""
        self.tree.expandAll()
        if self.is_tile_view and hasattr(self, "tile_view"):
            self.tile_view.populate(self.tree.invisibleRootItem())

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
        """Display a popup menu to select the active metadata filter(s)"""
        from translations import get_language
        lang = get_language()
        
        def tr_local(key, default):
            ru_translations = {
                "library.filter_duration_title": "Длительность",
                "library.filter_size_title": "Размер",
                "library.filter_progress_title": "Прогресс воспроизведения",
                "duration:short": "Короткие (< 3 ч)",
                "duration:medium": "Средние (3–10 ч)",
                "duration:long": "Длинные (> 10 ч)",
                "size:small": "Маленькие (< 100 МБ)",
                "size:large": "Большие (> 1 ГБ)",
                "progress:almost": "Почти дослушано (> 80%)",
                "progress:just_started": "Только начато (< 10%)",
                "progress:never_opened": "Ни разу не открыто",
            }
            if lang == "ru":
                return ru_translations.get(key, default)
            return default

        class KeepOpenMenu(QMenu):
            def mouseReleaseEvent(self, event):
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                action = self.actionAt(pos)
                if action and action.isCheckable():
                    action.trigger()
                    event.accept()
                else:
                    super().mouseReleaseEvent(event)

        menu = KeepOpenMenu(self)
        menu.setObjectName("metaFilterMenu")
        
        # Reset all filters option at the very top
        translated_reset = tr("library.filter_reset_all")
        if translated_reset == "library.filter_reset_all":
            translated_reset = "Reset all"
        
        act_reset = menu.addAction(translated_reset)
        act_reset.triggered.connect(self._reset_all_meta_filters)
        
        menu.addSeparator()
        
        options_no = [
            ("no_cover", "library.filter_no_cover"),
            ("no_author", "library.filter_no_author"),
            ("no_narrator", "library.filter_no_narrator")
        ]
        
        options_has = [
            ("has_cover", "library.filter_has_cover"),
            ("has_author", "library.filter_has_author"),
            ("has_narrator", "library.filter_has_narrator")
        ]
        
        action_map = {}
        
        # "Without" filters
        for filter_key, loc_key in options_no:
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
            action.setChecked(filter_key in self.current_meta_filters)
            action_map[action] = filter_key
            action.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))
            
        menu.addSeparator()

        # "With" filters (separated)
        for filter_key, loc_key in options_has:
            translated = tr(loc_key)
            if translated == loc_key:
                fallbacks = {
                    "library.filter_has_cover": "With cover",
                    "library.filter_has_author": "With author",
                    "library.filter_has_narrator": "With narrator"
                }
                translated = fallbacks.get(loc_key, loc_key)
                
            action = menu.addAction(translated)
            action.setCheckable(True)
            action.setChecked(filter_key in self.current_meta_filters)
            action_map[action] = filter_key
            action.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))
            
        menu.addSeparator()

        # Duration Submenu
        duration_menu = menu.addMenu(tr_local("library.filter_duration_title", "Duration"))
        duration_menu.setObjectName("durationFilterSubMenu")
        
        duration_options = [
            ("duration:short", "duration:short", "Short (< 3 hrs)"),
            ("duration:medium", "duration:medium", "Medium (3-10 hrs)"),
            ("duration:long", "duration:long", "Long (> 10 hrs)")
        ]
        
        for filter_key, key_tr, default_val in duration_options:
            act = duration_menu.addAction(tr_local(key_tr, default_val))
            act.setCheckable(True)
            act.setChecked(filter_key in self.current_meta_filters)
            action_map[act] = filter_key
            act.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))

        # Size Submenu
        size_menu = menu.addMenu(tr_local("library.filter_size_title", "Size"))
        size_menu.setObjectName("sizeFilterSubMenu")
        
        size_options = [
            ("size:small", "size:small", "Small (< 100 MB)"),
            ("size:large", "size:large", "Large (> 1 GB)")
        ]
        
        for filter_key, key_tr, default_val in size_options:
            act = size_menu.addAction(tr_local(key_tr, default_val))
            act.setCheckable(True)
            act.setChecked(filter_key in self.current_meta_filters)
            action_map[act] = filter_key
            act.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))

        # Progress Submenu
        progress_menu = menu.addMenu(tr_local("library.filter_progress_title", "Playback Progress"))
        progress_menu.setObjectName("progressFilterSubMenu")
        
        progress_options = [
            ("progress:almost", "progress:almost", "Almost completed (> 80%)"),
            ("progress:just_started", "progress:just_started", "Just started (< 10%)"),
            ("progress:never_opened", "progress:never_opened", "Never opened")
        ]
        
        for filter_key, key_tr, default_val in progress_options:
            act = progress_menu.addAction(tr_local(key_tr, default_val))
            act.setCheckable(True)
            act.setChecked(filter_key in self.current_meta_filters)
            action_map[act] = filter_key
            act.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))

        menu.addSeparator()
        
        # "Without language" option
        translated_none = tr("library.language_none")
        if translated_none == "library.language_none":
            translated_none = "Without Language"
        act_none = menu.addAction(translated_none)
        act_none.setCheckable(True)
        act_none.setChecked("lang:none" in self.current_meta_filters)
        action_map[act_none] = "lang:none"
        act_none.triggered.connect(lambda checked: self._toggle_meta_filter("lang:none", action_map))
        
        # List of unique languages
        langs = self.get_available_languages()
        if langs:
            for lang_val in langs:
                filter_key = f"lang:{lang_val}"
                action = menu.addAction(lang_val)
                action.setCheckable(True)
                action.setChecked(filter_key in self.current_meta_filters)
                action_map[action] = filter_key
                action.triggered.connect(lambda checked, fk=filter_key: self._toggle_meta_filter(fk, action_map))
            
        global_pos = self.btn_meta_filter_arrow.mapToGlobal(QPoint(0, self.btn_meta_filter_arrow.height()))
        menu.exec(global_pos)

    def _reset_all_meta_filters(self):
        self.current_meta_filters.clear()
        self.is_meta_filter_active = False
        if hasattr(self, "btn_meta_filter"):
            self.btn_meta_filter.setChecked(False)
        self.load_audiobooks(use_cache=True)

    def _on_meta_filter_selected(self, filter_key):
        self.current_meta_filter = filter_key
        self.is_meta_filter_active = bool(self.current_meta_filters)
        if hasattr(self, "btn_meta_filter"):
            self.btn_meta_filter.setChecked(self.is_meta_filter_active)
        self.load_audiobooks(use_cache=True)

    def _toggle_meta_filter(self, filter_key, action_map):
        groups = [
            {"no_cover", "has_cover"},
            {"no_author", "has_author"},
            {"no_narrator", "has_narrator"},
            {"duration:short", "duration:medium", "duration:long"},
            {"size:small", "size:large"},
            {"progress:almost", "progress:just_started", "progress:never_opened"},
        ]
        
        if filter_key.startswith("lang:"):
            lang_keys = {k for k in self.current_meta_filters if k.startswith("lang:")}
            self.current_meta_filters.difference_update(lang_keys)
            if filter_key not in lang_keys:
                self.current_meta_filters.add(filter_key)
        else:
            group = None
            for g in groups:
                if filter_key in g:
                    group = g
                    break
            
            if group:
                if filter_key in self.current_meta_filters:
                    self.current_meta_filters.remove(filter_key)
                else:
                    self.current_meta_filters.difference_update(group)
                    self.current_meta_filters.add(filter_key)
            else:
                if filter_key in self.current_meta_filters:
                    self.current_meta_filters.remove(filter_key)
                else:
                    self.current_meta_filters.add(filter_key)

        for act, fk in action_map.items():
            act.setChecked(fk in self.current_meta_filters)

        self.is_meta_filter_active = bool(self.current_meta_filters)
        if hasattr(self, "btn_meta_filter"):
            self.btn_meta_filter.setChecked(self.is_meta_filter_active)

        self.load_audiobooks(use_cache=True)

    def _matches_meta_filter(self, item_data) -> bool:
        """Check if an item matches the active metadata/language filter requirements"""
        if not self.is_meta_filter_active or not self.current_meta_filters:
            return True
            
        if item_data.get("is_folder"):
            return True
            
        for filter_key in self.current_meta_filters:
            if not self._matches_single_filter(item_data, filter_key):
                return False
        return True

    def _matches_single_filter(self, item_data, filter_key) -> bool:
        if filter_key in ("no_cover", "has_cover"):
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
            return has_cover if filter_key == "has_cover" else not has_cover
            
        elif filter_key in ("no_author", "has_author"):
            author = item_data.get("author")
            is_empty_author = (
                not author
                or not author.strip()
                or author.strip() == "(unknown author)"
                or author.strip() == "(неизвестный автор)"
                or author.strip() == tr("scanner.unknown_author")
            )
            return not is_empty_author if filter_key == "has_author" else is_empty_author
            
        elif filter_key in ("no_narrator", "has_narrator"):
            narrator = item_data.get("narrator")
            is_empty_narrator = (
                not narrator
                or not narrator.strip()
                or narrator.strip().lower() in ("(unknown narrator)", "(неизвестный чтец)", "(без чтеца)")
            )
            return not is_empty_narrator if filter_key == "has_narrator" else is_empty_narrator

        elif filter_key == "duration:short":
            duration = item_data.get("duration") or 0.0
            return duration < 3 * 3600
            
        elif filter_key == "duration:medium":
            duration = item_data.get("duration") or 0.0
            return 3 * 3600 <= duration < 10 * 3600
            
        elif filter_key == "duration:long":
            duration = item_data.get("duration") or 0.0
            return duration >= 10 * 3600
            
        elif filter_key == "size:small":
            total_size = item_data.get("total_size") or 0
            return total_size < 100 * 1024 * 1024
            
        elif filter_key == "size:large":
            total_size = item_data.get("total_size") or 0
            return total_size > 1024 * 1024 * 1024
            
        elif filter_key == "progress:almost":
            prog = item_data.get("progress_percent") or 0
            is_completed = item_data.get("is_completed")
            return prog > 80 and not is_completed
            
        elif filter_key == "progress:just_started":
            prog = item_data.get("progress_percent") or 0
            is_started = item_data.get("is_started")
            is_completed = item_data.get("is_completed")
            return prog < 10 and is_started and not is_completed
            
        elif filter_key == "progress:never_opened":
            is_started = item_data.get("is_started")
            listened = item_data.get("listened_duration") or 0.0
            prog = item_data.get("progress_percent") or 0
            return not is_started and listened == 0.0 and prog == 0

        elif filter_key == "lang:none":
            lang = item_data.get("language")
            return not (lang and lang.strip())

        elif filter_key.startswith("lang:"):
            target_lang = filter_key[5:]
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
        if self.is_tile_view and hasattr(self, "tile_view"):
            self.tile_view.canvas.update_selection_state(self.tree.selected_audiobook_paths)
            self.tile_view.canvas.update()

    def deselect_all_audiobooks(self):
        """Clear all selected audiobook paths"""
        self.tree.selected_audiobook_paths.clear()
        self.tree.viewport().update()
        if self.is_tile_view and hasattr(self, "tile_view"):
            self.tile_view.canvas.update_selection_state(self.tree.selected_audiobook_paths)
            self.tile_view.canvas.update()
