"""
Statistics Dialog Module
Displays listening statistics with GitHub-style heatmap visualization.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QWidget, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

from translations import tr, trf
from styles import StyleManager


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
        weeks = len(self.grid_data[0]) if self.grid_data else 53
        width = self.margin_left + weeks * (self.cell_size + self.cell_spacing) + 20
        height = self.margin_top + 7 * (self.cell_size + self.cell_spacing) + self.margin_bottom + 20
        
        self.setMinimumSize(width, height)
        self.setMaximumHeight(height)
        
        # Tooltip
        self.setMouseTracking(True)
        self.hovered_cell = None
        
    def _prepare_grid_data(self) -> list:
        """Prepare 2D grid data for rendering (7 rows x N weeks)
        
        Returns:
            List of lists: grid[row][col] = (date_str, seconds)
        """
        if not self.heatmap_data:
            return [[None] * 53 for _ in range(7)]
        
        # Get date range
        dates = sorted(self.heatmap_data.keys())
        if not dates:
            return [[None] * 53 for _ in range(7)]
        
        start_date = datetime.strptime(dates[0], '%Y-%m-%d').date()
        end_date = datetime.strptime(dates[-1], '%Y-%m-%d').date()
        
        # Find the Monday before start_date
        days_since_monday = start_date.weekday()
        grid_start = start_date - timedelta(days=days_since_monday)
        
        # Calculate number of weeks needed
        total_days = (end_date - grid_start).days + 1
        num_weeks = (total_days + 6) // 7
        
        # Initialize grid
        grid = [[None] * num_weeks for _ in range(7)]
        
        # Fill grid
        current_date = grid_start
        for week in range(num_weeks):
            for day in range(7):
                date_str = current_date.strftime('%Y-%m-%d')
                seconds = self.heatmap_data.get(date_str, 0.0)
                grid[day][week] = (date_str, seconds)
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
                theme_accent = "#39d353"  # Default green
        except:
            theme_accent = "#39d353"
        
        if seconds == 0:
            # No activity - dark background
            return QColor("#1a1f1e")
        
        # Calculate intensity (0.0 - 1.0)
        intensity = seconds / self.max_seconds if self.max_seconds > 0 else 0
        
        # Parse theme accent color
        base_color = QColor(theme_accent)
        
        # Create gradient levels (darker to brighter)
        if intensity <= 0.25:
            # Level 1 - 25% brightness
            factor = 0.25
        elif intensity <= 0.50:
            # Level 2 - 50% brightness
            factor = 0.50
        elif intensity <= 0.75:
            # Level 3 - 75% brightness
            factor = 0.75
        else:
            # Level 4 - 100% brightness (brightest)
            factor = 1.0
        
        # Apply brightness factor
        r = int(base_color.red() * factor)
        g = int(base_color.green() * factor)
        b = int(base_color.blue() * factor)
        
        return QColor(r, g, b)
    
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
        
        day_labels = [tr("statistics.mon"), "", tr("statistics.wed"), "", tr("statistics.fri"), "", ""]
        for row, label in enumerate(day_labels):
            if label:
                y = self.margin_top + row * (self.cell_size + self.cell_spacing) + self.cell_size // 2 + 3
                painter.drawText(5, y, label)
        
        # Draw month labels
        self._draw_month_labels(painter)
        
        # Draw legend
        self._draw_legend(painter)
    
    def _draw_month_labels(self, painter: QPainter):
        """Draw month labels above the heatmap"""
        if not self.grid_data or not self.grid_data[0]:
            return
        
        painter.setPen(QColor(150, 150, 150))
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        
        current_month = None
        month_names = {
            1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
            7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"
        }
        
        for col in range(len(self.grid_data[0])):
            cell_data = self.grid_data[0][col]
            if cell_data is None:
                continue
            
            date_str, _ = cell_data
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month = date_obj.month
            
            if month != current_month:
                current_month = month
                x = self.margin_left + col * (self.cell_size + self.cell_spacing)
                y = self.margin_top - 5
                painter.drawText(x, y, month_names.get(month, ""))
    
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
        
        # Color boxes
        for level in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
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
        
        # Load data
        self.heatmap_data = self.db.get_heatmap_data(365)
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
                'this_week_seconds': 0,
                'current_streak': 0,
                'longest_streak': 0,
                'average_daily': 0
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
        
        # Calculate streaks
        current_streak = self._calculate_current_streak()
        longest_streak = self._calculate_longest_streak()
        
        # Average daily (over 365 days)
        average_daily = total_seconds / 365 if total_seconds > 0 else 0
        
        return {
            'total_seconds': total_seconds,
            'this_year_seconds': this_year_seconds,
            'this_month_seconds': this_month_seconds,
            'this_week_seconds': this_week_seconds,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'average_daily': average_daily
        }
    
    def _calculate_current_streak(self) -> int:
        """Calculate current consecutive days streak"""
        if not self.heatmap_data:
            return 0
        
        today = datetime.now().date()
        streak = 0
        
        # Check backwards from today
        current_date = today
        while True:
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str in self.heatmap_data and self.heatmap_data[date_str] > 0:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    def _calculate_longest_streak(self) -> int:
        """Calculate longest consecutive days streak"""
        if not self.heatmap_data:
            return 0
        
        dates = sorted(self.heatmap_data.keys())
        longest = 0
        current = 0
        prev_date = None
        
        for date_str in dates:
            if self.heatmap_data[date_str] > 0:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if prev_date is None or (date_obj - prev_date).days == 1:
                    current += 1
                    longest = max(longest, current)
                else:
                    current = 1
                
                prev_date = date_obj
            else:
                current = 0
                prev_date = None
        
        return longest
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds to human-readable string
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted string like "2ч 30м"
        """
        if seconds == 0:
            return "0" + tr("statistics.minutes")
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}{tr('statistics.hours')}")
        if minutes > 0:
            parts.append(f"{minutes}{tr('statistics.minutes')}")
        
        return " ".join(parts) if parts else "0" + tr("statistics.minutes")
    
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
        
        # Row 2
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.current_streak"),
            f"{self.statistics['current_streak']} {tr('statistics.days')}"
        ), 1, 0)
        
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.longest_streak"),
            f"{self.statistics['longest_streak']} {tr('statistics.days')}"
        ), 1, 1)
        
        stats_layout.addWidget(self._create_stat_card(
            tr("statistics.average_daily"),
            self._format_time(self.statistics['average_daily'])
        ), 1, 2)
        
        layout.addLayout(stats_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Heatmap
        heatmap_widget = HeatmapWidget(self.heatmap_data, self)
        layout.addWidget(heatmap_widget)
        
        layout.addStretch()
    
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
        card.setFrameShape(QFrame.Shape.StyledPanel)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("statLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_widget = QLabel(value)
        value_widget.setObjectName("statValue")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        
        return card
