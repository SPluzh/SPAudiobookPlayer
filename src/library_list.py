"""List view components for the audiobook library.

This module contains the custom delegate and tree widget used to display
the audiobook library in a hierarchical list view.
"""

from functools import lru_cache
import zlib

from PyQt6.QtCore import (
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from library_utils import (
    NESTING_COLORS,
    draw_library_placeholder,
    get_placeholder_folder_rect,
)
from styles import StyleManager
from translations import tr, trf
import utils

def get_icon(*args, **kwargs):
    return utils.get_icon(*args, **kwargs)

def format_duration(*args, **kwargs):
    return utils.format_duration(*args, **kwargs)

def format_size(*args, **kwargs):
    return utils.format_size(*args, **kwargs)


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

            if getattr(self, "nesting_lines_single_color", False) and getattr(self, "nesting_lines_color", None):
                color = QColor(self.nesting_lines_color)
            else:
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
                        if getattr(self, "nesting_lines_single_color", False) and getattr(self, "nesting_lines_color", None):
                            line_color = QColor(self.nesting_lines_color)
                        else:
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
        progress_percent = data[6] if len(data) > 6 else 0
        codec = data[7] if len(data) > 7 else None
        b_min = data[8] if len(data) > 8 else None
        b_max = data[9] if len(data) > 9 else None
        b_mode = data[10] if len(data) > 10 else None
        container = data[11] if len(data) > 11 else None
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
                painter.setBrush(Qt.BrushStyle.NoBrush)
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

                if item_type == "folder":
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
                if item_type == "folder":
                    item = self.itemFromIndex(index)
                    if item:
                        delegate = self.itemDelegate()
                        if self.mass_selection_mode and delegate and hasattr(delegate, "get_checkbox_rect") and hasattr(delegate, "get_icon_rect"):
                            rect = self.visualRect(index)
                            icon_rect = delegate.get_icon_rect(rect, index)
                            cb_rect = delegate.get_checkbox_rect(QRectF(icon_rect))
                            if cb_rect.contains(QPointF(event.pos())):
                                self.toggle_item_selection_state(item)
                                return
                        
                        item.setExpanded(not item.isExpanded())
                        event.accept()
                        return

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
                                
                                self.toggle_item_selection_state(item)
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

    def toggle_item_selection_state(self, item):
        """Toggle selection state of a tree item (folder or audiobook) and synchronize parents/folders"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not path:
            return
            
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
