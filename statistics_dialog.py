"""
Statistics Dialog Module
Displays listening statistics with GitHub-style heatmap visualization.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QWidget, QGridLayout, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap, QIcon

from translations import tr, trf
from styles import StyleManager
from utils import load_icon, get_base_path


class HeatmapWidget(QWidget):
    """GitHub-style heatmap widget showing daily listening activity"""
    
    def __init__(self, heatmap_data: Dict[str, float], parent=None):
        """Initialize heatmap widget
        
        Args:
            heatmap_data: Dictionary mapping date strings to seconds listened
            parent: Parent widget
        """
        super().__init__(parent)
        self.heatmap_data = heatmap_data
        self.cell_size = 12
        self.cell_spacing = 2
        self.margin_left = 30
        self.margin_top = 20
        self.margin_bottom = 20
        
        # Calculate max value for color intensity
        self.max_seconds = max(heatmap_data.values()) if heatmap_data else 0
        
        # Prepare grid data (7 rows x 53 weeks)
        self.grid_data = self._prepare_grid_data()
        
        # Calculate widget size
        weeks = len(self.grid_data[0]) if self.grid_data else 52
        width = self.margin_left + weeks * (self.cell_size + self.cell_spacing) + 40
        height = self.margin_top + 7 * (self.cell_size + self.cell_spacing) + self.margin_bottom + 20
        
        self.setMinimumSize(width, height)
        self.setMaximumHeight(height)
        
        # Tooltip
        self.setMouseTracking(True)
        self.hovered_cell = None
        
    def _prepare_grid_data(self) -> list:
        """Prepare 2D grid data for rendering (7 rows x 53 weeks).
        Always ends on the current week's Sunday to provide a consistent view.
        """
        # End on the Sunday of the current week
        today = datetime.now().date()
        days_to_sunday = 6 - today.weekday()
        grid_end = today + timedelta(days=days_to_sunday)
        
        # Show exactly 52 weeks (364 days) to avoid month duplication at edges
        num_weeks = 52
        grid_start = grid_end - timedelta(weeks=num_weeks) + timedelta(days=1)
        
        # Initialize grid
        grid = [[None] * num_weeks for _ in range(7)]
        
        # Fill grid
        current_date = grid_start
        for week in range(num_weeks):
            for day in range(7):
                date_str = current_date.strftime('%Y-%m-%d')
                
                if current_date <= today:
                    seconds = self.heatmap_data.get(date_str, 0.0)
                    grid[day][week] = (date_str, seconds)
                else:
                    # Future dates in the current week (remain empty)
                    grid[day][week] = (date_str, -1.0)
                    
                current_date += timedelta(days=1)
        
        return grid
    
    def _get_cell_color(self, seconds: float) -> QColor:
        """Calculate cell color based on listening time
        
        Args:
            seconds: Seconds listened on this day
            
        Returns:
            QColor for the cell
        """
        # Get theme colors
        try:
            theme_accent = StyleManager.get_theme_property("accent_color")
            # StyleManager returns a tuple, extract the color string
            if isinstance(theme_accent, tuple) and len(theme_accent) > 0:
                theme_accent = theme_accent[0]
            if not theme_accent or not isinstance(theme_accent, str):
                theme_accent = "#018574"  # Use app's teal accent
        except:
            theme_accent = "#018574"
        
        if seconds < 0:
            # Future date - transparent
            return QColor(0, 0, 0, 0)
            
        if seconds == 0:
            # No activity - background matching grid
            return QColor("#2c2c2c")
        
        # Calculate intensity (0.0 - 1.0)
        intensity = seconds / self.max_seconds if self.max_seconds > 0 else 0
        
        # Parse theme accent color
        base_color = QColor(theme_accent)
        
        # Map intensity to 4 discrete alpha levels for better visual distinction
        color = QColor(theme_accent)
        # Map intensity to 5 discrete levels for better visual distinction
        if intensity <= 0.2:
            alpha = 60
        elif intensity <= 0.4:
            alpha = 110
        elif intensity <= 0.6:
            alpha = 160
        elif intensity <= 0.8:
            alpha = 210
        else:
            # Level 5: Top 20% - Radical brightness jump
            color = color.lighter(120)
            alpha = 255
            
        color.setAlpha(alpha)
        return color
    
    def paintEvent(self, event):
        """Paint the heatmap grid"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.grid_data:
            return
        
        # Draw cells
        for row in range(7):
            for col in range(len(self.grid_data[row])):
                cell_data = self.grid_data[row][col]
                if cell_data is None:
                    continue
                
                date_str, seconds = cell_data
                
                # Calculate cell position
                x = self.margin_left + col * (self.cell_size + self.cell_spacing)
                y = self.margin_top + row * (self.cell_size + self.cell_spacing)
                
                # Get cell color
                color = self._get_cell_color(seconds)
                
                # Draw cell
                painter.fillRect(x, y, self.cell_size, self.cell_size, color)
                
                # Draw border for hovered cell
                if self.hovered_cell == (row, col):
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(x, y, self.cell_size, self.cell_size)
        
        # Draw day labels (Mon, Wed, Fri)
        painter.setPen(QColor(150, 150, 150))
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        
        day_labels = [tr("statistics.mon"), "", tr("statistics.wed"), "", tr("statistics.fri"), "", tr("statistics.sun")]
        for row, label in enumerate(day_labels):
            if label:
                y = self.margin_top + row * (self.cell_size + self.cell_spacing) + self.cell_size // 2 + 3
                painter.drawText(5, y, label)
        
        # Draw month labels
        self._draw_month_labels(painter)
        
        # Draw legend
        self._draw_legend(painter)
    
    def _draw_month_labels(self, painter: QPainter):
        """Draw month labels above the heatmap with year indicator"""
        if not self.grid_data or not self.grid_data[0]:
            return
        
        painter.setPen(QColor(150, 150, 150))
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        
        current_month = None
        month_names = {
            1: tr("statistics.jan_short"), 2: tr("statistics.feb_short"), 3: tr("statistics.mar_short"),
            4: tr("statistics.apr_short"), 5: tr("statistics.may_short"), 6: tr("statistics.jun_short"),
            7: tr("statistics.jul_short"), 8: tr("statistics.aug_short"), 9: tr("statistics.sep_short"),
            10: tr("statistics.oct_short"), 11: tr("statistics.nov_short"), 12: tr("statistics.dec_short")
        }
        
        num_cols = len(self.grid_data[0])
        for col in range(num_cols):
            # Check any day of the week to see if a new month starts here
            month_found = None
            year_found = None
            for row in range(7):
                cell_data = self.grid_data[row][col]
                if cell_data:
                    date_obj = datetime.strptime(cell_data[0], '%Y-%m-%d')
                    if date_obj.month != current_month:
                        month_found = date_obj.month
                        year_found = date_obj.year
                        break
            
            if month_found is not None:
                current_month = month_found
                # Add year to the label (e.g., "Янв 24")
                label = f"{month_names.get(current_month, '')} {str(year_found)[2:]}"
                
                x = self.margin_left + col * (self.cell_size + self.cell_spacing)
                
                # Prevent the last label from going off-screen
                if col > num_cols - 4:
                    x -= 20
                
                y = self.margin_top - 5
                painter.drawText(x, y, label)
    
    def _draw_legend(self, painter: QPainter):
        """Draw color legend at the bottom"""
        painter.setPen(QColor(150, 150, 150))
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        
        legend_y = self.margin_top + 7 * (self.cell_size + self.cell_spacing) + 10
        legend_x = self.margin_left
        
        # "Less" label
        painter.drawText(legend_x, legend_y + 10, tr("statistics.less"))
        legend_x += 40
        
        # Color boxes (0, L1, L2, L3, L4, L5)
        for level in [0, 0.1, 0.3, 0.5, 0.7, 0.9]:
            seconds = level * self.max_seconds
            color = self._get_cell_color(seconds)
            painter.fillRect(legend_x, legend_y, self.cell_size, self.cell_size, color)
            legend_x += self.cell_size + self.cell_spacing
        
        # "More" label
        legend_x += 5
        painter.drawText(legend_x, legend_y + 10, tr("statistics.more"))
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for tooltip"""
        pos = event.pos()
        
        # Find cell under mouse
        for row in range(7):
            for col in range(len(self.grid_data[row])):
                x = self.margin_left + col * (self.cell_size + self.cell_spacing)
                y = self.margin_top + row * (self.cell_size + self.cell_spacing)
                
                if x <= pos.x() <= x + self.cell_size and y <= pos.y() <= y + self.cell_size:
                    self.hovered_cell = (row, col)
                    cell_data = self.grid_data[row][col]
                    if cell_data:
                        date_str, seconds = cell_data
                        self._show_tooltip(date_str, seconds)
                    self.update()
                    return
        
        self.hovered_cell = None
        self.setToolTip("")
        self.update()
    
    def _show_tooltip(self, date_str: str, seconds: float):
        """Show tooltip for a cell"""
        if seconds < 0:
            self.setToolTip("")
            return
            
        # Format time
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if hours > 0:
            time_str = f"{hours}{tr('statistics.hours')} {minutes}{tr('statistics.minutes')}"
        elif minutes > 0:
            time_str = f"{minutes}{tr('statistics.minutes')}"
        else:
            time_str = tr("statistics.no_data")
        
        tooltip = trf("statistics.tooltip", date=date_str, time=time_str)
        self.setToolTip(tooltip)


class StatisticsDialog(QDialog):
    """Dialog displaying listening statistics with heatmap"""
    
    def __init__(self, parent, db_manager):
        """Initialize statistics dialog
        
        Args:
            parent: Parent widget
            db_manager: DatabaseManager instance
        """
        super().__init__(parent)
        self.db = db_manager
        
        self.setWindowTitle(tr("statistics.title"))
        self.setMinimumSize(900, 600)
        
        # Load data (52 weeks = 364 days)
        self.heatmap_data = self.db.get_heatmap_data(364)
        self.book_stats = self.db.get_book_stats_by_month()
        self.statistics = self._calculate_statistics()
        
        # Setup UI
        self._setup_ui()
    
    def _calculate_statistics(self) -> Dict:
        """Calculate summary statistics from heatmap data
        
        Returns:
            Dictionary with calculated statistics
        """
        if not self.heatmap_data:
            return {
                'total_seconds': 0,
                'this_year_seconds': 0,
                'this_month_seconds': 0,
                'this_week_seconds': 0
            }
        
        total_seconds = sum(self.heatmap_data.values())
        
        # Calculate date ranges
        today = datetime.now().date()
        year_start = datetime(today.year, 1, 1).date()
        month_start = datetime(today.year, today.month, 1).date()
        week_start = today - timedelta(days=6)
        
        this_year_seconds = 0
        this_month_seconds = 0
        this_week_seconds = 0
        
        for date_str, seconds in self.heatmap_data.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if date_obj >= year_start:
                this_year_seconds += seconds
            
            if date_obj >= month_start:
                this_month_seconds += seconds
            
            if date_obj >= week_start:
                this_week_seconds += seconds
        return {
            'total_seconds': total_seconds,
            'this_year_seconds': this_year_seconds,
            'this_month_seconds': this_month_seconds,
            'this_week_seconds': this_week_seconds
        }
    

    def _format_time(self, seconds: float) -> str:
        """Format seconds to human-readable string"""
        if seconds <= 0:
            return "0" + tr("statistics.seconds")
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}{tr('statistics.hours')}")
        if minutes > 0:
            parts.append(f"{minutes}{tr('statistics.minutes')}")
        
        # Show seconds if it's the only unit or if there's remaining seconds
        if secs > 0 or not parts:
            parts.append(f"{secs}{tr('statistics.seconds')}")
            
        return " ".join(parts)
    
    def _setup_ui(self):
        """Setup dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Statistics cards
        stats_layout = QGridLayout()
        stats_layout.setSpacing(10)
        
        # Row 1
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.total_time"),
            self._format_time(self.statistics['total_seconds'])
        ), 0, 0)
        
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.this_year"),
            self._format_time(self.statistics['this_year_seconds'])
        ), 0, 1)
        
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.this_month"),
            self._format_time(self.statistics['this_month_seconds'])
        ), 0, 2)
        
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.this_week"),
            self._format_time(self.statistics['this_week_seconds'])
        ), 0, 3)
        
        layout.addLayout(stats_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Heatmap
        heatmap_widget = HeatmapWidget(self.heatmap_data, self)
        layout.addWidget(heatmap_widget)
        
        # Separator for history
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator2)
        
        # History list
        self._setup_history_list(layout)
        
        # Set minimum size for better scroll area visibility
        self.setMinimumSize(850, 750)

    def _setup_history_list(self, main_layout):
        """Setup the scrollable list of books by month"""
        if not self.book_stats:
            main_layout.addStretch()
            return
            
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        history_layout = QVBoxLayout(container)
        history_layout.setContentsMargins(0, 0, 10, 0)
        history_layout.setSpacing(8)
        
        # Month names for translation
        month_names = {
            "01": tr("statistics.jan"), "02": tr("statistics.feb"), "03": tr("statistics.mar"),
            "04": tr("statistics.apr"), "05": tr("statistics.may"), "06": tr("statistics.jun"),
            "07": tr("statistics.jul"), "08": tr("statistics.aug"), "09": tr("statistics.sep"),
            "10": tr("statistics.oct"), "11": tr("statistics.nov"), "12": tr("statistics.dec")
        }
        
        for month_str in sorted(self.book_stats.keys(), reverse=True):
            year, month = month_str.split("-")
            month_name = month_names.get(month, month)
            header_text = f"{month_name} {year}".upper()
            
            header = QLabel(header_text)
            header.setObjectName("sectionLabel")
            header.setContentsMargins(0, 10, 0, 5)
            history_layout.addWidget(header)
            
            for book in self.book_stats[month_str]:
                row = self._create_book_row(book)
                history_layout.addWidget(row)
        
        history_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def _create_book_row(self, book: dict) -> QWidget:
        """Create a single book row widget similar to library items"""
        row = QFrame()
        row.setObjectName("statCard")
        row.setFixedHeight(75)
        
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 5, 20, 5)
        row_layout.setSpacing(15)
        
        # Cover
        cover_label = QLabel()
        cover_label.setFixedSize(55, 55)
        cover_label.setScaledContents(True)
        
        cover_path = book.get('cached_cover_path') or book.get('cover_path')
        icon = None
        if cover_path:
            p = Path(cover_path)
            # Try absolute or relative to script dir
            if not p.is_absolute():
                p = get_base_path() / p
            icon = load_icon(p, 55, force_square=True)
            
        if icon:
            cover_label.setPixmap(icon.pixmap(55, 55))
        else:
            # Fallback to default cover if possible
            default_path = get_base_path() / "resources" / "icons" / "default_cover.png"
            default_icon = load_icon(default_path, 55, force_square=True)
            if default_icon:
                cover_label.setPixmap(default_icon.pixmap(55, 55))
            
        row_layout.addWidget(cover_label)
        
        # Text block
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title_label = QLabel(book['title'] or tr("delegate.no_title"))
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        
        author_label = QLabel(book['author'] or tr("scanner.unknown_author"))
        author_label.setObjectName("subtitleLabel")
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(author_label)
        row_layout.addLayout(text_layout, 1)
        
        # Time
        time_label = QLabel(self._format_time(book['seconds']))
        time_label.setObjectName("bigTimeLabel")
        row_layout.addWidget(time_label)
        
        return row
    
    def _create_stat_card(self, label: str, value: str) -> QWidget:
        """Create a statistics card widget
        
        Args:
            label: Card label
            value: Card value
            
        Returns:
            QWidget containing the card
        """
        card = QFrame()
        card.setObjectName("statCard")
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(5)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("statLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_widget = QLabel(value)
        value_widget.setObjectName("statValue")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        
        return card
