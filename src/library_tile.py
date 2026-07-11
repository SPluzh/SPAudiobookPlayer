"""Tile view components for the audiobook library.

This module contains custom widgets and canvases used to display
the audiobook library in a grid/tile layout.
"""

import sys
import math
import queue
import zlib
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QSize,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    QThread,
    QTimer,
)
from PyQt6.QtGui import (
    QIcon,
    QPixmap,
    QBrush,
    QColor,
    QFont,
    QPen,
    QPainter,
    QPainterPath,
    QPalette,
    QFontMetrics,
    QImage,
)
from PyQt6.QtWidgets import (
    QWidget,
    QLayout,
    QScrollArea,
    QFrame,
    QLabel,
    QHBoxLayout,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QStyleOptionViewItem,
)

from library_utils import NESTING_COLORS
from styles import StyleManager
from translations import tr
import utils


def get_base_path():
    return utils.get_base_path()


def get_icon(name, *args, **kwargs):
    return utils.get_icon(name, *args, **kwargs)


def load_icon(path, *args, **kwargs):
    return utils.load_icon(path, *args, **kwargs)


def format_duration(seconds):
    return utils.format_duration(seconds)


def is_last_visible_child(item):
    p_item = item.parent()
    if p_item:
        # Find all visible children of the parent
        visible_children = [
            p_item.child(i)
            for i in range(p_item.childCount())
            if not p_item.child(i).isHidden()
        ]
        return visible_children[-1] == item if visible_children else False
    else:
        tree = item.treeWidget()
        if tree:
            visible_top_items = [
                tree.topLevelItem(i)
                for i in range(tree.topLevelItemCount())
                if not tree.topLevelItem(i).isHidden()
            ]
            return visible_top_items[-1] == item if visible_top_items else False
        return False


def get_item_nesting_chain(item):
    """Get chain of parent paths for consistent color hashing and last-child info.

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


class WrapLayout(QLayout):
    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        if hasattr(self, "_items"):
            del self._items

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        # Force a minimum calculation width of 350 to prevent layout spikes when width is very small or 0
        calc_width = max(width, 350)
        res = self._do_layout(QRect(0, 0, calc_width, 0), True)
        # Clamp the height to a safe maximum of 30000 to prevent Windows GDI 16-bit coordinate overflow crashes
        res = min(res, 30000)
        return res

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            widget = item.widget()
            if widget and widget.isHidden():
                continue
            min_sz = item.minimumSize()
            size = size.expandedTo(min_sz)
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect, test_only):
        try:
            margins = self.contentsMargins()
            effective_rect = rect.adjusted(
                +margins.left(), +margins.top(), -margins.right(), -margins.bottom()
            )
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
                    space_x = (
                        widget.style().layoutSpacing(
                            QSizePolicy.ControlType.PushButton,
                            QSizePolicy.ControlType.PushButton,
                            Qt.Orientation.Horizontal,
                        )
                    )
                if space_y == -1:
                    space_y = (
                        widget.style().layoutSpacing(
                            QSizePolicy.ControlType.PushButton,
                            QSizePolicy.ControlType.PushButton,
                            Qt.Orientation.Vertical,
                        )
                    )

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

            return (
                y + line_height - effective_rect.y() + margins.top() + margins.bottom()
            )
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

    def __init__(
        self,
        path,
        title,
        author,
        narrator,
        progress_percent,
        is_started,
        is_completed,
        is_favorite,
        description,
        pixmap,
        icon_size,
        duration=0.0,
        language=None,
        parent=None,
    ):
        super().__init__(parent)
        self.path = path if path is not None else ""
        self.title = title if title is not None else ""
        self.author = author if author is not None else ""
        self.narrator = narrator if narrator is not None else ""
        self.progress_percent = (
            progress_percent if progress_percent is not None else 0.0
        )
        self.is_started = bool(is_started)
        self.is_completed = bool(is_completed)
        self.is_favorite = bool(is_favorite)
        self.description = description if description is not None else ""
        self.pixmap = pixmap
        self.icon_size = icon_size
        self.duration = duration
        self.language = language
        self.is_playing = False
        self.is_paused = True
        self.selected = False

        self.setObjectName("bookTile")
        self.setMouseTracking(True)

        self.padding = 8
        self.title_area_height = 85
        self.width_val = self.icon_size + self.padding * 2
        self.height_val = (
            self.icon_size + self.padding * 2 + self.title_area_height
        )
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
        return QRectF(
            center.x() - btn_size / 2.0,
            center.y() - btn_size / 2.0,
            btn_size,
            btn_size,
        )

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
        size = 20.0
        # Position: Top-Left of icon, mirrored from heart
        return QRectF(
            float(icon_rect.left() - 4),
            float(icon_rect.top() - 4),
            float(size),
            float(size),
        )

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
            _, status_color = StyleManager.get_theme_property(
                "delegate_status_completed"
            )
            if (
                not status_color
                or not status_color.isValid()
                or status_color == QColor()
            ):
                status_color = QColor("#4ecca3")
        elif self.is_started:
            _, status_color = StyleManager.get_theme_property(
                "delegate_status_started"
            )
            if (
                not status_color
                or not status_color.isValid()
                or status_color == QColor()
            ):
                status_color = QColor("#f9ca24")
        else:
            _, status_color = StyleManager.get_theme_property("delegate_status_new")
            if (
                not status_color
                or not status_color.isValid()
                or status_color == QColor()
            ):
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
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            has_progress = self.progress_percent > 0 or self.is_started
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
            is_play_hovered = self.hovered_field == "play"

            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Button circle
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            btn_color = QColor(accent_color)
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
                start_x = play_rect.left() + (play_rect.width() - total_w) // 2
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
                    center_f.x() - side / 3.0 + h_offset,
                    center_f.y() - side / 2.0,
                )
                tri_path.lineTo(
                    center_f.x() - side / 3.0 + h_offset,
                    center_f.y() + side / 2.0,
                )
                tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                tri_path.closeSubpath()

                p.fillPath(tri_path, Qt.GlobalColor.white)

            p.restore()

        if self.is_favorite:
            heart_rect = self.get_heart_rect(icon_rect)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_over_heart = self.hovered_field == "heart"

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
            if (
                not accent_color
                or not accent_color.isValid()
                or accent_color == QColor()
            ):
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

        if self.description:
            info_rect = self.get_info_rect(icon_rect)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_over_info = self.hovered_field == "info"

            # Background: Color from QSS
            prop = "icon_background_hover" if is_over_info else "icon_background"
            _, bg_color = StyleManager.get_theme_property(prop)
            if not bg_color or not bg_color.isValid() or bg_color == QColor():
                bg_color = QColor(0, 0, 0, 150)

            p.setBrush(bg_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(info_rect)

            # Draw 'i'
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if (
                not accent_color
                or not accent_color.isValid()
                or accent_color == QColor()
            ):
                accent_color = QColor("#018574")
            p.setPen(accent_color)
            font = p.font()
            font.setBold(True)
            font.setPixelSize(14)
            p.setFont(font)
            p.drawText(info_rect, Qt.AlignmentFlag.AlignCenter, "i")
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
                    fill_rect = QRectF(
                        pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height()
                    )
                    p.fillRect(fill_rect, accent_color)
            p.restore()

        if self.duration:
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            duration_text = format_duration(self.duration)
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            text_width = fm.horizontalAdvance(duration_text)
            text_height = fm.height()
            pad_h = 4
            pad_v = 2
            pill_width = text_width + pad_h * 2
            pill_height = text_height + pad_v * 2

            has_progress = self.progress_percent > 0 or self.is_started
            margin_bottom = 4 + (pb_h if has_progress else 0)
            margin_right = 4

            pill_x = icon_rect.right() - pill_width - margin_right
            pill_y = icon_rect.bottom() - pill_height - margin_bottom
            pill_rect = QRectF(pill_x, pill_y, pill_width, pill_height)

            p.setBrush(QColor(0, 0, 0, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(pill_rect, 3.0, 3.0)

            p.setPen(QColor("#ffffff"))
            p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, duration_text)
            p.restore()

        if (
            self.language
            and str(self.language).strip()
            and str(self.language).lower() != "unknown"
        ):
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            lang_text = str(self.language).strip().upper()
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            text_width = fm.horizontalAdvance(lang_text)
            text_height = fm.height()
            pad_h = 4
            pad_v = 2
            pill_width = text_width + pad_h * 2
            pill_height = text_height + pad_v * 2

            has_progress = self.progress_percent > 0 or self.is_started
            margin_bottom = 4 + (pb_h if has_progress else 0)
            margin_left = 4

            pill_x = icon_rect.left() + margin_left
            pill_y = icon_rect.bottom() - pill_height - margin_bottom
            pill_rect = QRectF(pill_x, pill_y, pill_width, pill_height)

            p.setBrush(QColor(0, 0, 0, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(pill_rect, 3.0, 3.0)

            p.setPen(QColor("#ffffff"))
            p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, lang_text)
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
            elided_title = fm.elidedText(
                self.title, Qt.TextElideMode.ElideRight, available_width * 2
            )

            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            title_height = min(title_bound.height(), fm.height() * 2)

            title_rect = QRect(self.padding, text_y, available_width, title_height)
            p.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
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
                author_icon_rect = QRect(
                    self.padding, author_icon_y, author_icon_size, author_icon_size
                )

                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.author_icon.paint(p, author_icon_rect)
                p.restore()

                author_x += author_icon_size + 3

            elided_author = fm.elidedText(
                self.author,
                Qt.TextElideMode.ElideRight,
                available_width - (author_x - self.padding),
            )

            author_rect = QRect(
                author_x,
                text_y,
                available_width - (author_x - self.padding),
                fm.height(),
            )
            p.drawText(
                author_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_author,
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
                narrator_icon_rect = QRect(
                    self.padding, narrator_icon_y, narrator_icon_size, narrator_icon_size
                )

                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.narrator_icon.paint(p, narrator_icon_rect)
                p.restore()

                narrator_x += narrator_icon_size + 3

            elided_narrator = fm.elidedText(
                self.narrator,
                Qt.TextElideMode.ElideRight,
                available_width - (narrator_x - self.padding),
            )

            narrator_rect = QRect(
                narrator_x,
                text_y,
                available_width - (narrator_x - self.padding),
                fm.height(),
            )
            p.drawText(
                narrator_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_narrator,
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
            self.context_menu_requested.emit(
                self.path, event.globalPosition().toPoint()
            )
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

        pe = (
            QStyle.PrimitiveElement.PE_IndicatorArrowDown
            if self.expanded
            else QStyle.PrimitiveElement.PE_IndicatorArrowRight
        )
        self.style().drawPrimitive(pe, opt, painter, self)


class FolderHeaderWidget(QWidget):
    toggled = pyqtSignal(str, bool)

    def __init__(
        self,
        path,
        display_name,
        depth,
        chain,
        is_last_child,
        is_expanded=True,
        parent=None,
        show_nesting=None,
        nesting_single_color=None,
        nesting_color=None,
        folder_icon=None,
        row_height=None,
    ):
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

        self.show_nesting = show_nesting
        self.nesting_single_color = nesting_single_color
        self.nesting_color = nesting_color
        self.folder_icon = folder_icon

        if row_height is None:
            # Fallback or local import to avoid circular dependency
            from library import LibraryWidget

            library = self.window().findChild(LibraryWidget)
            row_height = 35
            if library and hasattr(library, "delegate") and library.delegate:
                row_height = library.delegate.folder_row_height

            if self.show_nesting is None and library:
                self.show_nesting = getattr(library, "show_nesting_lines", True)
            if self.nesting_single_color is None and library:
                self.nesting_single_color = getattr(
                    library, "nesting_lines_single_color", False
                )
            if self.nesting_color is None and library:
                self.nesting_color = getattr(library, "nesting_lines_color", None)
            if self.folder_icon is None and library:
                self.folder_icon = getattr(library, "folder_icon", None)

        if self.show_nesting is None:
            self.show_nesting = True

        self.setFixedHeight(row_height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(0)

        # 1. Left indent spacer
        indent = 12 if self.show_nesting else 8
        if depth > 0:
            layout.addSpacing(depth * indent)

        # 2. Branch arrow widget
        self.arrow_widget = FolderBranchIndicator(self.expanded, self)
        layout.addWidget(self.arrow_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # 3. Spacing between arrow column and folder icon
        spacing = (10 if depth == 0 else 22) if self.show_nesting else 10
        layout.addSpacing(spacing)

        # 4. Folder icon label
        self.icon_label = QLabel()
        self.icon_label.setObjectName("FolderHeaderIcon")
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setScaledContents(True)
        if self.folder_icon:
            self.icon_label.setPixmap(self.folder_icon.pixmap(20, 20))
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
                hover_color = QColor(
                    text_color.red(), text_color.green(), text_color.blue(), 15
                )
            else:
                hover_color = QColor(255, 255, 255, 10)
            p.fillRect(self.rect(), hover_color)

        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

        indent = 12
        line_width = 2

        if self.show_nesting:
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

                if self.nesting_single_color and self.nesting_color:
                    color = QColor(self.nesting_color)
                else:
                    path_hash = zlib.adler32(
                        parent_path_str.encode("utf-8", errors="ignore")
                    )
                    color_index = path_hash % len(NESTING_COLORS)
                    color = NESTING_COLORS[color_index]

                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(color)

                line_x = 24 + i * indent

                if i == self.depth - 1:
                    # This is the folder's own nesting line/branch
                    if self.is_last_child:
                        # └ pattern
                        v_end = (
                            self.height()
                            if self.expanded
                            else (self.height() // 2 + line_width // 2)
                        )
                        p.drawRect(QRect(line_x, 0, line_width, v_end))
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
                        p.drawRect(QRect(line_x, 0, line_width, self.height()))
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

            if self.show_nesting:
                bar_x = 14 if self.depth == 0 else (26 + self.depth * 12)
            else:
                bar_x = 14 + self.depth * 8
            bar_rect = QRectF(
                float(bar_x),
                4.0,
                3.0,
                float(self.height() - 8),
            )
            p.drawRoundedRect(bar_rect, 2.0, 2.0)

        # Draw horizontal line at bottom for expanded folder
        if self.show_nesting and self.expanded and self.depth >= 0:
            if self.path:
                if self.nesting_single_color and self.nesting_color:
                    line_color = QColor(self.nesting_color)
                else:
                    path_hash = zlib.adler32(
                        str(self.path).encode("utf-8", errors="ignore")
                    )
                    color_index = path_hash % len(NESTING_COLORS)
                    line_color = NESTING_COLORS[color_index]

                p.setPen(QPen(line_color, line_width))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

                start_x = 12 if self.depth == 0 else (18 + self.depth * 12)

                y_pos = self.height() - 1
                p.drawLine(start_x, y_pos, self.width(), y_pos)

        p.end()


class BooksContainerWidget(QWidget):
    def __init__(
        self,
        chain,
        depth,
        parent=None,
        show_nesting=None,
        nesting_single_color=None,
        nesting_color=None,
    ):
        super().__init__(parent)
        self.chain = chain
        self.depth = depth

        self.show_nesting = show_nesting
        self.nesting_single_color = nesting_single_color
        self.nesting_color = nesting_color

        if self.show_nesting is None:
            # Fallback or local import to avoid circular dependency
            from library import LibraryWidget

            library = self.window().findChild(LibraryWidget)
            if library:
                self.show_nesting = getattr(library, "show_nesting_lines", True)
                self.nesting_single_color = getattr(
                    library, "nesting_lines_single_color", False
                )
                self.nesting_color = getattr(library, "nesting_lines_color", None)

        if self.show_nesting is None:
            self.show_nesting = True

        if self.show_nesting:
            left_margin = 14 if depth == 0 else (26 + depth * 12)
        else:
            left_margin = 14 + depth * 8
        self.setContentsMargins(left_margin, 4, 0, 4)

    def paintEvent(self, event):
        if not self.show_nesting:
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

            if self.nesting_single_color and self.nesting_color:
                color = QColor(self.nesting_color)
            else:
                path_hash = zlib.adler32(
                    parent_path_str.encode("utf-8", errors="ignore")
                )
                color_index = path_hash % len(NESTING_COLORS)
                color = NESTING_COLORS[color_index]

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)

            line_x = 24 + i * indent
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


class CoverLoader(QThread):
    cover_loaded = pyqtSignal(str, int, QImage)  # path, physical_size, QImage

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = queue.Queue()
        self._running = True
        self._requested = set()

    def queue_load(self, path, physical_size):
        key = (path, physical_size)
        if key in self._requested:
            return
        self._requested.add(key)
        self._queue.put(key)

    def stop(self):
        self._running = False
        self._queue.put((None, None))

    def run(self):
        while self._running:
            try:
                path, physical_size = self._queue.get()
                if path is None or not self._running:
                    break
                p = Path(path)
                if not p.exists() or not p.is_file():
                    continue
                image = QImage(path)
                if not image.isNull():
                    # Scale original image once (Foreground)
                    fg = image.scaled(
                        physical_size,
                        physical_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                    if fg.width() < physical_size or fg.height() < physical_size:
                        # Create square image canvas and fill background
                        result = QImage(
                            physical_size, physical_size, QImage.Format.Format_ARGB32
                        )
                        result.fill(Qt.GlobalColor.black)

                        painter = QPainter(result)
                        try:
                            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                            painter.setRenderHint(
                                QPainter.RenderHint.SmoothPixmapTransform
                            )

                            blur_factor = (
                                0.05  # Strong blur for the background
                            )

                            if fg.height() < physical_size:  # Landscape
                                y_offset = (physical_size - fg.height()) // 2

                                # Top
                                if y_offset > 0:
                                    top_strip = fg.copy(0, 0, fg.width(), 1)
                                    top_bg = top_strip.scaled(
                                        physical_size,
                                        y_offset,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    small = top_bg.scaled(
                                        int(physical_size * blur_factor),
                                        int(y_offset * blur_factor) or 1,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    blurred = small.scaled(
                                        physical_size,
                                        y_offset,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    painter.drawImage(0, 0, blurred)

                                # Bottom
                                if physical_size - (y_offset + fg.height()) > 0:
                                    bot_h = physical_size - (y_offset + fg.height())
                                    bot_strip = fg.copy(
                                        0, fg.height() - 1, fg.width(), 1
                                    )
                                    bot_bg = bot_strip.scaled(
                                        physical_size,
                                        bot_h,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    small = bot_bg.scaled(
                                        int(physical_size * blur_factor),
                                        int(bot_h * blur_factor) or 1,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    blurred = small.scaled(
                                        physical_size,
                                        bot_h,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    painter.drawImage(
                                        0, y_offset + fg.height(), blurred
                                    )

                            elif fg.width() < physical_size:  # Portrait
                                x_offset = (physical_size - fg.width()) // 2

                                # Left
                                if x_offset > 0:
                                    left_strip = fg.copy(0, 0, 1, fg.height())
                                    left_bg = left_strip.scaled(
                                        x_offset,
                                        physical_size,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    small = left_bg.scaled(
                                        int(x_offset * blur_factor) or 1,
                                        int(physical_size * blur_factor),
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    blurred = small.scaled(
                                        x_offset,
                                        physical_size,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    painter.drawImage(0, 0, blurred)

                                # Right
                                if physical_size - (x_offset + fg.width()) > 0:
                                    right_w = physical_size - (
                                        x_offset + fg.width()
                                    )
                                    right_strip = fg.copy(
                                        fg.width() - 1, 0, 1, fg.height()
                                    )
                                    right_bg = right_strip.scaled(
                                        right_w,
                                        physical_size,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    small = right_bg.scaled(
                                        int(right_w * blur_factor) or 1,
                                        int(physical_size * blur_factor),
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    blurred = small.scaled(
                                        right_w,
                                        physical_size,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation,
                                    )
                                    painter.drawImage(
                                        x_offset + fg.width(), 0, blurred
                                    )

                            # Draw original image in center
                            x = (physical_size - fg.width()) // 2
                            y = (physical_size - fg.height()) // 2
                            painter.drawImage(x, y, fg)
                        finally:
                            painter.end()

                        scaled_image = result
                    else:
                        scaled_image = fg

                    if not scaled_image.isNull():
                        self.cover_loaded.emit(path, physical_size, scaled_image)
            except Exception as e:
                print(f"[CoverLoader Error]: {e}", flush=True)


class VirtualTileCanvas(QWidget):
    def __init__(self, tile_flow_widget):
        super().__init__(tile_flow_widget)
        self.tile_flow_widget = tile_flow_widget
        self.setObjectName("libraryTileCanvas")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.tree_root_item = None
        self.blocks = []
        self.calculated_height = 0
        self.selected_paths = set()

        self.hovered_block = None
        self.hovered_book = None
        self.hovered_field = None

        self.padding = 8
        self.play_icon = get_icon("play")
        self.pause_icon = get_icon("pause")
        self.info_icon = get_icon("info_duration")
        self.author_icon = get_icon("author")
        self.narrator_icon = get_icon("narrator")

        self.cover_loader = CoverLoader(self)
        self.cover_loader.cover_loaded.connect(self.on_cover_loaded)
        self.cover_loader.start()

        self.cover_cache = {}

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        if hasattr(self, "cover_loader") and self.cover_loader:
            try:
                self.cover_loader.stop()
                self.cover_loader.wait()
            except (RuntimeError, AttributeError, ReferenceError):
                pass
        super().destroy(destroyWindow, destroySubWindows)

    def populate(self, tree_root_item):
        self.tree_root_item = tree_root_item
        self.rebuild_blocks()
        self.update_layout()
        self.update()

    def rebuild_blocks(self):
        if not self.tree_root_item:
            self.blocks = []
            return

        blocks = []
        current_books_block = None

        def traverse(item, depth):
            nonlocal current_books_block
            child_count = item.childCount()
            for i in range(child_count):
                child = item.child(i)
                if child.isHidden():
                    continue

                item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
                path = child.data(0, Qt.ItemDataRole.UserRole)
                chain = get_item_nesting_chain(child)
                is_last_child = is_last_visible_child(child)

                if item_type == "folder":
                    current_books_block = None

                    display_name = (
                        child.data(0, Qt.ItemDataRole.UserRole + 5)
                        or child.text(0)
                    )
                    is_expanded = child.isExpanded()
                    (
                        books_count,
                        total_seconds,
                    ) = self.tile_flow_widget.parent_library._get_folder_stats(
                        child
                    )

                    folder_block = {
                        "type": "folder",
                        "path": path,
                        "display_name": display_name,
                        "depth": depth,
                        "chain": chain,
                        "is_last_child": is_last_child,
                        "is_expanded": is_expanded,
                        "books_count": books_count,
                        "total_seconds": total_seconds,
                        "tree_item": child,
                        "y": 0,
                        "height": 0,
                    }
                    blocks.append(folder_block)

                    if is_expanded:
                        books_block = {
                            "type": "books",
                            "depth": depth + 1,
                            "chain": chain + [(path, is_last_child)],
                            "is_last_child": is_last_child,
                            "books": [],
                            "y": 0,
                            "height": 0,
                        }
                        current_books_block = books_block
                        blocks.append(books_block)
                        traverse(child, depth + 1)

                elif item_type == "audiobook":
                    if current_books_block is None:
                        current_books_block = {
                            "type": "books",
                            "depth": depth,
                            "chain": chain,
                            "is_last_child": is_last_child,
                            "books": [],
                            "y": 0,
                            "height": 0,
                        }
                        blocks.append(current_books_block)

                    current_books_block["is_last_child"] = is_last_child
                    book_data = self._extract_book_data(child)
                    current_books_block["books"].append(book_data)

            current_books_block = None

        traverse(self.tree_root_item, 0)
        self.blocks = [
            b for b in blocks if b["type"] != "books" or len(b["books"]) > 0
        ]

    def _extract_book_data(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        data = item.data(0, Qt.ItemDataRole.UserRole + 2) or ()
        status_data = item.data(0, Qt.ItemDataRole.UserRole + 3) or ()

        author = data[0] if len(data) > 0 else ""
        title = data[1] if len(data) > 1 else ""
        narrator = data[2] if len(data) > 2 else ""
        progress_percent = data[6] if len(data) > 6 else 0.0
        duration = data[4] if len(data) > 4 else 0.0
        description = data[12] if len(data) > 12 else ""
        language = data[14] if len(data) > 14 else None

        is_started = status_data[0] if len(status_data) > 0 else False
        is_completed = status_data[1] if len(status_data) > 1 else False
        is_favorite = status_data[2] if len(status_data) > 2 else False

        cover_path = item.data(0, Qt.ItemDataRole.UserRole + 5)
        tags = item.data(0, Qt.ItemDataRole.UserRole + 4) or []

        return {
            "path": path,
            "title": title,
            "author": author,
            "narrator": narrator,
            "progress_percent": progress_percent,
            "duration": duration,
            "language": language,
            "is_started": is_started,
            "is_completed": is_completed,
            "is_favorite": is_favorite,
            "description": description,
            "cover_path": cover_path,
            "tags": tags,
            "rect": QRect(),
            "tree_item": item,
        }

    def update_layout(self):
        canvas_width = self.width()
        current_y = 4

        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )
        tile_w = icon_size + 16
        tile_h = icon_size + 16 + 100
        hspacing = 6
        vspacing = 6

        folder_h = 35
        library = self.tile_flow_widget.parent_library
        if library and hasattr(library, "delegate") and library.delegate:
            folder_h = library.delegate.folder_row_height

        for block in self.blocks:
            block["y"] = current_y

            if block["type"] == "folder":
                block["height"] = folder_h
                current_y += folder_h
            elif block["type"] == "books":
                show_nesting = (
                    getattr(library, "show_nesting_lines", True)
                    if library
                    else True
                )
                if show_nesting:
                    grid_left = (
                        14 if block["depth"] == 0 else (26 + block["depth"] * 12)
                    )
                else:
                    grid_left = 14 + block["depth"] * 8
                avail_w = canvas_width - grid_left - 12
                cols = max(1, int((avail_w + hspacing) / (tile_w + hspacing)))
                block["cols"] = cols

                n = len(block["books"])
                rows = math.ceil(n / cols)
                grid_h = (
                    rows * tile_h + (rows - 1) * vspacing + 8 if rows > 0 else 0
                )
                block["height"] = grid_h

                for idx, book in enumerate(block["books"]):
                    row = idx // cols
                    col = idx % cols
                    tx = grid_left + col * (tile_w + hspacing)
                    ty = current_y + 4 + row * (tile_h + vspacing)
                    book["rect"] = QRect(tx, ty, tile_w, tile_h)

                current_y += grid_h

        self.calculated_height = current_y + 4
        self.setMinimumHeight(self.calculated_height)
        self.updateGeometry()

    def sizeHint(self):
        return QSize(self.width(), self.calculated_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()

    def on_cover_loaded(self, path, physical_size, qimage):
        pixmap = QPixmap.fromImage(qimage)
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        self.cover_cache[(path, physical_size)] = pixmap

        for block in self.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    cover_p_str = book.get("cover_path")
                    if cover_p_str:
                        cover_p = Path(cover_p_str)
                        if (
                            not cover_p.is_absolute()
                            and self.tile_flow_widget.config.get("default_path")
                        ):
                            cover_p = (
                                Path(
                                    self.tile_flow_widget.config.get("default_path")
                                )
                                / cover_p
                            )
                        if str(cover_p) == path:
                            self.update(book["rect"])

    def update_selection_state(self, selected_paths):
        self.selected_paths = selected_paths
        self.update()

    def update_playback_state(self, playing_path, is_paused):
        self.update()

    def update_texts(self):
        self.rebuild_blocks()
        self.update_layout()
        self.update()

    def refresh_tile(self, path):
        found_book = None
        for block in self.blocks:
            if block["type"] == "books":
                for book in block["books"]:
                    if book["path"] == path:
                        found_book = book
                        break
                if found_book:
                    break

        if found_book and found_book.get("tree_item"):
            new_data = self._extract_book_data(found_book["tree_item"])
            found_book.update(new_data)
            physical_size = int(
                self.tile_flow_widget.config.get("audiobook_icon_size", 100)
                * 1.5
                * self.devicePixelRatioF()
            )
            if found_book.get("cover_path"):
                cover_p = Path(found_book["cover_path"])
                if (
                    not cover_p.is_absolute()
                    and self.tile_flow_widget.config.get("default_path")
                ):
                    cover_p = (
                        Path(self.tile_flow_widget.config.get("default_path"))
                        / cover_p
                    )
                abs_path_str = str(cover_p)
                self.cover_loader._requested.discard((abs_path_str, physical_size))
                self.cover_cache.pop((abs_path_str, physical_size), None)
            self.update_layout()
            self.update(found_book["rect"])

    def on_folder_toggled(self, path, is_expanded):
        self.tile_flow_widget.parent_library.db.update_folder_expanded_state(
            path, is_expanded
        )
        self.tile_flow_widget.parent_library.update_cached_folder_expanded_state(
            path, is_expanded
        )

        item = self.tile_flow_widget.parent_library.find_item_by_path(
            self.tile_flow_widget.parent_library.tree.invisibleRootItem(), path
        )
        if item:
            self.tile_flow_widget.parent_library.tree.blockSignals(True)
            item.setExpanded(is_expanded)
            self.tile_flow_widget.parent_library.tree.blockSignals(False)

        self.rebuild_blocks()
        self.update_layout()
        self.update()

    def get_tags_rects(self, book) -> list:
        tags = book.get("tags")
        if not tags:
            return []

        tile_rect = book["rect"]
        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )
        icon_rect = QRect(
            tile_rect.left() + 8, tile_rect.top() + 8, icon_size, icon_size
        )

        text_y = icon_rect.bottom() + 12
        available_width = tile_rect.width() - 16
        padding = tile_rect.left() + 8

        title = book.get("title", "")
        if title:
            font, _ = StyleManager.get_theme_property("delegate_title")
            f = QFont(font) if font else QFont()
            f.setPixelSize(13)
            fm = QFontMetrics(f)
            elided_title = fm.elidedText(
                title, Qt.TextElideMode.ElideRight, available_width * 2
            )
            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            title_height = min(title_bound.height(), fm.height() * 2)
            text_y += title_height + 4

        author = book.get("author", "")
        if author:
            font, _ = StyleManager.get_theme_property("delegate_author")
            f = QFont(font) if font else QFont()
            f.setPixelSize(11)
            fm = QFontMetrics(f)
            text_y += fm.height() + 2

        narrator = book.get("narrator", "")
        if narrator:
            font, _ = StyleManager.get_theme_property("delegate_narrator")
            f = QFont(font) if font else QFont()
            f.setPixelSize(11)
            fm = QFontMetrics(f)
            text_y += fm.height() + 2
        elif author:
            text_y += 2
        elif title:
            text_y += 2

        tag_rects = []
        tag_x = padding
        font_tag, _ = StyleManager.get_theme_property("delegate_info_font")
        f = QFont(font_tag) if font_tag else QFont()
        fm = QFontMetrics(f)
        t_h = fm.height() + 4

        for tag in tags:
            tag_name = tag["name"]
            t_w = fm.horizontalAdvance(tag_name)
            tag_rect = QRectF(
                float(tag_x), float(text_y), float(t_w + 12), float(t_h)
            )

            if tag_rect.right() > tile_rect.right() - 8:
                break

            tag_rects.append((tag, tag_rect))
            tag_x += tag_rect.width() + 6

        return tag_rects

    def get_author_rect(self, book) -> QRect:
        author = book.get("author", "")
        if not author:
            return QRect()

        tile_rect = book["rect"]
        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )
        icon_rect = QRect(
            tile_rect.left() + 8, tile_rect.top() + 8, icon_size, icon_size
        )

        text_y = icon_rect.bottom() + 12
        available_width = tile_rect.width() - 16
        padding = tile_rect.left() + 8

        title = book.get("title", "")
        if title:
            font, _ = StyleManager.get_theme_property("delegate_title")
            f = QFont(font) if font else QFont()
            f.setPixelSize(13)
            fm = QFontMetrics(f)
            elided_title = fm.elidedText(
                title, Qt.TextElideMode.ElideRight, available_width * 2
            )
            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            title_height = min(title_bound.height(), fm.height() * 2)
            text_y += title_height + 4

        font, _ = StyleManager.get_theme_property("delegate_author")
        f = QFont(font) if font else QFont()
        f.setPixelSize(11)
        fm = QFontMetrics(f)

        author_x = padding
        icon_width = 0
        if self.author_icon and not self.author_icon.isNull():
            icon_width = 14 + 3
            author_x += icon_width

        text_width = fm.horizontalAdvance(author)
        actual_width = min(text_width, available_width - icon_width)

        return QRect(padding, text_y, icon_width + actual_width, fm.height())

    def get_narrator_rect(self, book) -> QRect:
        narrator = book.get("narrator", "")
        if not narrator:
            return QRect()

        tile_rect = book["rect"]
        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )
        icon_rect = QRect(
            tile_rect.left() + 8, tile_rect.top() + 8, icon_size, icon_size
        )

        text_y = icon_rect.bottom() + 12
        available_width = tile_rect.width() - 16
        padding = tile_rect.left() + 8

        title = book.get("title", "")
        if title:
            font, _ = StyleManager.get_theme_property("delegate_title")
            f = QFont(font) if font else QFont()
            f.setPixelSize(13)
            fm = QFontMetrics(f)
            elided_title = fm.elidedText(
                title, Qt.TextElideMode.ElideRight, available_width * 2
            )
            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            title_height = min(title_bound.height(), fm.height() * 2)
            text_y += title_height + 4

        author = book.get("author", "")
        if author:
            font, _ = StyleManager.get_theme_property("delegate_author")
            f = QFont(font) if font else QFont()
            f.setPixelSize(11)
            fm = QFontMetrics(f)
            text_y += fm.height() + 2

        font, _ = StyleManager.get_theme_property("delegate_narrator")
        f = QFont(font) if font else QFont()
        f.setPixelSize(11)
        fm = QFontMetrics(f)

        narrator_x = padding
        icon_width = 0
        if self.narrator_icon and not self.narrator_icon.isNull():
            icon_width = 14 + 3
            narrator_x += icon_width

        text_width = fm.horizontalAdvance(narrator)
        actual_width = min(text_width, available_width - icon_width)

        return QRect(padding, text_y, icon_width + actual_width, fm.height())

    def get_play_button_rect(self, icon_rect):
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(
            center.x() - btn_size / 2.0,
            center.y() - btn_size / 2.0,
            btn_size,
            btn_size,
        )

    def get_heart_rect(self, icon_rect):
        size = 20.0
        return QRectF(
            float(icon_rect.right() - size + 4),
            float(icon_rect.top() - 4),
            float(size),
            float(size),
        )

    def get_info_rect(self, icon_rect):
        size = 20.0
        return QRectF(
            float(icon_rect.left() - 4),
            float(icon_rect.top() - 4),
            float(size),
            float(size),
        )

    def get_tile_checkbox_rect(self, tile_rect) -> QRectF:
        """Calculate bounds for the mass selection checkbox on a book tile"""
        size = 20.0
        return QRectF(
            float(tile_rect.right() - size - 6),
            float(tile_rect.bottom() - size - 6),
            float(size),
            float(size),
        )

    def get_folder_checkbox_rect(self, icon_rect) -> QRectF:
        """Calculate bounds for the mass selection checkbox on a folder row"""
        cb_width = 18.0
        cb_height = 18.0
        x = icon_rect.right() + 10.0
        y = icon_rect.top() + (icon_rect.height() - cb_height) / 2.0
        return QRectF(x, y, cb_width, cb_height)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        old_hovered_block = self.hovered_block
        old_hovered_book = self.hovered_book
        old_hovered_field = self.hovered_field

        self.hovered_block = None
        self.hovered_book = None
        self.hovered_field = None

        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )

        for block in self.blocks:
            block_y = block["y"]
            block_h = block["height"]

            if block_y <= pos.y() < block_y + block_h:
                if block["type"] == "folder":
                    self.hovered_block = block
                    library = self.tile_flow_widget.parent_library
                    show_nesting = (
                        getattr(library, "show_nesting_lines", True)
                        if library
                        else True
                    )
                    mass_mode = getattr(library.tree, "mass_selection_mode", False)
                    if mass_mode:
                        if show_nesting:
                            icon_x = (
                                22
                                if block["depth"] == 0
                                else (34 + block["depth"] * 12)
                            )
                        else:
                            icon_x = 22 + block["depth"] * 8
                        icon_rect = QRect(
                            icon_x, block_y + (block_h - 20) // 2, 20, 20
                        )
                        cb_rect = self.get_folder_checkbox_rect(icon_rect)
                        if cb_rect.contains(QPointF(pos)):
                            self.hovered_field = "checkbox"
                        else:
                            self.hovered_field = None
                    else:
                        self.hovered_field = None
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    break
                elif block["type"] == "books":
                    for book in block["books"]:
                        tile_rect = book["rect"]
                        if tile_rect.contains(pos):
                            self.hovered_book = book
                            icon_rect = QRect(
                                tile_rect.left() + 8,
                                tile_rect.top() + 8,
                                icon_size,
                                icon_size,
                            )
                            play_rect = self.get_play_button_rect(icon_rect)
                            heart_rect = self.get_heart_rect(icon_rect)
                            info_rect = self.get_info_rect(icon_rect)
                            author_rect = self.get_author_rect(book)
                            narrator_rect = self.get_narrator_rect(book)

                            mass_mode = getattr(
                                self.tile_flow_widget.parent_library.tree,
                                "mass_selection_mode",
                                False,
                            )
                            cb_rect = (
                                self.get_tile_checkbox_rect(tile_rect)
                                if mass_mode
                                else None
                            )
                            is_over_cb = (
                                mass_mode
                                and cb_rect
                                and cb_rect.contains(QPointF(pos))
                            )
                            is_over_heart = book.get(
                                "is_favorite"
                            ) and heart_rect.contains(QPointF(pos))
                            is_over_info = bool(
                                book.get("description")
                            ) and info_rect.contains(QPointF(pos))
                            is_over_author = (
                                not author_rect.isEmpty()
                                and author_rect.contains(pos)
                            )
                            is_over_narrator = (
                                not narrator_rect.isEmpty()
                                and narrator_rect.contains(pos)
                            )

                            is_over_tag = False
                            tags_rects = self.get_tags_rects(book)
                            for tag, tag_rect in tags_rects:
                                if tag_rect.contains(QPointF(pos)):
                                    self.hovered_field = f"tag:{tag['id']}"
                                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                                    is_over_tag = True
                                    break

                            if is_over_cb:
                                self.hovered_field = "checkbox"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            elif play_rect.contains(QPointF(pos)):
                                self.hovered_field = "play"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            elif is_over_heart:
                                self.hovered_field = "heart"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            elif is_over_info:
                                self.hovered_field = "info"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            elif is_over_tag:
                                pass
                            elif is_over_author:
                                self.hovered_field = "author"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            elif is_over_narrator:
                                self.hovered_field = "narrator"
                                self.setCursor(Qt.CursorShape.PointingHandCursor)
                            else:
                                self.hovered_field = None
                                self.setCursor(Qt.CursorShape.ArrowCursor)
                            break
                    break

        if self.hovered_block is None and self.hovered_book is None:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if (
            self.hovered_block != old_hovered_block
            or self.hovered_book != old_hovered_book
            or self.hovered_field != old_hovered_field
        ):
            self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered_block = None
        self.hovered_book = None
        self.hovered_field = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()

        if event.button() == Qt.MouseButton.LeftButton:
            if self.hovered_block and self.hovered_block["type"] == "folder":
                path = self.hovered_block["path"]
                mass_mode = getattr(
                    self.tile_flow_widget.parent_library.tree,
                    "mass_selection_mode",
                    False,
                )
                if mass_mode and self.hovered_field == "checkbox":
                    item = self.hovered_block["tree_item"]
                    if item:
                        self.tile_flow_widget.parent_library.tree.toggle_item_selection_state(
                            item
                        )
                        self.update_selection_state(
                            self.tile_flow_widget.parent_library.tree.selected_audiobook_paths
                        )
                        self.update()
                    event.accept()
                    return
                is_expanded = not self.hovered_block["is_expanded"]
                self.on_folder_toggled(path, is_expanded)
                event.accept()
                return
            elif self.hovered_book:
                path = self.hovered_book["path"]
                if self.hovered_field == "checkbox":
                    self.tile_flow_widget.on_tile_clicked(path)
                    event.accept()
                    return
                elif self.hovered_field == "play":
                    self.tile_flow_widget.on_tile_play_clicked(path)
                    event.accept()
                    return
                elif self.hovered_field == "heart":
                    self.tile_flow_widget.on_tile_favorite_clicked(path)
                    event.accept()
                    return
                elif self.hovered_field == "info":
                    self.tile_flow_widget.on_tile_description_requested(path)
                    event.accept()
                    return
                elif self.hovered_field == "author":
                    author = self.hovered_book.get("author", "")
                    if author:
                        self.tile_flow_widget.parent_library.tree.search_requested.emit(
                            author
                        )
                    event.accept()
                    return
                elif self.hovered_field == "narrator":
                    narrator = self.hovered_book.get("narrator", "")
                    if narrator:
                        self.tile_flow_widget.parent_library.tree.search_requested.emit(
                            narrator
                        )
                    event.accept()
                    return
                elif self.hovered_field and self.hovered_field.startswith("tag:"):
                    tag_id = int(self.hovered_field.split(":")[1])
                    for tag in self.hovered_book.get("tags", []):
                        if tag["id"] == tag_id:
                            self.tile_flow_widget.parent_library.tree.tag_clicked.emit(
                                tag
                            )
                            break
                    event.accept()
                    return
                else:
                    self.tile_flow_widget.on_tile_clicked(path)
                    event.accept()
                    return
        elif event.button() == Qt.MouseButton.RightButton:
            for block in self.blocks:
                block_y = block["y"]
                block_h = block["height"]
                if block_y <= pos.y() < block_y + block_h:
                    if block["type"] == "folder":
                        path = block["path"]
                        item = block["tree_item"]
                        if item:
                            tree_pos = (
                                self.tile_flow_widget.parent_library.tree.viewport().mapFromGlobal(
                                    event.globalPosition().toPoint()
                                )
                            )
                            self.tile_flow_widget.parent_library.show_context_menu(
                                tree_pos, item
                            )
                            event.accept()
                            return
                    elif block["type"] == "books":
                        for book in block["books"]:
                            if book["rect"].contains(pos):
                                path = book["path"]
                                item = book["tree_item"]
                                if item:
                                    tree_pos = (
                                        self.tile_flow_widget.parent_library.tree.viewport().mapFromGlobal(
                                            event.globalPosition().toPoint()
                                        )
                                    )
                                    self.tile_flow_widget.parent_library.show_context_menu(
                                        tree_pos, item
                                    )
                                    event.accept()
                                    return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.hovered_book:
                path = self.hovered_book["path"]
                self.tile_flow_widget.on_tile_double_clicked(path)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        clip_rect = event.rect()

        library = self.tile_flow_widget.parent_library
        show_nesting = (
            getattr(library, "show_nesting_lines", True) if library else True
        )
        single_color = (
            getattr(library, "nesting_lines_single_color", False)
            if library
            else False
        )
        custom_color = (
            getattr(library, "nesting_lines_color", None) if library else None
        )

        icon_size = int(
            self.tile_flow_widget.config.get("audiobook_icon_size", 100) * 1.5
        )
        tile_w = icon_size + 16
        tile_h = icon_size + 16 + 100
        hspacing = 6
        vspacing = 6

        playing_path = None
        if library.delegate:
            playing_path = library.delegate.playing_path
        if not playing_path and library.current_playing_item:
            try:
                playing_path = library.current_playing_item.data(
                    0, Qt.ItemDataRole.UserRole
                )
            except RuntimeError:
                pass
        is_paused = library.delegate.is_paused if library.delegate else True

        selected_paths = getattr(library.tree, "selected_audiobook_paths", set())

        for block in self.blocks:
            block_y = block["y"]
            block_h = block["height"]

            block_rect = QRect(0, block_y, self.width(), block_h)
            if not block_rect.intersects(clip_rect):
                continue

            if block["type"] == "folder":
                depth = block["depth"]
                chain = block["chain"]
                is_last_child = block["is_last_child"]
                is_expanded = block["is_expanded"]
                path = block["path"]
                display_name = block["display_name"]

                if self.hovered_block == block:
                    _, text_color = StyleManager.get_theme_property(
                        "delegate_folder"
                    )
                    if text_color:
                        hover_color = QColor(
                            text_color.red(),
                            text_color.green(),
                            text_color.blue(),
                            15,
                        )
                    else:
                        hover_color = QColor(255, 255, 255, 10)
                    p.fillRect(block_rect, hover_color)

                indent = 12 if show_nesting else 8
                line_width = 2

                if show_nesting:
                    p.save()
                    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    for i in range(depth):
                        if i >= len(chain):
                            continue
                        parent_path_str, _ = chain[i]
                        if i < depth - 1:
                            child_is_last = chain[i + 1][1]
                            if child_is_last:
                                continue

                        if single_color and custom_color:
                            color = QColor(custom_color)
                        else:
                            path_hash = zlib.adler32(
                                parent_path_str.encode("utf-8", errors="ignore")
                            )
                            color_index = path_hash % len(NESTING_COLORS)
                            color = NESTING_COLORS[color_index]

                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(color)
                        line_x = 24 + i * indent

                        if i == depth - 1:
                            if is_last_child:
                                v_end = (
                                    block_h
                                    if is_expanded
                                    else (block_h // 2 + line_width // 2)
                                )
                                p.drawRect(QRect(line_x, block_y, line_width, v_end))
                                p.drawRect(
                                    QRect(
                                        line_x,
                                        block_y
                                        + (block_h - line_width) // 2,
                                        indent,
                                        line_width,
                                    )
                                )
                            else:
                                p.drawRect(
                                    QRect(line_x, block_y, line_width, block_h)
                                )
                                p.drawRect(
                                    QRect(
                                        line_x,
                                        block_y
                                        + (block_h - line_width) // 2,
                                        indent,
                                        line_width,
                                    )
                                )
                        else:
                            p.drawRect(QRect(line_x, block_y, line_width, block_h))

                    if is_expanded and depth >= 0 and path:
                        if single_color and custom_color:
                            line_color = QColor(custom_color)
                        else:
                            path_hash = zlib.adler32(
                                str(path).encode("utf-8", errors="ignore")
                            )
                            color_index = path_hash % len(NESTING_COLORS)
                            line_color = NESTING_COLORS[color_index]
                        p.setPen(QPen(line_color, line_width))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        start_x = 12 if depth == 0 else (18 + depth * 12)
                        p.drawLine(
                            start_x,
                            block_y + block_h - 1,
                            self.width(),
                            block_y + block_h - 1,
                        )
                    p.restore()

                arrow_rect = QRect(
                    depth * indent, block_y + (block_h - 12) // 2, 12, 12
                )
                opt = QStyleOption()
                opt.rect = arrow_rect
                opt.state = QStyle.StateFlag.State_Enabled
                if is_expanded:
                    opt.state |= QStyle.StateFlag.State_Open
                pe = (
                    QStyle.PrimitiveElement.PE_IndicatorArrowDown
                    if is_expanded
                    else QStyle.PrimitiveElement.PE_IndicatorArrowRight
                )
                self.style().drawPrimitive(pe, opt, p, self)

                if show_nesting:
                    icon_x = 22 if depth == 0 else (34 + depth * 12)
                else:
                    icon_x = 22 + depth * 8
                icon_rect = QRect(icon_x, block_y + (block_h - 20) // 2, 20, 20)
                if library.folder_icon:
                    p.drawPixmap(icon_rect, library.folder_icon.pixmap(20, 20))

                mass_mode = getattr(library.tree, "mass_selection_mode", False)
                if mass_mode:
                    cb_rect = self.get_folder_checkbox_rect(icon_rect)
                    is_checked = path in selected_paths
                    is_over_cb = (
                        self.hovered_block == block
                        and self.hovered_field == "checkbox"
                    )

                    p.save()
                    p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    border_color = QColor("#555555")
                    _, accent_color = StyleManager.get_theme_property(
                        "delegate_accent"
                    )
                    if (
                        not accent_color
                        or not accent_color.isValid()
                        or accent_color == QColor()
                    ):
                        accent_color = QColor("#018574")

                    if is_checked:
                        bg_color = QColor(accent_color)
                        if is_over_cb:
                            bg_color = bg_color.lighter(110)
                        p.setBrush(bg_color)
                        p.setPen(Qt.PenStyle.NoPen)
                        p.drawRoundedRect(cb_rect, 4.0, 4.0)

                        checkmark_path = QPainterPath()
                        w = cb_rect.width()
                        h = cb_rect.height()
                        checkmark_path.moveTo(
                            cb_rect.left() + w * 0.25, cb_rect.top() + h * 0.5
                        )
                        checkmark_path.lineTo(
                            cb_rect.left() + w * 0.45, cb_rect.top() + h * 0.75
                        )
                        checkmark_path.lineTo(
                            cb_rect.left() + w * 0.75, cb_rect.top() + h * 0.35
                        )

                        pen = QPen(
                            Qt.GlobalColor.white,
                            2.0,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin,
                        )
                        p.setPen(pen)
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawPath(checkmark_path)
                    else:
                        bg_color = QColor(Qt.GlobalColor.transparent)
                        if is_over_cb:
                            border_color = border_color.lighter(130)
                        p.setBrush(bg_color)
                        p.setPen(QPen(border_color, 1.5))
                        p.drawRoundedRect(cb_rect, 4.0, 4.0)
                    p.restore()

                books_count = block["books_count"]
                total_seconds = block["total_seconds"]
                display_text = display_name
                if books_count > 0:
                    duration_str = format_duration(total_seconds)
                    books_str = library._format_books_count(books_count)
                    display_text = f"{display_name} ({books_str}, {duration_str})"

                text_x = icon_rect.right() + (43 if mass_mode else 8)
                font, color = StyleManager.get_theme_property("delegate_folder")
                if font:
                    p.setFont(font)
                if color and color.isValid():
                    p.setPen(color)
                else:
                    p.setPen(QColor("#CCCCCC"))
                p.drawText(
                    QRect(text_x, block_y, self.width() - text_x - 10, block_h),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    display_text,
                )

                if path and playing_path:
                    p_path = str(playing_path).replace("\\", "/")
                    f_path = str(path).replace("\\", "/")
                    is_active = False
                    if p_path.startswith(f_path):
                        if (
                            len(p_path) == len(f_path)
                            or p_path[len(f_path)] == "/"
                        ):
                            is_active = True
                    if is_active:
                        _, accent_color = StyleManager.get_theme_property(
                            "delegate_accent"
                        )
                        if not accent_color:
                            accent_color = QColor("#018574")
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(accent_color)
                        if show_nesting:
                            bar_x = 14 if depth == 0 else (26 + depth * 12)
                        else:
                            bar_x = 14 + depth * 8
                        bar_rect = QRectF(
                            float(bar_x),
                            float(block_y + 4),
                            3.0,
                            float(block_h - 8),
                        )
                        p.drawRoundedRect(bar_rect, 2.0, 2.0)

            elif block["type"] == "books":
                depth = block["depth"]
                chain = block["chain"]

                if show_nesting:
                    p.save()
                    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    indent = 12
                    line_width = 2
                    for i in range(depth):
                        if i >= len(chain):
                            continue
                        parent_path_str, _ = chain[i]
                        if i < depth - 1:
                            child_is_last = chain[i + 1][1]
                            if child_is_last:
                                continue

                        if single_color and custom_color:
                            color = QColor(custom_color)
                        else:
                            path_hash = zlib.adler32(
                                parent_path_str.encode("utf-8", errors="ignore")
                            )
                            color_index = path_hash % len(NESTING_COLORS)
                            color = NESTING_COLORS[color_index]

                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(color)
                        line_x = 24 + i * indent

                        if i == depth - 1:
                            # Draw row-by-row branches and bends
                            n = len(block["books"])
                            cols = block.get("cols", 1)
                            rows = math.ceil(n / cols)

                            for r in range(rows):
                                row_y = block_y + 4 + r * (tile_h + vspacing)
                                row_h = tile_h
                                cover_center_y = row_y + 8 + icon_size // 2

                                segment_top = block_y if r == 0 else row_y
                                is_last_row = r == rows - 1
                                if is_last_row and block.get("is_last_child", False):
                                    # └ pattern for the last row
                                    p.drawRect(
                                        QRect(
                                            line_x,
                                            segment_top,
                                            line_width,
                                            cover_center_y
                                            - segment_top
                                            + line_width // 2,
                                        )
                                    )
                                    p.drawRect(
                                        QRect(
                                            line_x,
                                            cover_center_y - line_width // 2,
                                            indent,
                                            line_width,
                                        )
                                    )
                                else:
                                    # ├ pattern for other rows
                                    p.drawRect(
                                        QRect(
                                            line_x,
                                            segment_top,
                                            line_width,
                                            (
                                                row_y
                                                + row_h
                                                + (vspacing if not is_last_row else 4)
                                            )
                                            - segment_top,
                                        )
                                    )
                                    p.drawRect(
                                        QRect(
                                            line_x,
                                            cover_center_y - line_width // 2,
                                            indent,
                                            line_width,
                                        )
                                    )
                        else:
                            p.drawRect(QRect(line_x, block_y, line_width, block_h))
                    p.restore()

                dpr = self.devicePixelRatioF()
                physical_size = int(icon_size * dpr)

                for book in block["books"]:
                    tile_rect = book["rect"]
                    if not tile_rect.intersects(clip_rect):
                        continue
                    self._paint_book_tile(
                        p,
                        book,
                        tile_rect,
                        icon_size,
                        physical_size,
                        playing_path,
                        is_paused,
                        selected_paths,
                    )

    def _paint_book_tile(
        self,
        p,
        book,
        tile_rect,
        icon_size,
        physical_size,
        playing_path,
        is_paused,
        selected_paths,
    ):
        is_selected = book["path"] in selected_paths
        is_hovered = self.hovered_book == book
        is_playing = playing_path and str(playing_path).replace(
            "\\", "/"
        ) == str(book["path"]).replace("\\", "/")

        # Check if mass selection mode is active
        library = self.tile_flow_widget.parent_library
        mass_mode = getattr(library.tree, "mass_selection_mode", False)

        p.save()
        # Draw base tile background
        _, bg_color = StyleManager.get_theme_property("tile_background")
        if not bg_color or not bg_color.isValid():
            bg_color = QColor("#444444")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg_color)
        p.drawRoundedRect(QRectF(tile_rect), 6.0, 6.0)

        # Draw selection or hover overlays
        if is_selected and not mass_mode:
            _, sel_bg = StyleManager.get_theme_property("theme_primary")
            if not sel_bg:
                sel_bg = QColor("#3498db")
            sel_bg_alpha = QColor(sel_bg.red(), sel_bg.green(), sel_bg.blue(), 40)
            p.setPen(QPen(sel_bg, 1.0))
            p.setBrush(sel_bg_alpha)
            p.drawRoundedRect(QRectF(tile_rect), 6.0, 6.0)
        elif is_hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 10))
            p.drawRoundedRect(QRectF(tile_rect), 6.0, 6.0)
        p.restore()

        icon_rect = QRect(
            tile_rect.left() + 8, tile_rect.top() + 8, icon_size, icon_size
        )

        cover_path = book.get("cover_path")
        pixmap = None
        if cover_path:
            cover_p = Path(cover_path)
            if (
                not cover_p.is_absolute()
                and self.tile_flow_widget.config.get("default_path")
            ):
                cover_p = (
                    Path(self.tile_flow_widget.config.get("default_path")) / cover_p
                )
            abs_path_str = str(cover_p)
            pixmap = self.cover_cache.get((abs_path_str, physical_size))
            if not pixmap:
                self.cover_loader.queue_load(abs_path_str, physical_size)

        if not pixmap:
            default_key = ("default", physical_size)
            pixmap = self.cover_cache.get(default_key)
            if not pixmap:
                default_cover = self.tile_flow_widget.config.get(
                    "default_cover_file", "resources/icons/default_cover.png"
                )
                default_cover_path = get_base_path() / default_cover
                if default_cover_path.exists() and default_cover_path.is_file():
                    tile_cover_icon = load_icon(
                        default_cover_path, physical_size, force_square=True
                    )
                    if tile_cover_icon and not tile_cover_icon.isNull():
                        pixmap = tile_cover_icon.pixmap(
                            QSize(physical_size, physical_size)
                        )
                        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
                        self.cover_cache[default_key] = pixmap

        p.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
        p.setClipPath(path)
        if pixmap and not pixmap.isNull():
            p.drawPixmap(icon_rect, pixmap)
        p.restore()

        if is_hovered:
            _, overlay_bg = StyleManager.get_theme_property("overlay_background")
            if not overlay_bg:
                overlay_bg = QColor(0, 0, 0, 80)
            p.save()
            p.setClipPath(path)
            p.fillRect(icon_rect, overlay_bg)
            p.restore()

        is_completed = book.get("is_completed", False)
        is_started = book.get("is_started", False)

        # Draw status triangle (New / Started / Finished)
        show_status = (
            getattr(library, "show_status_triangle", True) if library else True
        )
        if show_status:
            if is_completed:
                _, status_color = StyleManager.get_theme_property(
                    "delegate_status_completed"
                )
                if not status_color or not status_color.isValid():
                    status_color = QColor("#4ecca3")
            elif is_started:
                _, status_color = StyleManager.get_theme_property(
                    "delegate_status_started"
                )
                if not status_color or not status_color.isValid():
                    status_color = QColor("#f9ca24")
            else:
                _, status_color = StyleManager.get_theme_property(
                    "delegate_status_new"
                )
                if not status_color or not status_color.isValid():
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

        if is_playing:
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            p.save()
            pen = QPen(accent_color, 8)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            has_progress = book.get("progress_percent", 0.0) > 0 or is_started
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

        if is_hovered or is_playing:
            play_rect = self.get_play_button_rect(icon_rect)
            is_play_hovered = is_hovered and self.hovered_field == "play"

            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color:
                accent_color = QColor("#018574")
            btn_color = QColor(accent_color)
            if not is_play_hovered:
                btn_color.setAlpha(200)
            else:
                btn_color = btn_color.lighter(110)

            p.setBrush(btn_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(play_rect)

            p.setBrush(Qt.GlobalColor.white)
            if is_playing and not is_paused:
                w = play_rect.width() // 5
                h = play_rect.height() // 2
                gap = w // 2
                total_w = w * 2 + gap
                start_x = play_rect.left() + (play_rect.width() - total_w) // 2
                start_y = play_rect.top() + (play_rect.height() - h) // 2
                p.drawRect(QRectF(start_x, start_y, w, h))
                p.drawRect(QRectF(start_x + w + gap, start_y, w, h))
            else:
                side = play_rect.width() // 2
                center_f = QPointF(play_rect.center())
                h_offset = play_rect.width() / 20.0

                tri_path = QPainterPath()
                tri_path.moveTo(
                    center_f.x() - side / 3.0 + h_offset,
                    center_f.y() - side / 2.0,
                )
                tri_path.lineTo(
                    center_f.x() - side / 3.0 + h_offset,
                    center_f.y() + side / 2.0,
                )
                tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                tri_path.closeSubpath()
                p.fillPath(tri_path, Qt.GlobalColor.white)
            p.restore()

        if book.get("is_favorite"):
            heart_rect = self.get_heart_rect(icon_rect)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_over_heart = is_hovered and self.hovered_field == "heart"
            prop = "icon_background_hover" if is_over_heart else "icon_background"
            _, bg_color = StyleManager.get_theme_property(prop)
            if not bg_color or not bg_color.isValid():
                bg_color = QColor(0, 0, 0, 150)
            p.setBrush(bg_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(heart_rect)

            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if not accent_color or not accent_color.isValid():
                accent_color = QColor("#018574")
            p.setBrush(accent_color)

            hr = heart_rect.adjusted(1, 2, -1, -3)
            hpath = QPainterPath()
            hpath.moveTo(hr.center().x(), hr.bottom())
            hpath.cubicTo(
                hr.right(),
                hr.center().y(),
                hr.right(),
                hr.top(),
                hr.center().x(),
                hr.top() + hr.height() * 0.2,
            )
            hpath.cubicTo(
                hr.left(),
                hr.top(),
                hr.left(),
                hr.center().y(),
                hr.center().x(),
                hr.bottom(),
            )
            p.drawPath(hpath)
            p.drawPath(hpath)
            p.restore()

        if book.get("description"):
            info_rect = self.get_info_rect(icon_rect)
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            is_over_info = is_hovered and self.hovered_field == "info"

            # Background: Color from QSS
            prop = "icon_background_hover" if is_over_info else "icon_background"
            _, bg_color = StyleManager.get_theme_property(prop)
            if not bg_color or not bg_color.isValid() or bg_color == QColor():
                bg_color = QColor(0, 0, 0, 150)

            p.setBrush(bg_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(info_rect)

            # Draw 'i'
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if (
                not accent_color
                or not accent_color.isValid()
                or accent_color == QColor()
            ):
                accent_color = QColor("#018574")
            p.setPen(accent_color)
            font = p.font()
            font.setBold(True)
            font.setPixelSize(14)
            p.setFont(font)
            p.drawText(info_rect, Qt.AlignmentFlag.AlignCenter, "i")
            p.restore()

        # Draw mass selection checkbox if mode is active
        library = self.tile_flow_widget.parent_library
        mass_mode = getattr(library.tree, "mass_selection_mode", False)
        if mass_mode:
            cb_rect = self.get_tile_checkbox_rect(tile_rect)
            is_checked = book["path"] in selected_paths
            is_over_cb = is_hovered and self.hovered_field == "checkbox"

            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            border_color = QColor("#555555")
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            if (
                not accent_color
                or not accent_color.isValid()
                or accent_color == QColor()
            ):
                accent_color = QColor("#018574")

            if is_checked:
                bg_color = QColor(accent_color)
                if is_over_cb:
                    bg_color = bg_color.lighter(110)
                p.setBrush(bg_color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(cb_rect, 4.0, 4.0)

                checkmark_path = QPainterPath()
                w = cb_rect.width()
                h = cb_rect.height()
                checkmark_path.moveTo(
                    cb_rect.left() + w * 0.25, cb_rect.top() + h * 0.5
                )
                checkmark_path.lineTo(
                    cb_rect.left() + w * 0.45, cb_rect.top() + h * 0.75
                )
                checkmark_path.lineTo(
                    cb_rect.left() + w * 0.75, cb_rect.top() + h * 0.35
                )

                pen = QPen(
                    Qt.GlobalColor.white,
                    2.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(checkmark_path)
            else:
                bg_color = QColor(Qt.GlobalColor.transparent)
                if is_over_cb:
                    border_color = border_color.lighter(130)
                p.setBrush(bg_color)
                p.setPen(QPen(border_color, 1.5))
                p.drawRoundedRect(cb_rect, 4.0, 4.0)
            p.restore()

        pb_x = icon_rect.left()
        pb_w = icon_rect.width()
        _, border_color = StyleManager.get_theme_property("overlay_progress_bg")
        if not border_color:
            border_color = QColor("#444444")
        _, accent_color = StyleManager.get_theme_property("theme_primary")
        if not accent_color:
            accent_color = QColor("#3498db")

        progress_percent = book.get("progress_percent", 0.0)
        if progress_percent > 0 or is_started:
            p.save()
            pb_rect = QRectF(float(pb_x), float(pb_y), float(pb_w), float(pb_h))
            p.fillRect(pb_rect, border_color)
            if progress_percent > 0:
                fill_w = pb_rect.width() * progress_percent / 100.0
                if fill_w > 0:
                    fill_rect = QRectF(
                        pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height()
                    )
                    p.fillRect(fill_rect, accent_color)
            p.restore()

        duration = book.get("duration", 0.0)
        if duration:
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            duration_text = format_duration(duration)
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            text_width = fm.horizontalAdvance(duration_text)
            text_height = fm.height()
            pad_h = 4
            pad_v = 2
            pill_width = text_width + pad_h * 2
            pill_height = text_height + pad_v * 2

            has_progress = progress_percent > 0 or is_started
            margin_bottom = 4 + (pb_h if has_progress else 0)
            margin_right = 4

            pill_x = icon_rect.right() - pill_width - margin_right
            pill_y = icon_rect.bottom() - pill_height - margin_bottom
            pill_rect = QRectF(pill_x, pill_y, pill_width, pill_height)

            p.setBrush(QColor(0, 0, 0, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(pill_rect, 3.0, 3.0)

            p.setPen(QColor("#ffffff"))
            p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, duration_text)
            p.restore()

        language = book.get("language")
        if (
            language
            and str(language).strip()
            and str(language).lower() != "unknown"
        ):
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            lang_text = str(language).strip().upper()
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            fm = p.fontMetrics()
            text_width = fm.horizontalAdvance(lang_text)
            text_height = fm.height()
            pad_h = 4
            pad_v = 2
            pill_width = text_width + pad_h * 2
            pill_height = text_height + pad_v * 2

            has_progress = progress_percent > 0 or is_started
            margin_bottom = 4 + (pb_h if has_progress else 0)
            margin_left = 4

            pill_x = icon_rect.left() + margin_left
            pill_y = icon_rect.bottom() - pill_height - margin_bottom
            pill_rect = QRectF(pill_x, pill_y, pill_width, pill_height)

            p.setBrush(QColor(0, 0, 0, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(pill_rect, 3.0, 3.0)

            p.setPen(QColor("#ffffff"))
            p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, lang_text)
            p.restore()

        text_y = icon_rect.bottom() + 12
        available_width = tile_rect.width() - 16
        padding = tile_rect.left() + 8

        title = book.get("title", "")
        if title:
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
            elided_title = fm.elidedText(
                title, Qt.TextElideMode.ElideRight, available_width * 2
            )
            title_bound = fm.boundingRect(
                QRect(0, 0, available_width, 100),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            title_height = min(title_bound.height(), fm.height() * 2)

            p.drawText(
                QRect(padding, text_y, available_width, title_height),
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap,
                elided_title,
            )
            p.restore()
            text_y += title_height + 4

        author = book.get("author", "")
        if author:
            p.save()
            font, color = StyleManager.get_theme_property("delegate_author")
            if font:
                font = QFont(font)
                font.setPixelSize(11)
                is_hovered_author = (
                    self.hovered_book == book
                    and getattr(self, "hovered_field", None) == "author"
                )
                if is_hovered_author:
                    font.setBold(True)
                p.setFont(font)
            if color and color.isValid():
                p.setPen(color)
            else:
                p.setPen(QColor("#a0a0a0"))

            fm = p.fontMetrics()
            author_x = padding
            if self.author_icon and not self.author_icon.isNull():
                author_icon_size = 14
                author_icon_y = text_y + (fm.height() - author_icon_size) // 2
                author_icon_rect = QRect(
                    padding, author_icon_y, author_icon_size, author_icon_size
                )

                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.author_icon.paint(p, author_icon_rect)
                p.restore()
                author_x += author_icon_size + 3

            elided_author = fm.elidedText(
                author, Qt.TextElideMode.ElideRight, available_width - (author_x - padding)
            )
            p.drawText(
                QRect(
                    author_x,
                    text_y,
                    available_width - (author_x - padding),
                    fm.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_author,
            )
            p.restore()
            text_y += fm.height() + 2

        narrator = book.get("narrator", "")
        if narrator:
            p.save()
            font, color = StyleManager.get_theme_property("delegate_narrator")
            if font:
                font = QFont(font)
                font.setPixelSize(11)
                is_hovered_narrator = (
                    self.hovered_book == book
                    and getattr(self, "hovered_field", None) == "narrator"
                )
                if is_hovered_narrator:
                    font.setBold(True)
                p.setFont(font)
            if color and color.isValid():
                p.setPen(color)
            else:
                p.setPen(QColor("#808080"))

            fm = p.fontMetrics()
            narrator_x = padding
            if self.narrator_icon and not self.narrator_icon.isNull():
                narrator_icon_size = 14
                narrator_icon_y = text_y + (fm.height() - narrator_icon_size) // 2
                narrator_icon_rect = QRect(
                    padding, narrator_icon_y, narrator_icon_size, narrator_icon_size
                )

                p.save()
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self.narrator_icon.paint(p, narrator_icon_rect)
                p.restore()
                narrator_x += narrator_icon_size + 3

            elided_narrator = fm.elidedText(
                narrator,
                Qt.TextElideMode.ElideRight,
                available_width - (narrator_x - padding),
            )
            p.drawText(
                QRect(
                    narrator_x,
                    text_y,
                    available_width - (narrator_x - padding),
                    fm.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided_narrator,
            )
            p.restore()
            text_y += fm.height() + 2

        # Draw tags
        tags_rects = self.get_tags_rects(book)
        if tags_rects:
            p.save()
            for tag, tag_rect in tags_rects:
                tag_name = tag["name"]
                _, accent_color = StyleManager.get_theme_property(
                    "delegate_accent"
                )
                if not accent_color or not accent_color.isValid():
                    accent_color = QColor("#018574")
                tag_color = QColor(tag["color"] or accent_color.name())

                # Dynamic text color based on brightness
                text_color = (
                    Qt.GlobalColor.white
                    if tag_color.lightness() < 130
                    else Qt.GlobalColor.black
                )

                font_tag, _ = StyleManager.get_theme_property(
                    "delegate_info_font"
                )
                if font_tag:
                    p.setFont(font_tag)

                # Highlight if hovered
                is_hovered_tag = (
                    self.hovered_book == book
                    and getattr(self, "hovered_field", None) == f"tag:{tag['id']}"
                )
                if is_hovered_tag:
                    tag_color = tag_color.lighter(115)

                path = QPainterPath()
                path.addRoundedRect(tag_rect, 4.0, 4.0)

                p.setBrush(tag_color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(path)

                p.setPen(text_color)
                p.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_name)
            p.restore()


class TileFlowWidget(QScrollArea):
    def __init__(self, parent_library, parent=None):
        super().__init__(parent)
        self.parent_library = parent_library
        self.config = parent_library.config

        self.setObjectName("libraryTileView")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.canvas = VirtualTileCanvas(self)
        self.setWidget(self.canvas)

    def clear(self):
        self.canvas.populate(None)

    def populate(self, tree_root_item):
        self.canvas.populate(tree_root_item)

        playing_path = None
        if (
            hasattr(self.parent_library, "delegate")
            and self.parent_library.delegate
        ):
            playing_path = getattr(
                self.parent_library.delegate, "playing_path", None
            )
        if (
            not playing_path
            and hasattr(self.parent_library, "current_playing_item")
            and self.parent_library.current_playing_item
        ):
            try:
                playing_path = self.parent_library.current_playing_item.data(
                    0, Qt.ItemDataRole.UserRole
                )
            except RuntimeError:
                pass
        is_paused = (
            self.parent_library.delegate.is_paused
            if (
                hasattr(self.parent_library, "delegate")
                and self.parent_library.delegate
            )
            else True
        )
        self.update_playback_state(playing_path, is_paused)

    def update_playback_state(self, playing_path, is_paused):
        self.canvas.update_playback_state(playing_path, is_paused)

    def update_selection_state(self, selected_paths):
        self.canvas.update_selection_state(selected_paths)

    def update_texts(self):
        self.canvas.update_texts()

    def refresh_tile(self, path):
        self.canvas.refresh_tile(path)

    def on_tile_play_clicked(self, path):
        self.parent_library.tree.play_button_clicked.emit(path)

    def on_tile_clicked(self, path):
        item = self.parent_library.find_item_by_path(
            self.parent_library.tree.invisibleRootItem(), path
        )
        if item:
            if getattr(self.parent_library.tree, "mass_selection_mode", False):
                self.parent_library.tree.toggle_item_selection_state(item)
                self.canvas.update_selection_state(
                    self.parent_library.tree.selected_audiobook_paths
                )
                self.canvas.update()
            else:
                self.parent_library.tree.setCurrentItem(item)
                self.parent_library.audiobook_selected.emit(path)

    def on_tile_double_clicked(self, path):
        item = self.parent_library.find_item_by_path(
            self.parent_library.tree.invisibleRootItem(), path
        )
        if item:
            self.parent_library.on_item_double_clicked(item, 0)

    def on_tile_favorite_clicked(self, path):
        self.parent_library.on_tree_favorite_clicked(path)

    def on_tile_description_requested(self, path):
        self.parent_library.show_description_dialog(path)
