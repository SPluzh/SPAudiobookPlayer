from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QLineEdit, QWidget, QGridLayout
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QRegularExpression
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
        
        hue_gradient = (
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #FF0000, stop:0.17 #FFFF00, stop:0.33 #00FF00, "
            "stop:0.5 #00FFFF, stop:0.67 #0000FF, stop:0.83 #FF00FF, stop:1 #FF0000);"
        )
        self.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                {hue_gradient}
                height: 12px;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                border: 1px solid #555555;
                width: 10px;
                height: 16px;
                margin-top: -2px;
                margin-bottom: -2px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #eeeeee;
            }}
        """)


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
        self.preview_box.setStyleSheet(
            f"background-color: {self.color.name()}; border: 1px solid #555555; border-radius: 4px;"
        )


class AppearanceDialog(QDialog):
    """Compact appearance settings dialog with custom color picker fields and Hex inputs for accent, window background, and secondary background"""
    
    # Signals
    accent_preview = pyqtSignal(str)       # Keeping for backward compatibility
    accent_saved = pyqtSignal(str)         # Keeping for backward compatibility
    appearance_preview = pyqtSignal(str, str, str, str, str) # Emits (accent_color, window_color, bg_dark_color, text_color, border_color)
    appearance_saved = pyqtSignal(str, str, str, str, str)   # Emits (accent_color, window_color, bg_dark_color, text_color, border_color)
    
    def __init__(self, parent=None, current_accent="", default_accent="", current_window="", default_window="", current_bg_dark="", default_bg_dark="", current_text="", default_text="", current_border="", default_border=""):
        """Initialize appearance settings dialog"""
        super().__init__(parent)
        self.setWindowTitle(tr("appearance.title"))
        self.setMinimumSize(320, 240)
        self.setMaximumWidth(360)
        
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
        
        self.updating_ui = False
        
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Helper regex validator for HEX colors
        hex_regex = QRegularExpression("^#[0-9A-Fa-f]{0,6}$")
        validator = QRegularExpressionValidator(hex_regex, self)
        
        # Dummy line edit just to sync field height across widgets
        dummy_line = QLineEdit()
        dummy_line.ensurePolished()
        field_height = dummy_line.sizeHint().height()
        
        # Grid layout for the color options to keep them perfectly aligned vertically
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(8)
        grid_layout.setVerticalSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Accent Color Row
        accent_label = QLabel(tr("appearance.accent_label"))
        grid_layout.addWidget(accent_label, 0, 0)
        
        self.accent_color_btn = QPushButton()
        self.accent_color_btn.setObjectName("accentColorBtn")
        self.accent_color_btn.setFixedSize(field_height, field_height)
        self.accent_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accent_color_btn.clicked.connect(self.choose_accent_color)
        grid_layout.addWidget(self.accent_color_btn, 0, 1)
        
        self.accent_hex_input = QLineEdit()
        self.accent_hex_input.setObjectName("accentHexInput")
        self.accent_hex_input.setMaxLength(7)
        self.accent_hex_input.setFixedWidth(75)
        self.accent_hex_input.setValidator(validator)
        self.accent_hex_input.textChanged.connect(self.on_accent_hex_changed)
        grid_layout.addWidget(self.accent_hex_input, 0, 2)
        
        # 2. Window Color Row
        window_label = QLabel(tr("appearance.window_label"))
        grid_layout.addWidget(window_label, 1, 0)
        
        self.window_color_btn = QPushButton()
        self.window_color_btn.setObjectName("windowColorBtn")
        self.window_color_btn.setFixedSize(field_height, field_height)
        self.window_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.window_color_btn.clicked.connect(self.choose_window_color)
        grid_layout.addWidget(self.window_color_btn, 1, 1)
        
        self.window_hex_input = QLineEdit()
        self.window_hex_input.setObjectName("windowHexInput")
        self.window_hex_input.setMaxLength(7)
        self.window_hex_input.setFixedWidth(75)
        self.window_hex_input.setValidator(validator)
        self.window_hex_input.textChanged.connect(self.on_window_hex_changed)
        grid_layout.addWidget(self.window_hex_input, 1, 2)

        # 3. Secondary BG Color Row
        bg_dark_label = QLabel(tr("appearance.bg_dark_label"))
        grid_layout.addWidget(bg_dark_label, 2, 0)
        
        self.bg_dark_color_btn = QPushButton()
        self.bg_dark_color_btn.setObjectName("bgDarkColorBtn")
        self.bg_dark_color_btn.setFixedSize(field_height, field_height)
        self.bg_dark_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_dark_color_btn.clicked.connect(self.choose_bg_dark_color)
        grid_layout.addWidget(self.bg_dark_color_btn, 2, 1)
        
        self.bg_dark_hex_input = QLineEdit()
        self.bg_dark_hex_input.setObjectName("bgDarkHexInput")
        self.bg_dark_hex_input.setMaxLength(7)
        self.bg_dark_hex_input.setFixedWidth(75)
        self.bg_dark_hex_input.setValidator(validator)
        self.bg_dark_hex_input.textChanged.connect(self.on_bg_dark_hex_changed)
        grid_layout.addWidget(self.bg_dark_hex_input, 2, 2)
        
        # 4. Font Color Row
        text_label = QLabel(tr("appearance.text_label"))
        grid_layout.addWidget(text_label, 3, 0)
        
        self.text_color_btn = QPushButton()
        self.text_color_btn.setObjectName("textColorBtn")
        self.text_color_btn.setFixedSize(field_height, field_height)
        self.text_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_color_btn.clicked.connect(self.choose_text_color)
        grid_layout.addWidget(self.text_color_btn, 3, 1)
        
        self.text_hex_input = QLineEdit()
        self.text_hex_input.setObjectName("textHexInput")
        self.text_hex_input.setMaxLength(7)
        self.text_hex_input.setFixedWidth(75)
        self.text_hex_input.setValidator(validator)
        self.text_hex_input.textChanged.connect(self.on_text_hex_changed)
        grid_layout.addWidget(self.text_hex_input, 3, 2)
        
        # 5. Border Color Row
        border_label = QLabel(tr("appearance.border_label"))
        grid_layout.addWidget(border_label, 4, 0)
        
        self.border_color_btn = QPushButton()
        self.border_color_btn.setObjectName("borderColorBtn")
        self.border_color_btn.setFixedSize(field_height, field_height)
        self.border_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.border_color_btn.clicked.connect(self.choose_border_color)
        grid_layout.addWidget(self.border_color_btn, 4, 1)
        
        self.border_hex_input = QLineEdit()
        self.border_hex_input.setObjectName("borderHexInput")
        self.border_hex_input.setMaxLength(7)
        self.border_hex_input.setFixedWidth(75)
        self.border_hex_input.setValidator(validator)
        self.border_hex_input.textChanged.connect(self.on_border_hex_changed)
        grid_layout.addWidget(self.border_hex_input, 4, 2)
        
        # Let column 3 take any extra space to push controls left
        grid_layout.setColumnStretch(3, 1)
        main_layout.addLayout(grid_layout)
        
        # 6. Action Buttons (Default / Cancel / Save)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
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
        
        # Sync UI controls to starting colors
        self.update_ui_from_accent(self.current_accent)
        self.update_ui_from_window(self.current_window)
        self.update_ui_from_bg_dark(self.current_bg_dark)
        self.update_ui_from_text(self.current_text)
        self.update_ui_from_border(self.current_border)
        
    def update_ui_from_accent(self, color_hex: str):
        """Synchronize custom accent color button background and hex input"""
        self.updating_ui = True
        try:
            self.accent_hex_input.setText(color_hex.upper())
            self.accent_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 1px solid #555555;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffffff;
                }}
            """)
        finally:
            self.updating_ui = False

    def update_ui_from_window(self, color_hex: str):
        """Synchronize custom window color button background and hex input"""
        self.updating_ui = True
        try:
            self.window_hex_input.setText(color_hex.upper())
            self.window_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 1px solid #555555;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffffff;
                }}
            """)
        finally:
            self.updating_ui = False

    def update_ui_from_bg_dark(self, color_hex: str):
        """Synchronize custom secondary bg color button background and hex input"""
        self.updating_ui = True
        try:
            self.bg_dark_hex_input.setText(color_hex.upper())
            self.bg_dark_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 1px solid #555555;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffffff;
                }}
            """)
        finally:
            self.updating_ui = False
            
    def update_ui_from_text(self, color_hex: str):
        """Synchronize custom font color button background and hex input"""
        self.updating_ui = True
        try:
            self.text_hex_input.setText(color_hex.upper())
            self.text_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 1px solid #555555;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffffff;
                }}
            """)
        finally:
            self.updating_ui = False
            
    def update_ui_from_border(self, color_hex: str):
        """Synchronize custom border color button background and hex input"""
        self.updating_ui = True
        try:
            self.border_hex_input.setText(color_hex.upper())
            self.border_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    border: 1px solid #555555;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid #ffffff;
                }}
            """)
        finally:
            self.updating_ui = False
            
    def choose_accent_color(self):
        """Open custom compact color picker dialog for accent and preview changes live"""
        color_before = self.current_accent
        dialog = ColorPickerDialog(self, QColor(self.current_accent))
        dialog.colorChanged.connect(self.select_accent_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_accent = dialog.color.name().upper()
            self.update_ui_from_accent(self.current_accent)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            self.accent_preview.emit(self.current_accent)
        else:
            self.current_accent = color_before
            self.update_ui_from_accent(self.current_accent)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            self.accent_preview.emit(self.current_accent)
            
    def select_accent_color_preview(self, color: QColor):
        """Update accent preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_accent = color_hex
        self.update_ui_from_accent(color_hex)
        self.appearance_preview.emit(color_hex, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
        self.accent_preview.emit(color_hex)
        
    def choose_window_color(self):
        """Open custom compact color picker dialog for window background and preview changes live"""
        color_before = self.current_window
        dialog = ColorPickerDialog(self, QColor(self.current_window))
        dialog.colorChanged.connect(self.select_window_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_window = dialog.color.name().upper()
            self.update_ui_from_window(self.current_window)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
        else:
            self.current_window = color_before
            self.update_ui_from_window(self.current_window)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            
    def select_window_color_preview(self, color: QColor):
        """Update window preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_window = color_hex
        self.update_ui_from_window(color_hex)
        self.appearance_preview.emit(self.current_accent, color_hex, self.current_bg_dark, self.current_text, self.current_border)

    def choose_bg_dark_color(self):
        """Open custom compact color picker dialog for secondary bg and preview changes live"""
        color_before = self.current_bg_dark
        dialog = ColorPickerDialog(self, QColor(self.current_bg_dark))
        dialog.colorChanged.connect(self.select_bg_dark_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_bg_dark = dialog.color.name().upper()
            self.update_ui_from_bg_dark(self.current_bg_dark)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
        else:
            self.current_bg_dark = color_before
            self.update_ui_from_bg_dark(self.current_bg_dark)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            
    def select_bg_dark_color_preview(self, color: QColor):
        """Update secondary bg preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_bg_dark = color_hex
        self.update_ui_from_bg_dark(color_hex)
        self.appearance_preview.emit(self.current_accent, self.current_window, color_hex, self.current_text, self.current_border)
        
    def choose_text_color(self):
        """Open custom compact color picker dialog for font color and preview changes live"""
        color_before = self.current_text
        dialog = ColorPickerDialog(self, QColor(self.current_text))
        dialog.colorChanged.connect(self.select_text_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_text = dialog.color.name().upper()
            self.update_ui_from_text(self.current_text)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
        else:
            self.current_text = color_before
            self.update_ui_from_text(self.current_text)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            
    def select_text_color_preview(self, color: QColor):
        """Update font color preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_text = color_hex
        self.update_ui_from_text(color_hex)
        self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, color_hex, self.current_border)

    def choose_border_color(self):
        """Open custom compact color picker dialog for border color and preview changes live"""
        color_before = self.current_border
        dialog = ColorPickerDialog(self, QColor(self.current_border))
        dialog.colorChanged.connect(self.select_border_color_preview)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_border = dialog.color.name().upper()
            self.update_ui_from_border(self.current_border)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
        else:
            self.current_border = color_before
            self.update_ui_from_border(self.current_border)
            self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
            
    def select_border_color_preview(self, color: QColor):
        """Update border color preview from dialog changes"""
        color_hex = color.name().upper()
        self.current_border = color_hex
        self.update_ui_from_border(color_hex)
        self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, color_hex)

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
                self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
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
                self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)

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
                self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)

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
                self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
                
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
                self.appearance_preview.emit(self.current_accent, self.current_window, self.current_bg_dark, self.current_text, self.current_border)
                
    def reset_to_default(self):
        """Reset current colors to theme default values"""
        self.current_accent = self.default_accent
        self.current_window = self.default_window
        self.current_bg_dark = self.default_bg_dark
        self.current_text = self.default_text
        self.current_border = self.default_border
        self.update_ui_from_accent(self.default_accent)
        self.update_ui_from_window(self.default_window)
        self.update_ui_from_bg_dark(self.default_bg_dark)
        self.update_ui_from_text(self.default_text)
        self.update_ui_from_border(self.default_border)
        self.appearance_preview.emit(self.default_accent, self.default_window, self.default_bg_dark, self.default_text, self.default_border)
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
            
        self.appearance_saved.emit(saved_accent, saved_window, saved_bg_dark, saved_text, saved_border)
        # Also emit old compatibility signal
        self.accent_saved.emit(saved_accent)
        super().accept()
        
    def reject(self):
        """Revert preview changes and close the dialog"""
        self.appearance_preview.emit(self.original_accent, self.original_window, self.original_bg_dark, self.original_text, self.original_border)
        # Also emit old compatibility signal
        self.accent_preview.emit(self.original_accent)
        super().reject()
