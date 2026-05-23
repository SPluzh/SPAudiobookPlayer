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
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap, QIcon, QPainterPath

from translations import tr, trf
from styles import StyleManager
from utils import load_icon, get_base_path




class HeatmapToolTip(QFrame):
    """Custom tooltip popup for HeatmapWidget showing detailed daily breakdown"""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("heatmapTooltip")
        
        # UI Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(6)
        
        # Header: Date & Total time
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(15)
        
        self.date_label = QLabel(self)
        self.date_label.setObjectName("tooltipDate")
        
        self.total_label = QLabel(self)
        self.total_label.setObjectName("tooltipTotal")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.header_layout.addWidget(self.date_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.total_label)
        self.main_layout.addLayout(self.header_layout)
        
        # Separator line
        self.separator = QFrame(self)
        self.separator.setObjectName("tooltipSeparator")
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Plain)
        self.main_layout.addWidget(self.separator)
        
        # Track active row widgets directly in main_layout to avoid nested layout caching lag
        self.book_row_widgets = []
        
    def _format_duration(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}{tr('statistics.hours')}")
        if minutes > 0 or hours > 0:
            parts.append(f"{minutes}{tr('statistics.minutes')}")
        if hours == 0 and minutes == 0:
            parts.append(f"{secs}{tr('statistics.seconds')}")
            
        return " ".join(parts)

    def update_content(self, date_str: str, total_seconds: float, daily_books: list):
        """Update tooltip content with date, total time, and per-book list"""
        # Format Date
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            month_names = {
                1: tr("statistics.jan"), 2: tr("statistics.feb"), 3: tr("statistics.mar"),
                4: tr("statistics.apr"), 5: tr("statistics.may"), 6: tr("statistics.jun"),
                7: tr("statistics.jul"), 8: tr("statistics.aug"), 9: tr("statistics.sep"),
                10: tr("statistics.oct"), 11: tr("statistics.nov"), 12: tr("statistics.dec")
            }
            month_str = month_names.get(date_obj.month, "")
            formatted_date = f"{date_obj.day} {month_str} {date_obj.year}"
        except Exception:
            formatted_date = date_str
            
        self.date_label.setText(formatted_date)
        
        # Format Total Time
        total_time_str = self._format_duration(total_seconds)
        self.total_label.setText(total_time_str)
        
        # Clear previous books list instantly to ensure synchronous size recalculation
        for widget in self.book_row_widgets:
            self.main_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self.book_row_widgets.clear()
                 
        # Add new books list
        if not daily_books or total_seconds == 0:
            no_act_label = QLabel(tr("statistics.no_data"), self)
            no_act_label.setObjectName("tooltipBookTitle")
            self.main_layout.addWidget(no_act_label)
            self.book_row_widgets.append(no_act_label)
        else:
            for book in daily_books:
                book_row = QWidget(self)
                book_row.setObjectName("tooltipBookRow")
                row_lay = QHBoxLayout(book_row)
                row_lay.setContentsMargins(0, 0, 0, 0)
                row_lay.setSpacing(15)
                
                # Book name (Author — Title)
                author = book.get('author')
                title = book.get('title')
                if author and title:
                    display_name = f"{author} — {title}"
                elif title:
                    display_name = title
                elif author:
                    display_name = f"{author} — {book.get('audiobook_name', tr('delegate.no_title'))}"
                else:
                    display_name = book.get('audiobook_name') or tr('delegate.no_title')
                
                # Limit length of book title so it doesn't span too wide
                if len(display_name) > 35:
                    display_name = display_name[:32] + "..."
                    
                title_lbl = QLabel(display_name, book_row)
                title_lbl.setObjectName("tooltipBookTitle")
                
                # Duration for this book
                book_seconds = book.get('total_seconds', 0.0)
                time_lbl = QLabel(self._format_duration(book_seconds), book_row)
                time_lbl.setObjectName("tooltipBookTime")
                time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                row_lay.addWidget(title_lbl)
                row_lay.addStretch()
                row_lay.addWidget(time_lbl)
                
                self.main_layout.addWidget(book_row)
                self.book_row_widgets.append(book_row)
                
        # Shrink to 0x0 first to force Qt to contract the window to its new minimumSizeHint
        self.resize(0, 0)
        self.adjustSize()


class HeatmapWidget(QWidget):
    """GitHub-style heatmap widget showing daily listening activity"""
    
    def __init__(self, heatmap_data: Dict[str, float], db_manager=None, parent=None):
        """Initialize heatmap widget
        
        Args:
            heatmap_data: Dictionary mapping date strings to seconds listened
            db_manager: DatabaseManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.heatmap_data = heatmap_data
        self.db = db_manager
        self.db_cache = {}
        self.cell_size = 12
        self.cell_spacing = 2
        self.margin_left = 30
        self.margin_top = 15
        self.margin_bottom = 10
        
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
            _, theme_accent = StyleManager.get_theme_property("delegate_accent")
            if not theme_accent or not isinstance(theme_accent, QColor):
                theme_accent = QColor("#018574")  # Fallback
        except:
            theme_accent = QColor("#018574")
        
        if seconds < 0:
            # Future date - transparent
            return QColor(0, 0, 0, 0)
            
        if seconds == 0:
            # No activity - background matching grid
            return QColor(45, 45, 45) # Subtle contrast
        
        # Calculate intensity (0.0 - 1.0)
        intensity = seconds / self.max_seconds if self.max_seconds > 0 else 0
        
        # Map intensity to 5 discrete levels for better visual distinction
        color = QColor(theme_accent)
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
            
        # Get label color from theme
        try:
            _, label_color = StyleManager.get_theme_property("delegate_title")
        except:
            label_color = QColor(204, 204, 204)
        
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
        painter.setPen(label_color)
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        
        day_labels = [tr("statistics.mon"), "", tr("statistics.wed"), "", tr("statistics.fri"), "", tr("statistics.sun")]
        for row, label in enumerate(day_labels):
            if label:
                y = self.margin_top + row * (self.cell_size + self.cell_spacing) + self.cell_size // 2 + 3
                painter.drawText(5, y, label)
        
        # Draw month labels
        self._draw_month_labels(painter, label_color)
        
        # Draw legend
        self._draw_legend(painter, label_color)
    
    def _draw_month_labels(self, painter: QPainter, label_color: QColor):
        """Draw month labels above the heatmap with year indicator"""
        if not self.grid_data or not self.grid_data[0]:
            return
        
        painter.setPen(label_color)
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
                # Skip drawing the current month of last year on the far left to avoid duplication
                today = datetime.now().date()
                if col == 0 and month_found == today.month:
                    continue
                # Add year to the label (e.g., "Янв 24")
                label = f"{month_names.get(current_month, '')} {str(year_found)[2:]}"
                
                x = self.margin_left + col * (self.cell_size + self.cell_spacing)
                
                # Prevent the last label from going off-screen
                if col > num_cols - 4:
                    x -= 20
                
                y = self.margin_top - 5
                painter.drawText(x, y, label)
    
    def _draw_legend(self, painter: QPainter, label_color: QColor):
        """Draw color legend at the bottom"""
        painter.setPen(label_color)
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
        
        # Calculate row and col in grid using division to avoid dead zones in cell spacing
        col = (pos.x() - self.margin_left) // (self.cell_size + self.cell_spacing)
        row = (pos.y() - self.margin_top) // (self.cell_size + self.cell_spacing)
        
        num_weeks = len(self.grid_data[0]) if self.grid_data else 52
        if 0 <= row < 7 and 0 <= col < num_weeks:
            cell_data = self.grid_data[row][col]
            if cell_data:
                date_str, seconds = cell_data
                if self.hovered_cell != (row, col):
                    self.hovered_cell = (row, col)
                    self._show_tooltip(date_str, seconds)
                self.update()
                return
        
        if self.hovered_cell is not None:
            self.hovered_cell = None
            if hasattr(self, 'custom_tooltip') and self.custom_tooltip:
                self.custom_tooltip.hide()
            self.update()
            
    def leaveEvent(self, event):
        """Hide custom tooltip when mouse leaves the widget"""
        # Double check if mouse is really outside the widget boundaries
        # This prevents false leaveEvents triggered by OS window mapping
        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        if self.rect().contains(cursor_pos):
            return
            
        if self.hovered_cell is not None:
            self.hovered_cell = None
            if hasattr(self, 'custom_tooltip') and self.custom_tooltip:
                self.custom_tooltip.hide()
            self.update()
            
    def _show_tooltip(self, date_str: str, seconds: float):
        """Show custom floating tooltip for a cell"""
        if seconds < 0:
            if hasattr(self, 'custom_tooltip') and self.custom_tooltip:
                self.custom_tooltip.hide()
            return
            
        # Get books breakdown
        if seconds == 0:
            daily_books = []
        else:
            if date_str not in self.db_cache:
                if self.db:
                    daily_books = self.db.get_daily_stats(start_date=date_str, end_date=date_str)
                    # Sort books by listen time descending
                    daily_books.sort(key=lambda x: x.get('total_seconds', 0.0), reverse=True)
                else:
                    daily_books = []
                self.db_cache[date_str] = daily_books
            else:
                daily_books = self.db_cache[date_str]
                
        # Initialize tooltip if not already done
        if not hasattr(self, 'custom_tooltip') or not self.custom_tooltip:
            self.custom_tooltip = HeatmapToolTip(self.window())
            
        self.custom_tooltip.update_content(date_str, seconds, daily_books)
        self.custom_tooltip.resize(0, 0)
        self.custom_tooltip.layout().activate()
        self.custom_tooltip.adjustSize()
        
        # Position the tooltip
        row, col = self.hovered_cell
        cell_x = self.margin_left + col * (self.cell_size + self.cell_spacing)
        cell_y = self.margin_top + row * (self.cell_size + self.cell_spacing)
        
        # Convert local coordinate to global coordinate
        global_pos = self.mapToGlobal(QPoint(cell_x, cell_y))
        
        tooltip_width = self.custom_tooltip.width()
        tooltip_height = self.custom_tooltip.height()
        
        # Default: position above and to the right of the cell to avoid obscuring the cursor
        tooltip_x = global_pos.x() + self.cell_size + 10
        tooltip_y = global_pos.y() - tooltip_height - 10
        
        # Screen boundary checks
        screen = self.screen()
        if screen:
            screen_geom = screen.availableGeometry()
            
            # If goes off the right edge, position to the left of the cell instead
            if tooltip_x + tooltip_width > screen_geom.right():
                tooltip_x = global_pos.x() - tooltip_width - 10
                
            # Keep within horizontal screen bounds
            tooltip_x = max(screen_geom.left(), min(tooltip_x, screen_geom.right() - tooltip_width))
            
            # If goes off the top edge, position below the cell instead
            if tooltip_y < screen_geom.top():
                tooltip_y = global_pos.y() + self.cell_size + 10
                
            # Keep within vertical screen bounds
            tooltip_y = max(screen_geom.top(), min(tooltip_y, screen_geom.bottom() - tooltip_height))
                
        self.custom_tooltip.move(tooltip_x, tooltip_y)
        self.custom_tooltip.show()


class CoverWithProgress(QWidget):
    """Custom cover widget that renders a cover image and a progress bar below it"""
    def __init__(self, progress_percent: int = 0, parent=None):
        super().__init__(parent)
        self.progress_percent = progress_percent
        self.setFixedSize(55, 62)  # 55px width, 62px height (55 cover + 3 gap + 4 pb)
        self._pixmap = None
        
    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 1. Draw Cover Image (top 55x55)
        cover_rect = QRectF(0, 0, 55, 55)
        path = QPainterPath()
        path.addRoundedRect(cover_rect, 3.0, 3.0)
        
        painter.save()
        painter.setClipPath(path)
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(QRect(0, 0, 55, 55), self._pixmap)
        painter.restore()
        
        # 2. Draw Progress Bar below cover (Y starts at 58, height is 4)
        pb_rect = QRectF(0, 58, 55, 4)
        
        # Background
        _, bg_color = StyleManager.get_theme_property("overlay_progress_bg")
        painter.fillRect(pb_rect, bg_color)
        
        # Fill
        fill_w = pb_rect.width() * min(100, max(0, self.progress_percent)) / 100.0
        if fill_w > 0:
            fill_rect = QRectF(pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height())
            _, primary_color = StyleManager.get_theme_property("delegate_accent")
            painter.fillRect(fill_rect, primary_color)


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
        layout.setSpacing(8)
        
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
        heatmap_widget = HeatmapWidget(self.heatmap_data, self.db, self)
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
            header.setContentsMargins(0, 5, 0, 5)
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
        row.setFixedHeight(85)
        
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 5, 20, 5)
        row_layout.setSpacing(15)
        
        # Cover
        progress_val = book.get('progress_percent') or 0
        cover_label = CoverWithProgress(progress_percent=progress_val)
        
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
        
        # Timeline status (Started / Completed)
        timeline_parts = []
        
        if book.get('time_started'):
            ts = book['time_started']
            started_date = ""
            try:
                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                started_date = dt.strftime('%d.%m.%Y')
            except ValueError:
                try:
                    dt = datetime.strptime(ts.split()[0], '%Y-%m-%d')
                    started_date = dt.strftime('%d.%m.%Y')
                except:
                    started_date = str(ts)
            if started_date:
                timeline_parts.append(trf("statistics.started_on", date=started_date))
                
        if book.get('is_completed') and book.get('time_finished'):
            tf = book['time_finished']
            completed_date = ""
            try:
                dt = datetime.strptime(tf, '%Y-%m-%d %H:%M:%S')
                completed_date = dt.strftime('%d.%m.%Y')
            except ValueError:
                try:
                    dt = datetime.strptime(tf.split()[0], '%Y-%m-%d')
                    completed_date = dt.strftime('%d.%m.%Y')
                except:
                    completed_date = str(tf)
            if completed_date:
                timeline_parts.append(trf("statistics.completed_on", date=completed_date))
                
        if timeline_parts:
            completed_text = "  •  ".join(timeline_parts)
            completed_label = QLabel(completed_text)
            completed_label.setObjectName("completedLabel")
            text_layout.addWidget(completed_label)
            
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
        card_layout.setContentsMargins(15, 5, 15, 5)
        card_layout.setSpacing(2)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("statLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_widget = QLabel(value)
        value_widget.setObjectName("statValue")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        
        return card
