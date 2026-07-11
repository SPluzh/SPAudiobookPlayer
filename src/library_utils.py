"""Utility functions and constants for the library module.

This module contains shared layout, painting utilities, and constants
that are used across list-based and tile-based library views.
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
from styles import StyleManager
from translations import tr

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


def get_placeholder_folder_rect(rect: QRectF) -> QRectF:
    """Calculate the folder icon rect within the given bounds.

    Args:
        rect: The bounding rectangle of the empty library area.

    Returns:
        QRectF: The calculated bounding box of the folder icon.
    """
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


def draw_library_placeholder(painter: QPainter, rect: QRectF) -> None:
    """Draw a beautiful placeholder when the library is empty.

    Args:
        painter: The active QPainter object.
        rect: The bounding rectangle of the widget.
    """
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
