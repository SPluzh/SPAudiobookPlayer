from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QLineEdit, QWidget, QGridLayout, QFrame, QCheckBox, QGroupBox, QScrollArea, QListWidget, QListWidgetItem, QAbstractItemView
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QRegularExpression, QTimer
from PyQt6.QtGui import QColor, QRegularExpressionValidator, QPainter, QImage, QMouseEvent, QPen
from translations import tr
from utils import get_icon

class SVPicker(QWidget):
    """2D Saturation-Value picker area"""
    colorChanged = pyqtSignal(int, int)  # Emits (saturation, value) where both are 0-255
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 150)
        self.hue = 0      # 0-359
        self.sat = 255    # 0-255
        self.val = 255    # 0-255
        self._image = None
        self._need_update_image = True
        
    def set_hue(self, hue: int):
        if self.hue != hue:
            self.hue = hue
            self._need_update_image = True
            self.update()
            
    def set_sv(self, sat: int, val: int):
        self.sat = sat
        self.val = val
        self.update()
        
    def _generate_image(self):
        w, h = self.width(), self.height()
        img = QImage(w, h, QImage.Format.Format_RGB32)
        for y in range(h):
            # Value goes from 255 (top) to 0 (bottom)
            v = 255 - int(y * 255 / (h - 1))
            for x in range(w):
                # Saturation goes from 0 (left) to 255 (right)
                s = int(x * 255 / (w - 1))
                color = QColor.fromHsv(self.hue, s, v)
                img.setPixelColor(x, y, color)
        self._image = img
        self._need_update_image = False
        
    def paintEvent(self, event):
        painter = QPainter(self)
        if self._need_update_image or self._image is None:
            self._generate_image()
        painter.drawImage(0, 0, self._image)
        
        # Draw beautiful target handle
        w, h = self.width(), self.height()
        px = int(self.sat * (w - 1) / 255)
        py = int((255 - self.val) * (h - 1) / 255)
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Outer black circle
        painter.setPen(QPen(QColor(0, 0, 0, 150), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(px - 6, py - 6, 12, 12)
        
        # Inner white circle
        painter.setPen(QPen(QColor(255, 255, 255, 255), 2))
        painter.drawEllipse(px - 5, py - 5, 10, 10)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.update_from_mouse(event.position().toPoint())
            
    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.update_from_mouse(event.position().toPoint())
            
    def update_from_mouse(self, pos: QPoint):
        w, h = self.width(), self.height()
        x = max(0, min(pos.x(), w - 1))
        y = max(0, min(pos.y(), h - 1))
        
        self.sat = int(x * 255 / (w - 1))
        self.val = 255 - int(y * 255 / (h - 1))
        self.update()
        self.colorChanged.emit(self.sat, self.val)


class HueSlider(QSlider):
    """Custom QSlider with rainbow hue background"""
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 359)
        self.setFixedHeight(12)
        self.setProperty("class", "hue-slider")


class ColorPickerDialog(QDialog):
    """Compact color picker dialog with 2D SV area and Hue slider"""
    colorChanged = pyqtSignal(QColor)
    
    def __init__(self, parent=None, initial_color=QColor(255, 0, 0)):
        super().__init__(parent)
        self.setWindowTitle(tr("appearance.picker_title", "Pick Color"))
        self.setFixedSize(200, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self.color = initial_color
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.picker = SVPicker()
        self.picker.set_hue(initial_color.hue())
        self.picker.set_sv(initial_color.saturation(), initial_color.value())
        layout.addWidget(self.picker)
        
        self.hue_slider = HueSlider()
        self.hue_slider.setValue(initial_color.hue())
        layout.addWidget(self.hue_slider)
        
        btn_layout = QHBoxLayout()
        
        # Swatch preview box
        self.preview_box = QLabel()
        self.preview_box.setProperty("class", "color-preview-box")
        self.preview_box.setFixedSize(36, 22)
        btn_layout.addWidget(self.preview_box)
        
        btn_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(60)
        ok_btn.setFixedHeight(22)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        # Connect signals
        self.picker.colorChanged.connect(self.on_sv_changed)
        self.hue_slider.valueChanged.connect(self.on_hue_changed)
        
        self.update_preview()
        
    def on_sv_changed(self, sat, val):
        self.color = QColor.fromHsv(self.hue_slider.value(), sat, val)
        self.update_preview()
        self.colorChanged.emit(self.color)
        
    def on_hue_changed(self, hue):
        self.picker.set_hue(hue)
        self.color = QColor.fromHsv(hue, self.picker.sat, self.picker.val)
        self.update_preview()
        self.colorChanged.emit(self.color)
        
    def update_preview(self):
        self.preview_box.setStyleSheet(f"background-color: {self.color.name()};")


class AppearanceDialog(QDialog):
    """Compact appearance settings dialog with custom color picker fields and Hex inputs for accent, window background, and secondary background"""
    
    # Signals
    accent_preview = pyqtSignal(str)       # Keeping for backward compatibility
    accent_saved = pyqtSignal(str)         # Keeping for backward compatibility
    appearance_preview = pyqtSignal(str, str, str, str, str, str, str, str, str, float) # Emits (accent, window, bg_dark, text, border, status_new, status_started, status_completed, icon_color, icon_thickness)
    appearance_saved = pyqtSignal(str, str, str, str, str, str, str, str, str, float)   # Emits (accent, window, bg_dark, text, border, status_new, status_started, status_completed, icon_color, icon_thickness)
    
    def __init__(self, parent=None, current_accent="", default_accent="", current_window="", default_window="", current_bg_dark="", default_bg_dark="", current_text="", default_text="", current_border="", default_border="",
                 current_status_new="", default_status_new="", current_status_started="", default_status_started="", current_status_completed="", default_status_completed="",
                 current_icon_color="", default_icon_color="#cccccc",
                 current_icon_thickness=2.0, default_icon_thickness=2.0,
                 show_detailed_info=True,
                 show_info_progress=True, show_info_file_count=True, show_info_duration=True, show_info_size=True,
                 show_info_technical=True, show_info_year_written=True, show_info_year_recorded=True, show_info_language=True,
                 show_visualizer=True, show_nesting_lines=True, show_status_triangle=True, show_statusbar=True,
                 remember_filter_folders=True,
                 info_order="progress,file_count,duration,size,technical,year_written,year_recorded,language",
                 default_info_order="progress,file_count,duration,size,technical,year_written,year_recorded,language"):
        """Initialize appearance settings dialog"""
        super().__init__(parent)
        self.setWindowTitle(tr("appearance.title"))
        self.setMinimumSize(720, 580)
        
        # Keep track of original, current, and default values
        self.original_accent = current_accent
        self.default_accent = default_accent
        self.current_accent = current_accent or default_accent
        
        self.original_window = current_window
        self.default_window = default_window
        self.current_window = current_window or default_window
        
        self.original_bg_dark = current_bg_dark
        self.default_bg_dark = default_bg_dark
        self.current_bg_dark = current_bg_dark or default_bg_dark
        
        self.original_text = current_text
        self.default_text = default_text
        self.current_text = current_text or default_text
        
        self.original_border = current_border
        self.default_border = default_border
        self.current_border = current_border or default_border

        self.original_status_new = current_status_new
        self.default_status_new = default_status_new
        self.current_status_new = current_status_new or default_status_new

        self.original_status_started = current_status_started
        self.default_status_started = default_status_started
        self.current_status_started = current_status_started or default_status_started

        self.original_status_completed = current_status_completed
        self.default_status_completed = default_status_completed
        self.current_status_completed = current_status_completed or default_status_completed

        self.original_icon_color = current_icon_color
        self.default_icon_color = default_icon_color
        self.current_icon_color = current_icon_color or default_icon_color

        self.original_icon_thickness = current_icon_thickness
        self.default_icon_thickness = default_icon_thickness
        self.current_icon_thickness = current_icon_thickness

        # Book info settings states
        self.original_show_detailed_info = show_detailed_info
        self.current_show_detailed_info = show_detailed_info

        self.original_show_info_progress = show_info_progress
        self.current_show_info_progress = show_info_progress
        
        self.original_show_info_file_count = show_info_file_count
        self.current_show_info_file_count = show_info_file_count
        
        self.original_show_info_duration = show_info_duration
        self.current_show_info_duration = show_info_duration
        
        self.original_show_info_size = show_info_size
        self.current_show_info_size = show_info_size
        
        self.original_show_info_technical = show_info_technical
        self.current_show_info_technical = show_info_technical
        
        self.original_show_info_year_written = show_info_year_written
        self.current_show_info_year_written = show_info_year_written
        
        self.original_show_info_year_recorded = show_info_year_recorded
        self.current_show_info_year_recorded = show_info_year_recorded
        
        self.original_show_info_language = show_info_language
        self.current_show_info_language = show_info_language

        self.original_info_order = info_order
        self.default_info_order = default_info_order
        self.current_info_order = info_order or default_info_order

        self.info_keys = ["progress", "file_count", "duration", "size", "technical", "year_written", "year_recorded", "language"]
        self.key_to_translation = {
            "progress": "appearance.info_progress",
            "file_count": "appearance.info_files",
            "duration": "appearance.info_duration",
            "size": "appearance.info_size",
            "technical": "appearance.info_technical",
            "year_written": "appearance.info_year_written",
            "year_recorded": "appearance.info_year_recorded",
            "language": "appearance.info_language",
        }

        # Interface options states
        self.original_show_visualizer = show_visualizer
        self.current_show_visualizer = show_visualizer
        
        self.original_show_nesting_lines = show_nesting_lines
        self.current_show_nesting_lines = show_nesting_lines
        
        self.original_show_status_triangle = show_status_triangle
        self.current_show_status_triangle = show_status_triangle
        
        self.original_show_statusbar = show_statusbar
        self.current_show_statusbar = show_statusbar
        
        self.original_remember_filter_folders = remember_filter_folders
        self.current_remember_filter_folders = remember_filter_folders
        

        
        self.updating_ui = False
        
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Scroll area for settings contents
        scroll = QScrollArea()
        scroll.setObjectName("appearanceScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll)

        container = QWidget()
        container.setObjectName("appearanceContainer")
        scroll.setWidget(container)
        
        cols_layout = QHBoxLayout(container)
        cols_layout.setSpacing(16)
        cols_layout.setContentsMargins(0, 0, 4, 0)
        
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        cols_layout.addLayout(right_layout, 1)
        cols_layout.addLayout(left_layout, 1)
        
        # ------------------ GROUP 1: WINDOW SETTINGS ------------------
        group_colors = QGroupBox(tr("appearance.tab_colors", "Window Settings"))
        colors_layout = QVBoxLayout(group_colors)
        colors_layout.setSpacing(10)
        colors_layout.setContentsMargins(8, 12, 8, 8)
        
        # Helper regex validator for HEX colors
        hex_regex = QRegularExpression("^#[0-9A-Fa-f]{0,6}$")
        validator = QRegularExpressionValidator(hex_regex, self)
        
        # Dummy line edit just to sync field height across widgets
        dummy_line = QLineEdit()
        dummy_line.ensurePolished()
        field_height = 20
        
        # Grid layout for the color options to keep them perfectly aligned vertically
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Accent Color Row
        accent_label = QLabel(tr("appearance.accent_label"))
        accent_tooltip = tr("appearance.accent_tooltip")
        accent_label.setToolTip(accent_tooltip)
        grid_layout.addWidget(accent_label, 0, 0)
        
        self.accent_color_btn = QPushButton()
        self.accent_color_btn.setObjectName("accentColorBtn")
        self.accent_color_btn.setFixedSize(field_height, field_height)
        self.accent_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accent_color_btn.setToolTip(accent_tooltip)
        self.accent_color_btn.clicked.connect(self.choose_accent_color)
        grid_layout.addWidget(self.accent_color_btn, 0, 1)
        
        self.accent_hex_input = QLineEdit()
        self.accent_hex_input.setObjectName("accentHexInput")
        self.accent_hex_input.setMaxLength(7)
        self.accent_hex_input.setFixedWidth(75)
        self.accent_hex_input.setFixedHeight(field_height)

        self.accent_hex_input.setValidator(validator)
        self.accent_hex_input.setToolTip(accent_tooltip)
        self.accent_hex_input.textChanged.connect(self.on_accent_hex_changed)
        grid_layout.addWidget(self.accent_hex_input, 0, 2)
        
        # 2. Window Color Row
        window_label = QLabel(tr("appearance.window_label"))
        window_tooltip = tr("appearance.window_tooltip")
        window_label.setToolTip(window_tooltip)
        grid_layout.addWidget(window_label, 1, 0)
        
        self.window_color_btn = QPushButton()
        self.window_color_btn.setObjectName("windowColorBtn")
        self.window_color_btn.setFixedSize(field_height, field_height)
        self.window_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.window_color_btn.setToolTip(window_tooltip)
        self.window_color_btn.clicked.connect(self.choose_window_color)
        grid_layout.addWidget(self.window_color_btn, 1, 1)
        
        self.window_hex_input = QLineEdit()
        self.window_hex_input.setObjectName("windowHexInput")
        self.window_hex_input.setMaxLength(7)
        self.window_hex_input.setFixedWidth(75)
        self.window_hex_input.setFixedHeight(field_height)

        self.window_hex_input.setValidator(validator)
        self.window_hex_input.setToolTip(window_tooltip)
        self.window_hex_input.textChanged.connect(self.on_window_hex_changed)
        grid_layout.addWidget(self.window_hex_input, 1, 2)

        # 3. Secondary BG Color Row
        bg_dark_label = QLabel(tr("appearance.bg_dark_label"))
        bg_dark_tooltip = tr("appearance.bg_dark_tooltip")
        bg_dark_label.setToolTip(bg_dark_tooltip)
        grid_layout.addWidget(bg_dark_label, 2, 0)
        
        self.bg_dark_color_btn = QPushButton()
        self.bg_dark_color_btn.setObjectName("bgDarkColorBtn")
        self.bg_dark_color_btn.setFixedSize(field_height, field_height)
        self.bg_dark_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_dark_color_btn.setToolTip(bg_dark_tooltip)
        self.bg_dark_color_btn.clicked.connect(self.choose_bg_dark_color)
        grid_layout.addWidget(self.bg_dark_color_btn, 2, 1)
        
        self.bg_dark_hex_input = QLineEdit()
        self.bg_dark_hex_input.setObjectName("bgDarkHexInput")
        self.bg_dark_hex_input.setMaxLength(7)
        self.bg_dark_hex_input.setFixedWidth(75)
        self.bg_dark_hex_input.setFixedHeight(field_height)

        self.bg_dark_hex_input.setValidator(validator)
        self.bg_dark_hex_input.setToolTip(bg_dark_tooltip)
        self.bg_dark_hex_input.textChanged.connect(self.on_bg_dark_hex_changed)
        grid_layout.addWidget(self.bg_dark_hex_input, 2, 2)
        
        # 4. Font Color Row
        text_label = QLabel(tr("appearance.text_label"))
        text_tooltip = tr("appearance.text_tooltip")
        text_label.setToolTip(text_tooltip)
        grid_layout.addWidget(text_label, 3, 0)
        
        self.text_color_btn = QPushButton()
        self.text_color_btn.setObjectName("textColorBtn")
        self.text_color_btn.setFixedSize(field_height, field_height)
        self.text_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_color_btn.setToolTip(text_tooltip)
        self.text_color_btn.clicked.connect(self.choose_text_color)
        grid_layout.addWidget(self.text_color_btn, 3, 1)
        
        self.text_hex_input = QLineEdit()
        self.text_hex_input.setObjectName("textHexInput")
        self.text_hex_input.setMaxLength(7)
        self.text_hex_input.setFixedWidth(75)
        self.text_hex_input.setFixedHeight(field_height)

        self.text_hex_input.setValidator(validator)
        self.text_hex_input.setToolTip(text_tooltip)
        self.text_hex_input.textChanged.connect(self.on_text_hex_changed)
        grid_layout.addWidget(self.text_hex_input, 3, 2)
        
        # 5. Border Color Row
        border_label = QLabel(tr("appearance.border_label"))
        border_tooltip = tr("appearance.border_tooltip")
        border_label.setToolTip(border_tooltip)
        grid_layout.addWidget(border_label, 4, 0)
        
        self.border_color_btn = QPushButton()
        self.border_color_btn.setObjectName("borderColorBtn")
        self.border_color_btn.setFixedSize(field_height, field_height)
        self.border_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.border_color_btn.setToolTip(border_tooltip)
        self.border_color_btn.clicked.connect(self.choose_border_color)
        grid_layout.addWidget(self.border_color_btn, 4, 1)
        
        self.border_hex_input = QLineEdit()
        self.border_hex_input.setObjectName("borderHexInput")
        self.border_hex_input.setMaxLength(7)
        self.border_hex_input.setFixedWidth(75)
        self.border_hex_input.setFixedHeight(field_height)

        self.border_hex_input.setValidator(validator)
        self.border_hex_input.setToolTip(border_tooltip)
        self.border_hex_input.textChanged.connect(self.on_border_hex_changed)
        grid_layout.addWidget(self.border_hex_input, 4, 2)
        
        # 6. Icon Color Row
        icon_label = QLabel(tr("appearance.icon_label", "Icon Color:"))
        icon_tooltip = tr("appearance.icon_tooltip", "Color for application SVG icons")
        icon_label.setToolTip(icon_tooltip)
        grid_layout.addWidget(icon_label, 5, 0)
        
        self.icon_color_btn = QPushButton()
        self.icon_color_btn.setObjectName("iconColorBtn")
        self.icon_color_btn.setFixedSize(field_height, field_height)
        self.icon_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_color_btn.setToolTip(icon_tooltip)
        self.icon_color_btn.clicked.connect(self.choose_icon_color)
        grid_layout.addWidget(self.icon_color_btn, 5, 1)
        
        self.icon_hex_input = QLineEdit()
        self.icon_hex_input.setObjectName("iconHexInput")
        self.icon_hex_input.setMaxLength(7)
        self.icon_hex_input.setFixedWidth(75)
        self.icon_hex_input.setFixedHeight(field_height)

        self.icon_hex_input.setValidator(validator)
        self.icon_hex_input.setToolTip(icon_tooltip)
        self.icon_hex_input.textChanged.connect(self.on_icon_color_hex_changed)
        grid_layout.addWidget(self.icon_hex_input, 5, 2)
        
        # 7. Icon Line Thickness Row
        thickness_label = QLabel(tr("appearance.icon_thickness_label", "Icon Line Thickness:"))
        thickness_tooltip = tr("appearance.icon_thickness_tooltip", "Stroke width for application SVG icons (1.0 - 4.0)")
        thickness_label.setToolTip(thickness_tooltip)
        grid_layout.addWidget(thickness_label, 6, 0)
        
        self.thickness_slider = QSlider(Qt.Orientation.Horizontal)
        self.thickness_slider.setObjectName("iconThicknessSlider")
        self.thickness_slider.setRange(10, 40)
        self.thickness_slider.setToolTip(thickness_tooltip)
        self.thickness_slider.valueChanged.connect(self.on_thickness_slider_changed)
        grid_layout.addWidget(self.thickness_slider, 6, 1, 1, 2)
        
        self.thickness_value_label = QLabel()
        self.thickness_value_label.setObjectName("iconThicknessValueLabel")
        self.thickness_value_label.setFixedWidth(50)
        self.thickness_value_label.setToolTip(thickness_tooltip)
        grid_layout.addWidget(self.thickness_value_label, 6, 3)
        
        # Let column 4 take any extra space to push controls left
        grid_layout.setColumnStretch(4, 1)
        colors_layout.addLayout(grid_layout)
        
        # Add window settings checkboxes (like Show Status Bar)
        colors_layout.addSpacing(4)
        self.chk_statusbar = QCheckBox(tr("menu.show_statusbar", "Show Status Bar"))
        self.chk_statusbar.setToolTip(tr("appearance.statusbar_tooltip"))
        self.chk_statusbar.stateChanged.connect(self.on_interface_checkbox_changed)
        colors_layout.addWidget(self.chk_statusbar)
        
        left_layout.addWidget(group_colors)
        
        # ------------------ GROUP 2: LIBRARY LIST SETTINGS ------------------
        group_info = QGroupBox(tr("appearance.tab_info", "Library List Settings"))
        info_layout = QVBoxLayout(group_info)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(8, 12, 8, 8)
        
        # Library List View checkboxes (nesting lines, status triangle, remember filter folders)
        self.chk_status_triangle = QCheckBox(tr("menu.show_status_triangle", "Show Status Triangle"))
        self.chk_status_triangle.setToolTip(tr("appearance.status_triangle_tooltip"))
        self.chk_nesting_lines = QCheckBox(tr("menu.show_nesting_lines", "Show Nesting Lines"))
        self.chk_nesting_lines.setToolTip(tr("appearance.nesting_lines_tooltip"))
        self.chk_remember_filter_folders = QCheckBox(tr("menu.remember_filter_folders", "Remember Folder View"))
        self.chk_remember_filter_folders.setToolTip(tr("appearance.remember_filter_folders_tooltip"))
        
        info_layout.addWidget(self.chk_status_triangle)

        # Status Colors Grid (Indented under show_status_triangle checkbox)
        self.status_colors_widget = QWidget()
        status_colors_grid = QGridLayout(self.status_colors_widget)
        status_colors_grid.setHorizontalSpacing(8)
        status_colors_grid.setVerticalSpacing(8)
        status_colors_grid.setContentsMargins(15, 0, 0, 4)
        
        # New Status Row
        status_new_label = QLabel(tr("appearance.status_new_label", "New Status Color:"))
        status_new_tooltip = tr("appearance.status_new_tooltip")
        status_new_label.setToolTip(status_new_tooltip)
        status_colors_grid.addWidget(status_new_label, 0, 0)
        
        self.status_new_color_btn = QPushButton()
        self.status_new_color_btn.setFixedSize(field_height, field_height)
        self.status_new_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_new_color_btn.setToolTip(status_new_tooltip)
        self.status_new_color_btn.clicked.connect(self.choose_status_new_color)
        status_colors_grid.addWidget(self.status_new_color_btn, 0, 1)
        
        self.status_new_hex_input = QLineEdit()
        self.status_new_hex_input.setObjectName("statusNewHexInput")
        self.status_new_hex_input.setMaxLength(7)
        self.status_new_hex_input.setFixedWidth(75)
        self.status_new_hex_input.setFixedHeight(field_height)
        self.status_new_hex_input.setValidator(validator)
        self.status_new_hex_input.setToolTip(status_new_tooltip)
        self.status_new_hex_input.textChanged.connect(self.on_status_new_hex_changed)
        status_colors_grid.addWidget(self.status_new_hex_input, 0, 2)
        
        # Started Status Row
        status_started_label = QLabel(tr("appearance.status_started_label", "Started Status Color:"))
        status_started_tooltip = tr("appearance.status_started_tooltip")
        status_started_label.setToolTip(status_started_tooltip)
        status_colors_grid.addWidget(status_started_label, 1, 0)
        
        self.status_started_color_btn = QPushButton()
        self.status_started_color_btn.setFixedSize(field_height, field_height)
        self.status_started_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_started_color_btn.setToolTip(status_started_tooltip)
        self.status_started_color_btn.clicked.connect(self.choose_status_started_color)
        status_colors_grid.addWidget(self.status_started_color_btn, 1, 1)
        
        self.status_started_hex_input = QLineEdit()
        self.status_started_hex_input.setObjectName("statusStartedHexInput")
        self.status_started_hex_input.setMaxLength(7)
        self.status_started_hex_input.setFixedWidth(75)
        self.status_started_hex_input.setFixedHeight(field_height)
        self.status_started_hex_input.setValidator(validator)
        self.status_started_hex_input.setToolTip(status_started_tooltip)
        self.status_started_hex_input.textChanged.connect(self.on_status_started_hex_changed)
        status_colors_grid.addWidget(self.status_started_hex_input, 1, 2)
        
        # Completed Status Row
        status_completed_label = QLabel(tr("appearance.status_completed_label", "Finished Status Color:"))
        status_completed_tooltip = tr("appearance.status_completed_tooltip")
        status_completed_label.setToolTip(status_completed_tooltip)
        status_colors_grid.addWidget(status_completed_label, 2, 0)
        
        self.status_completed_color_btn = QPushButton()
        self.status_completed_color_btn.setFixedSize(field_height, field_height)
        self.status_completed_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_completed_color_btn.setToolTip(status_completed_tooltip)
        self.status_completed_color_btn.clicked.connect(self.choose_status_completed_color)
        status_colors_grid.addWidget(self.status_completed_color_btn, 2, 1)
        
        self.status_completed_hex_input = QLineEdit()
        self.status_completed_hex_input.setObjectName("statusCompletedHexInput")
        self.status_completed_hex_input.setMaxLength(7)
        self.status_completed_hex_input.setFixedWidth(75)
        self.status_completed_hex_input.setFixedHeight(field_height)
        self.status_completed_hex_input.setValidator(validator)
        self.status_completed_hex_input.setToolTip(status_completed_tooltip)
        self.status_completed_hex_input.textChanged.connect(self.on_status_completed_hex_changed)
        status_colors_grid.addWidget(self.status_completed_hex_input, 2, 2)
        
        status_colors_grid.setColumnStretch(3, 1)
        info_layout.addWidget(self.status_colors_widget)

        # Book Info Line Settings Section
        self.chk_show_detailed_info = QCheckBox(tr("appearance.show_detailed_info"))
        self.chk_show_detailed_info.setToolTip(tr("appearance.show_detailed_info_tooltip"))
        self.chk_show_detailed_info.setStyleSheet("margin-bottom: 2px;")
        info_layout.addWidget(self.chk_show_detailed_info)
        
        checkbox_layout = QVBoxLayout()
        checkbox_layout.setSpacing(6)
        checkbox_layout.setContentsMargins(15, 0, 0, 0)
        

        self.info_list_widget = QListWidget()
        self.info_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.info_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.info_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.info_list_widget.setObjectName("infoListWidget")
        self.info_list_widget.setToolTip(tr("appearance.info_items_tooltip"))
        self.info_list_widget.setFixedHeight(200)
        
        self.btn_up = QPushButton("▲")
        self.btn_up.setToolTip(tr("appearance.move_up", "Move Up"))
        self.btn_up.setFixedSize(30, 30)
        self.btn_up.clicked.connect(self.move_item_up)
        
        self.btn_down = QPushButton("▼")
        self.btn_down.setToolTip(tr("appearance.move_down", "Move Down"))
        self.btn_down.setFixedSize(30, 30)
        self.btn_down.clicked.connect(self.move_item_down)
        
        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(8)
        list_btn_layout.addWidget(self.info_list_widget, 1)
        
        btn_v_layout = QVBoxLayout()
        btn_v_layout.setSpacing(4)
        btn_v_layout.addWidget(self.btn_up)
        btn_v_layout.addWidget(self.btn_down)
        btn_v_layout.addStretch()
        
        list_btn_layout.addLayout(btn_v_layout)
        checkbox_layout.addLayout(list_btn_layout)
        
        info_layout.addLayout(checkbox_layout)

        info_layout.addWidget(self.chk_nesting_lines)
        info_layout.addWidget(self.chk_remember_filter_folders)
        
        self.chk_status_triangle.stateChanged.connect(self.on_interface_checkbox_changed)
        self.chk_nesting_lines.stateChanged.connect(self.on_interface_checkbox_changed)
        self.chk_remember_filter_folders.stateChanged.connect(self.on_interface_checkbox_changed)
        
        self.chk_show_detailed_info.stateChanged.connect(self.on_show_detailed_info_changed)
        
        # Connect list widget signals
        self.info_list_widget.itemChanged.connect(self.on_list_item_changed)

        right_layout.addWidget(group_info)
        right_layout.addStretch()
        
        # ------------------ GROUP 3: PLAYER SETTINGS ------------------
        group_interface = QGroupBox(tr("appearance.tab_interface", "Player Settings"))
        interface_layout = QVBoxLayout(group_interface)
        interface_layout.setSpacing(8)
        interface_layout.setContentsMargins(8, 12, 8, 8)

        self.chk_visualizer = QCheckBox(tr("menu.show_visualizer", "Show Visualizer"))
        self.chk_visualizer.setToolTip(tr("appearance.visualizer_tooltip"))

        interface_layout.addWidget(self.chk_visualizer)

        self.chk_visualizer.stateChanged.connect(self.on_interface_checkbox_changed)

        left_layout.addWidget(group_interface)
        left_layout.addStretch()
        
        # Action Buttons (Default / Cancel / Save) at the bottom
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setContentsMargins(0, 4, 0, 0)
        
        self.default_btn = QPushButton(tr("appearance.default_btn"))
        self.default_btn.setObjectName("defaultColorBtn")
        self.default_btn.setFixedHeight(28)
        self.default_btn.clicked.connect(self.reset_to_default)
        actions_layout.addWidget(self.default_btn, 1)
        
        cancel_button = QPushButton(tr("appearance.cancel_btn"))
        cancel_button.setObjectName("cancelBtn")
        cancel_button.setIcon(get_icon("cancel") or get_icon("close"))
        cancel_button.setFixedHeight(28)
        cancel_button.clicked.connect(self.reject)
        actions_layout.addWidget(cancel_button, 1)
        
        save_button = QPushButton(tr("appearance.save_btn"))
        save_button.setObjectName("saveBtn")
        save_button.setIcon(get_icon("save"))
        save_button.setFixedHeight(28)
        save_button.clicked.connect(self.accept)
        actions_layout.addWidget(save_button, 1)
        
        main_layout.addLayout(actions_layout)
        
        # Aliases for backward compatibility
        self.hex_input = self.accent_hex_input
        self.custom_color_btn = self.accent_color_btn
        
        # Set dynamic property for stylesheet styling of color buttons
        for btn in [
            self.accent_color_btn, self.window_color_btn, self.bg_dark_color_btn,
            self.text_color_btn, self.border_color_btn, self.icon_color_btn,
            self.status_new_color_btn, self.status_started_color_btn, self.status_completed_color_btn
        ]:
            btn.setProperty("class", "color-btn")
            
        # Sync UI controls to starting colors and checkboxes
        self.update_ui_from_accent(self.current_accent)
        self.update_ui_from_window(self.current_window)
        self.update_ui_from_bg_dark(self.current_bg_dark)
        self.update_ui_from_text(self.current_text)
        self.update_ui_from_border(self.current_border)
        self.update_ui_from_icon_color(self.current_icon_color)
        self.update_ui_from_status_new(self.current_status_new)
        self.update_ui_from_status_started(self.current_status_started)
        self.update_ui_from_status_completed(self.current_status_completed)
        self.update_checkboxes_ui()
        self.update_ui_from_icon_thickness(self.current_icon_thickness)
        
    def on_thickness_slider_changed(self, value):
        self.current_icon_thickness = value / 10.0
        self.thickness_value_label.setText(f"{self.current_icon_thickness:.1f} px")
        self.emit_preview()

    def update_ui_from_icon_thickness(self, thickness: float):
        """Synchronize custom icon line thickness slider and value label"""
        self.updating_ui = True
        try:
            self.thickness_slider.setValue(int(thickness * 10))
            self.thickness_value_label.setText(f"{thickness:.1f} px")
        finally:
            self.updating_ui = False
        
    def emit_preview(self):
        """Emit current colors and icon thickness for live previewing"""
        self.appearance_preview.emit(
            self.current_accent,
            self.current_window,
            self.current_bg_dark,
            self.current_text,
            self.current_border,
            self.current_status_new,
            self.current_status_started,
            self.current_status_completed,
            self.current_icon_color,
            self.current_icon_thickness
        )

    def get_tooltip_qss(self):
        bg = self.current_bg_dark if self.current_bg_dark else "#373737"
        text = self.current_text if self.current_text else "#eaeaea"
        accent = self.current_accent if self.current_accent else "#018574"
        return f"QToolTip {{ background-color: {bg}; color: {text}; border: 1px solid {accent}; padding: 4px; border-radius: 3px; }}"

    def update_color_button_stylesheets(self):
        tooltip_qss = self.get_tooltip_qss()
        buttons = [
            ("accent_color_btn", self.current_accent),
            ("window_color_btn", self.current_window),
            ("bg_dark_color_btn", self.current_bg_dark),
            ("text_color_btn", self.current_text),
            ("border_color_btn", self.current_border),
            ("icon_color_btn", self.current_icon_color),
            ("status_new_color_btn", self.current_status_new),
            ("status_started_color_btn", self.current_status_started),
            ("status_completed_color_btn", self.current_status_completed),
        ]
        for attr, color_hex in buttons:
            btn = getattr(self, attr, None)
            if btn and color_hex:
                btn.setStyleSheet(f"QPushButton {{ background-color: {color_hex}; }} {tooltip_qss}")

    def update_color_button(self, btn, hex_input, color_hex):
        self.updating_ui = True
        try:
            hex_input.setText(color_hex.upper())
        finally:
            self.updating_ui = False
        
        # Sync values in class attributes as they might have been called before updating_ui check
        if btn == getattr(self, "accent_color_btn", None):
            self.current_accent = color_hex
        elif btn == getattr(self, "window_color_btn", None):
            self.current_window = color_hex
        elif btn == getattr(self, "bg_dark_color_btn", None):
            self.current_bg_dark = color_hex
        elif btn == getattr(self, "text_color_btn", None):
            self.current_text = color_hex
        elif btn == getattr(self, "border_color_btn", None):
            self.current_border = color_hex
        elif btn == getattr(self, "icon_color_btn", None):
            self.current_icon_color = color_hex
        elif btn == getattr(self, "status_new_color_btn", None):
            self.current_status_new = color_hex
        elif btn == getattr(self, "status_started_color_btn", None):
            self.current_status_started = color_hex
        elif btn == getattr(self, "status_completed_color_btn", None):
            self.current_status_completed = color_hex

        self.update_color_button_stylesheets()

    def update_ui_from_icon_color(self, color_hex: str):
        """Synchronize custom icon color button background and hex input"""
        self.update_color_button(self.icon_color_btn, self.icon_hex_input, color_hex)

    def update_ui_from_status_new(self, color_hex: str):
        """Synchronize custom status new color button background and hex input"""
        self.update_color_button(self.status_new_color_btn, self.status_new_hex_input, color_hex)

    def update_ui_from_status_started(self, color_hex: str):
        """Synchronize custom status started color button background and hex input"""
        self.update_color_button(self.status_started_color_btn, self.status_started_hex_input, color_hex)

    def update_ui_from_status_completed(self, color_hex: str):
        """Synchronize custom status completed color button background and hex input"""
        self.update_color_button(self.status_completed_color_btn, self.status_completed_hex_input, color_hex)

    def update_ui_from_accent(self, color_hex: str):
        """Synchronize custom accent color button background and hex input"""
        self.update_color_button(self.accent_color_btn, self.accent_hex_input, color_hex)

    def update_ui_from_window(self, color_hex: str):
        """Synchronize custom window color button background and hex input"""
        self.update_color_button(self.window_color_btn, self.window_hex_input, color_hex)

    def update_ui_from_bg_dark(self, color_hex: str):
        """Synchronize custom secondary bg color button background and hex input"""
        self.update_color_button(self.bg_dark_color_btn, self.bg_dark_hex_input, color_hex)
            
    def update_ui_from_text(self, color_hex: str):
        """Synchronize custom font color button background and hex input"""
        self.update_color_button(self.text_color_btn, self.text_hex_input, color_hex)
            
    def update_ui_from_border(self, color_hex: str):
        """Synchronize custom border color button background and hex input"""
        self.update_color_button(self.border_color_btn, self.border_hex_input, color_hex)
            
    def choose_accent_color(self):
        """Open custom compact color picker dialog for accent and preview changes live"""
        color_before = self.current_accent
        dialog = ColorPickerDialog(self, QColor(self.current_accent))
        dialog.colorChanged.connect(self.select_accent_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_accent_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_accent = dialog.color.name().upper()
        else:
            self.current_accent = color_before
        self.update_ui_from_accent(self.current_accent)
        self.emit_preview()
        self.accent_preview.emit(self.current_accent)
            
    def select_accent_color_preview(self, color: QColor):
        """Update accent preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_accent = color_hex
        self.update_ui_from_accent(color_hex)
        self.emit_preview()
        self.accent_preview.emit(color_hex)
        
    def choose_window_color(self):
        """Open custom compact color picker dialog for window background and preview changes live"""
        color_before = self.current_window
        dialog = ColorPickerDialog(self, QColor(self.current_window))
        dialog.colorChanged.connect(self.select_window_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_window_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_window = dialog.color.name().upper()
        else:
            self.current_window = color_before
        self.update_ui_from_window(self.current_window)
        self.emit_preview()
            
    def select_window_color_preview(self, color: QColor):
        """Update window preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_window = color_hex
        self.update_ui_from_window(color_hex)
        self.emit_preview()

    def choose_bg_dark_color(self):
        """Open custom compact color picker dialog for secondary bg and preview changes live"""
        color_before = self.current_bg_dark
        dialog = ColorPickerDialog(self, QColor(self.current_bg_dark))
        dialog.colorChanged.connect(self.select_bg_dark_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_bg_dark_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_bg_dark = dialog.color.name().upper()
        else:
            self.current_bg_dark = color_before
        self.update_ui_from_bg_dark(self.current_bg_dark)
        self.emit_preview()
            
    def select_bg_dark_color_preview(self, color: QColor):
        """Update secondary bg preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_bg_dark = color_hex
        self.update_ui_from_bg_dark(color_hex)
        self.emit_preview()
        
    def choose_text_color(self):
        """Open custom compact color picker dialog for font color and preview changes live"""
        color_before = self.current_text
        dialog = ColorPickerDialog(self, QColor(self.current_text))
        dialog.colorChanged.connect(self.select_text_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_text_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_text = dialog.color.name().upper()
        else:
            self.current_text = color_before
        self.update_ui_from_text(self.current_text)
        self.emit_preview()
            
    def select_text_color_preview(self, color: QColor):
        """Update font color preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_text = color_hex
        self.update_ui_from_text(color_hex)
        self.emit_preview()

    def choose_border_color(self):
        """Open custom compact color picker dialog for border color and preview changes live"""
        color_before = self.current_border
        dialog = ColorPickerDialog(self, QColor(self.current_border))
        dialog.colorChanged.connect(self.select_border_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_border_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_border = dialog.color.name().upper()
        else:
            self.current_border = color_before
        self.update_ui_from_border(self.current_border)
        self.emit_preview()
            
    def select_border_color_preview(self, color: QColor):
        """Update border color preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_border = color_hex
        self.update_ui_from_border(color_hex)
        self.emit_preview()

    def choose_icon_color(self):
        """Open custom compact color picker dialog for icon color and preview changes live"""
        color_before = self.current_icon_color
        dialog = ColorPickerDialog(self, QColor(self.current_icon_color))
        dialog.colorChanged.connect(self.select_icon_color_preview)
        result = dialog.exec()
        try:
            dialog.colorChanged.disconnect(self.select_icon_color_preview)
        except Exception:
            pass

        if result == QDialog.DialogCode.Accepted:
            self.current_icon_color = dialog.color.name().upper()
        else:
            self.current_icon_color = color_before
        self.update_ui_from_icon_color(self.current_icon_color)
        self.emit_preview()
            
    def select_icon_color_preview(self, color: QColor):
        """Update icon color preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_icon_color = color_hex
        self.update_ui_from_icon_color(color_hex)
        self.emit_preview()

    def choose_status_new_color(self):
        """Open custom compact color picker dialog for status new and preview changes live"""
        color_before = self.current_status_new
        dialog = ColorPickerDialog(self, QColor(self.current_status_new))
        dialog.colorChanged.connect(self.select_status_new_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_status_new = dialog.color.name().upper()
            self.update_ui_from_status_new(self.current_status_new)
            self.emit_preview()
        else:
            self.current_status_new = color_before
            self.update_ui_from_status_new(self.current_status_new)
            self.emit_preview()
            
    def select_status_new_color_preview(self, color: QColor):
        """Update status new preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_status_new = color_hex
        self.update_ui_from_status_new(color_hex)
        self.emit_preview()

    def choose_status_started_color(self):
        """Open custom compact color picker dialog for status started and preview changes live"""
        color_before = self.current_status_started
        dialog = ColorPickerDialog(self, QColor(self.current_status_started))
        dialog.colorChanged.connect(self.select_status_started_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_status_started = dialog.color.name().upper()
            self.update_ui_from_status_started(self.current_status_started)
            self.emit_preview()
        else:
            self.current_status_started = color_before
            self.update_ui_from_status_started(self.current_status_started)
            self.emit_preview()
            
    def select_status_started_color_preview(self, color: QColor):
        """Update status started preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_status_started = color_hex
        self.update_ui_from_status_started(color_hex)
        self.emit_preview()

    def choose_status_completed_color(self):
        """Open custom compact color picker dialog for status completed and preview changes live"""
        color_before = self.current_status_completed
        dialog = ColorPickerDialog(self, QColor(self.current_status_completed))
        dialog.colorChanged.connect(self.select_status_completed_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_status_completed = dialog.color.name().upper()
            self.update_ui_from_status_completed(self.current_status_completed)
            self.emit_preview()
        else:
            self.current_status_completed = color_before
            self.update_ui_from_status_completed(self.current_status_completed)
            self.emit_preview()
            
    def select_status_completed_color_preview(self, color: QColor):
        """Update status completed preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_status_completed = color_hex
        self.update_ui_from_status_completed(color_hex)
        self.emit_preview()

    def on_accent_hex_changed(self, text: str):
        """Update accent picker button and emit preview from Accent Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.accent_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_accent = text.upper()
                self.update_ui_from_accent(self.current_accent)
                self.emit_preview()
                self.accent_preview.emit(self.current_accent)

    def on_window_hex_changed(self, text: str):
        """Update window picker button and emit preview from Window Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.window_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_window = text.upper()
                self.update_ui_from_window(self.current_window)
                self.emit_preview()

    def on_bg_dark_hex_changed(self, text: str):
        """Update secondary bg picker button and emit preview from Secondary BG Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.bg_dark_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_bg_dark = text.upper()
                self.update_ui_from_bg_dark(self.current_bg_dark)
                self.emit_preview()

    def on_text_hex_changed(self, text: str):
        """Update font color picker button and emit preview from Font Color Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.text_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_text = text.upper()
                self.update_ui_from_text(self.current_text)
                self.emit_preview()
                
    def on_border_hex_changed(self, text: str):
        """Update border color picker button and emit preview from Border Color Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.border_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_border = text.upper()
                self.update_ui_from_border(self.current_border)
                self.emit_preview()

    def on_icon_color_hex_changed(self, text: str):
        """Update icon color picker button and emit preview from Icon Color Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.icon_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_icon_color = text.upper()
                self.update_ui_from_icon_color(self.current_icon_color)
                self.emit_preview()

    def on_status_new_hex_changed(self, text: str):
        """Update status new picker button and emit preview from Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.status_new_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_status_new = text.upper()
                self.update_ui_from_status_new(self.current_status_new)
                self.emit_preview()

    def on_status_started_hex_changed(self, text: str):
        """Update status started picker button and emit preview from Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.status_started_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_status_started = text.upper()
                self.update_ui_from_status_started(self.current_status_started)
                self.emit_preview()

    def on_status_completed_hex_changed(self, text: str):
        """Update status completed picker button and emit preview from Hex input box"""
        if self.updating_ui:
            return
            
        if not text.startswith("#"):
            self.updating_ui = True
            text = "#" + text.replace("#", "")
            self.status_completed_hex_input.setText(text)
            self.updating_ui = False
            
        if len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self.current_status_completed = text.upper()
                self.update_ui_from_status_completed(self.current_status_completed)
                self.emit_preview()
                
    def reset_to_default(self):
        """Reset current colors and thickness to theme default values"""
        self.current_accent = self.default_accent
        self.current_window = self.default_window
        self.current_bg_dark = self.default_bg_dark
        self.current_text = self.default_text
        self.current_border = self.default_border
        self.current_icon_color = self.default_icon_color
        self.current_status_new = self.default_status_new
        self.current_status_started = self.default_status_started
        self.current_status_completed = self.default_status_completed
        self.current_icon_thickness = self.default_icon_thickness
        
        self.update_ui_from_accent(self.default_accent)
        self.update_ui_from_window(self.default_window)
        self.update_ui_from_bg_dark(self.default_bg_dark)
        self.update_ui_from_text(self.default_text)
        self.update_ui_from_border(self.default_border)
        self.update_ui_from_icon_color(self.default_icon_color)
        self.update_ui_from_status_new(self.default_status_new)
        self.update_ui_from_status_started(self.default_status_started)
        self.update_ui_from_status_completed(self.default_status_completed)
        self.update_ui_from_icon_thickness(self.default_icon_thickness)
        
        # Reset info line settings to True
        self.current_show_detailed_info = True
        self.current_show_info_progress = True
        self.current_show_info_file_count = True
        self.current_show_info_duration = True
        self.current_show_info_size = True
        self.current_show_info_technical = True
        self.current_show_info_year_written = True
        self.current_show_info_year_recorded = True
        self.current_show_info_language = True
        
        # Reset interface settings to default
        self.current_show_visualizer = True
        self.current_show_nesting_lines = True
        self.current_show_status_triangle = True
        self.current_show_statusbar = True
        self.current_remember_filter_folders = True
        
        self.update_checkboxes_ui()
        
        self.emit_preview()
        self.accent_preview.emit(self.default_accent)
        
    def accept(self):
        """Save and close the dialog"""
        saved_accent = self.current_accent
        if saved_accent.lower() == self.default_accent.lower():
            saved_accent = ""
            
        saved_window = self.current_window
        if saved_window.lower() == self.default_window.lower():
            saved_window = ""
            
        saved_bg_dark = self.current_bg_dark
        if saved_bg_dark.lower() == self.default_bg_dark.lower():
            saved_bg_dark = ""
            
        saved_text = self.current_text
        if saved_text.lower() == self.default_text.lower():
            saved_text = ""
            
        saved_border = self.current_border
        if saved_border.lower() == self.default_border.lower():
            saved_border = ""

        saved_icon_color = self.current_icon_color
        if saved_icon_color.lower() == self.default_icon_color.lower():
            saved_icon_color = ""

        saved_status_new = self.current_status_new
        if saved_status_new.lower() == self.default_status_new.lower():
            saved_status_new = ""

        saved_status_started = self.current_status_started
        if saved_status_started.lower() == self.default_status_started.lower():
            saved_status_started = ""

        saved_status_completed = self.current_status_completed
        if saved_status_completed.lower() == self.default_status_completed.lower():
            saved_status_completed = ""
            
        self.appearance_saved.emit(saved_accent, saved_window, saved_bg_dark, saved_text, saved_border,
                                   saved_status_new, saved_status_started, saved_status_completed,
                                   saved_icon_color, self.current_icon_thickness)
        # Also emit old compatibility signal
        self.accent_saved.emit(saved_accent)
        super().accept()
        
    def reject(self):
        """Revert preview changes and close the dialog"""
        self.current_accent = self.original_accent
        self.current_window = self.original_window
        self.current_bg_dark = self.original_bg_dark
        self.current_text = self.original_text
        self.current_border = self.original_border
        self.current_icon_color = self.original_icon_color
        self.current_status_new = self.original_status_new
        self.current_status_started = self.original_status_started
        self.current_status_completed = self.original_status_completed
        self.current_icon_thickness = self.original_icon_thickness
 
        self.update_ui_from_accent(self.original_accent)
        self.update_ui_from_window(self.original_window)
        self.update_ui_from_bg_dark(self.original_bg_dark)
        self.update_ui_from_text(self.original_text)
        self.update_ui_from_border(self.original_border)
        self.update_ui_from_icon_color(self.original_icon_color)
        self.update_ui_from_status_new(self.original_status_new)
        self.update_ui_from_status_started(self.original_status_started)
        self.update_ui_from_status_completed(self.original_status_completed)
        self.update_ui_from_icon_thickness(self.original_icon_thickness)
 
        self.current_show_detailed_info = self.original_show_detailed_info
        self.current_show_info_progress = self.original_show_info_progress
        self.current_show_info_file_count = self.original_show_info_file_count
        self.current_show_info_duration = self.original_show_info_duration
        self.current_show_info_size = self.original_show_info_size
        self.current_show_info_technical = self.original_show_info_technical
        self.current_show_info_year_written = self.original_show_info_year_written
        self.current_show_info_year_recorded = self.original_show_info_year_recorded
        self.current_show_info_language = self.original_show_info_language
        self.current_info_order = self.original_info_order
        
        self.current_show_visualizer = self.original_show_visualizer
        self.current_show_nesting_lines = self.original_show_nesting_lines
        self.current_show_status_triangle = self.original_show_status_triangle
        self.current_show_statusbar = self.original_show_statusbar
        self.current_remember_filter_folders = self.original_remember_filter_folders
        
        self.update_checkboxes_ui()
 
        self.emit_preview()
        # Also emit old compatibility signal
        self.accent_preview.emit(self.original_accent)
        super().reject()

    def populate_info_list(self, keys):
        old_updating = self.updating_ui
        self.updating_ui = True
        try:
            self.info_list_widget.clear()
            
            key_to_val = {
                "progress": self.current_show_info_progress,
                "file_count": self.current_show_info_file_count,
                "duration": self.current_show_info_duration,
                "size": self.current_show_info_size,
                "technical": self.current_show_info_technical,
                "year_written": self.current_show_info_year_written,
                "year_recorded": self.current_show_info_year_recorded,
                "language": self.current_show_info_language,
            }
            
            for key in keys:
                if key in self.key_to_translation:
                    name = tr(self.key_to_translation[key])
                    item = QListWidgetItem(name)
                    item.setData(Qt.ItemDataRole.UserRole, key)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    
                    tooltip_key = f"appearance.info_{key}_tooltip"
                    if key == "file_count":
                        tooltip_key = "appearance.info_files_tooltip"
                    item.setToolTip(tr(tooltip_key))
                    
                    checked = key_to_val.get(key, True)
                    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                    self.info_list_widget.addItem(item)
            self.adjust_list_widget_height()
        finally:
            self.updating_ui = old_updating

    def adjust_list_widget_height(self):
        h = 0
        for i in range(self.info_list_widget.count()):
            row_h = self.info_list_widget.sizeHintForRow(i)
            if row_h <= 0:
                row_h = 24
            h += row_h
        h += self.info_list_widget.frameWidth() * 2 + 4
        self.info_list_widget.setFixedHeight(max(h, 200))

    def showEvent(self, event):
        super().showEvent(event)
        self.adjust_list_widget_height()

    def update_info_order_from_list(self):
        keys = []
        for i in range(self.info_list_widget.count()):
            item = self.info_list_widget.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            keys.append(key)
            checked = item.checkState() == Qt.CheckState.Checked
            if key == "progress":
                self.current_show_info_progress = checked
            elif key == "file_count":
                self.current_show_info_file_count = checked
            elif key == "duration":
                self.current_show_info_duration = checked
            elif key == "size":
                self.current_show_info_size = checked
            elif key == "technical":
                self.current_show_info_technical = checked
            elif key == "year_written":
                self.current_show_info_year_written = checked
            elif key == "year_recorded":
                self.current_show_info_year_recorded = checked
            elif key == "language":
                self.current_show_info_language = checked
        self.current_info_order = ",".join(keys)

    def on_list_item_changed(self, item):
        if self.updating_ui:
            return
        self.update_info_order_from_list()
        self.emit_preview()

    def move_item_up(self):
        curr_row = self.info_list_widget.currentRow()
        if curr_row > 0:
            self.info_list_widget.itemChanged.disconnect(self.on_list_item_changed)
            try:
                item = self.info_list_widget.takeItem(curr_row)
                self.info_list_widget.insertItem(curr_row - 1, item)
                self.info_list_widget.setCurrentRow(curr_row - 1)
                self.update_info_order_from_list()
                self.emit_preview()
            finally:
                self.info_list_widget.itemChanged.connect(self.on_list_item_changed)

    def move_item_down(self):
        curr_row = self.info_list_widget.currentRow()
        if curr_row >= 0 and curr_row < self.info_list_widget.count() - 1:
            self.info_list_widget.itemChanged.disconnect(self.on_list_item_changed)
            try:
                item = self.info_list_widget.takeItem(curr_row)
                self.info_list_widget.insertItem(curr_row + 1, item)
                self.info_list_widget.setCurrentRow(curr_row + 1)
                self.update_info_order_from_list()
                self.emit_preview()
            finally:
                self.info_list_widget.itemChanged.connect(self.on_list_item_changed)

    def update_checkboxes_ui(self):
        """Update checkboxes widgets state based on internal current values"""
        old_updating = self.updating_ui
        self.updating_ui = True
        try:
            self.chk_show_detailed_info.setChecked(self.current_show_detailed_info)
            
            order_keys = [k.strip() for k in self.current_info_order.split(",") if k.strip() in self.info_keys]
            for k in self.info_keys:
                if k not in order_keys:
                    order_keys.append(k)
            self.populate_info_list(order_keys)
            
            self.chk_visualizer.setChecked(self.current_show_visualizer)
            self.chk_nesting_lines.setChecked(self.current_show_nesting_lines)
            self.chk_status_triangle.setChecked(self.current_show_status_triangle)
            self.chk_statusbar.setChecked(self.current_show_statusbar)
            self.chk_remember_filter_folders.setChecked(self.current_remember_filter_folders)
            
            # Update enabled state of child widgets
            enabled = self.current_show_detailed_info
            self.info_list_widget.setEnabled(enabled)
            self.btn_up.setEnabled(enabled)
            self.btn_down.setEnabled(enabled)
            
            # Enable/disable status colors customization
            self.status_colors_widget.setEnabled(self.current_show_status_triangle)
        finally:
            self.updating_ui = old_updating

    def on_show_detailed_info_changed(self):
        """Handle state change in the master show_detailed_info checkbox"""
        if self.updating_ui:
            return
            
        self.current_show_detailed_info = self.chk_show_detailed_info.isChecked()
        
        # Update enabled state of child widgets
        enabled = self.current_show_detailed_info
        self.info_list_widget.setEnabled(enabled)
        self.btn_up.setEnabled(enabled)
        self.btn_down.setEnabled(enabled)
        
        # Emit live preview to update the layout
        self.emit_preview()

    def on_interface_checkbox_changed(self):
        """Handle state change in interface checkboxes to update internal state and trigger live preview"""
        if self.updating_ui:
            return
            
        self.current_show_visualizer = self.chk_visualizer.isChecked()
        self.current_show_nesting_lines = self.chk_nesting_lines.isChecked()
        self.current_show_status_triangle = self.chk_status_triangle.isChecked()
        self.current_show_statusbar = self.chk_statusbar.isChecked()
        self.current_remember_filter_folders = self.chk_remember_filter_folders.isChecked()
        
        # Enable/disable status colors customization dynamically
        self.status_colors_widget.setEnabled(self.current_show_status_triangle)
        
        # Emit live preview to update the layout
        self.emit_preview()

    def get_info_settings(self) -> dict:
        """Get the current settings of the info line checkboxes"""
        return {
            "show_detailed_info": self.current_show_detailed_info,
            "show_info_progress": self.current_show_info_progress,
            "show_info_file_count": self.current_show_info_file_count,
            "show_info_duration": self.current_show_info_duration,
            "show_info_size": self.current_show_info_size,
            "show_info_technical": self.current_show_info_technical,
            "show_info_year_written": self.current_show_info_year_written,
            "show_info_year_recorded": self.current_show_info_year_recorded,
            "show_info_language": self.current_show_info_language,
            "info_order": self.current_info_order
        }

    def get_interface_settings(self) -> dict:
        """Get the current settings of the interface checkboxes"""
        return {
            "show_visualizer": self.current_show_visualizer,
            "show_nesting_lines": self.current_show_nesting_lines,
            "show_status_triangle": self.current_show_status_triangle,
            "show_statusbar": self.current_show_statusbar,
            "remember_filter_folders": self.current_remember_filter_folders
        }
