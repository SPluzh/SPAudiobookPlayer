
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTimer, Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QIcon
import math

class VisualizerButton(QPushButton):
    """
    A QPushButton that renders a real-time frequency spectrum visualization 
    as its background.
    """
    def __init__(self, parent=None, fps=30):
        super().__init__(parent)
        self.player = None
        self.fps = fps
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_visualization)
        
        self.bar_count = 20  # Fewer bars for a button
        self.bar_color = QColor("#CCCCCC")
        self.bar_color.setAlpha(180) # Slightly transparent
        self.decay = [0.0] * self.bar_count
        self.decay_speed = 0.2
        
        # Start animation
        self.timer.start(1000 // self.fps)
        
    def set_player(self, player):
        self.player = player
        
    def update_visualization(self):
        if self.isVisible() and self.player and self.player.is_playing():
             self.update()
        elif self.player and not self.player.is_playing():
             # Ensure we clear the vis when stopped
             if any(x > 0.01 for x in self.decay):
                 self.update()
            
    def paintEvent(self, event):
        # 1. Run standard button painting (background, border, etc.)
        # We can either let super() paint first, or replace it.
        # Let's let super() paint everything (including icon), but we want vis BEHIND icon.
        # So we should paint vis first, then call super() but super() might draw background over it.
        # Actually, standard QPushButton paints background. 
        # Best approach: Paint our own background + vis, then call standard paint for Icon/Text?
        # Or just paint vis on top of background? 
        
        # Let's try:
        # 1. Custom paint background (if needed)
        # 2. Paint Vis
        # 3. Call super().paintEvent(event) ? No, super will draw background over.
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw styling (simulated from stylesheet or just simple)
        # Since we use QSS, we might want to respect it. 
        # But for valid QSS background + custom painting, it's tricky.
        # Let's draw the visualization *over* the button background but *under* the icon.
        
        # To do this correctly with QSS:
        # We invoke the style to draw the Control (background/border)
        opt = self.initStyleOption_()
        self.style().drawControl(Qt.Style.CE_PushButton, opt, painter, self)
        
        # Now draw visualization
        if self.player and self.player.is_playing():
            self.draw_spectrum(painter)
            
        # Now draw the Icon manually (to ensure it's on top)
        # The style().drawControl already drew the icon if we didn't mask it.
        # But since we drew spectrum AFTER drawControl, we might be drawing over the icon?
        # No, Audio spectrum is usually at bottom or full fill? 
        
        # Wait, if we use drawControl, it draws EVERYTHING (Background + Icon + Text).
        # So if we draw spectrum AFTER, it is ON TOP of Icon. bad.
        # If we draw spectrum BEFORE, drawControl (Background) overwrites it.
        
        # Solution:
        # 1. Draw spectrum.
        # 2. Draw Icon manually.
        # But we lose the nice QSS background styling unless we replicate it or assume transparent background.
        
        # Alternative: 
        # Use a transparent background for the button in QSS, paint our own background + spectrum, then draw Icon.
        pass # Replaced by actual code below

    def paintEvent(self, event):
        # 1. Let standard button paint itself first (Background, Border, Icon, Text)
        super().paintEvent(event)
        
        # 2. Draw spectrum visualization OVER background but potentially UNDER content needed?
        # Since super() paints everything, we are painting ON TOP of everything (including text/icon).
        # We will re-paint the icon at the end to ensure it's visible.
        
        if self.player and self.player.is_playing():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            self.draw_spectrum(painter)
            
            # 3. Re-draw icon to be on top of spectrum
            if not self.icon().isNull():
                icon = self.icon()
                rect = self.rect()
                size = self.iconSize()
                
                # Center icon
                x = (rect.width() - size.width()) // 2
                y = (rect.height() - size.height()) // 2
                
                # Get correct state
                mode = QIcon.Mode.Normal
                if not self.isEnabled(): mode = QIcon.Mode.Disabled
                elif self.isDown(): mode = QIcon.Mode.Selected
                
                icon.paint(painter, x, y, size.width(), size.height(), Qt.AlignmentFlag.AlignCenter, mode)
                
    def draw_spectrum(self, painter):
        # Get FFT data
        data = self.player.get_spectrum()
        if not data:
            return
            
        width = self.width()
        height = self.height()
        mid_y = height / 2
        
        useful_data = data[:100] # less bins for button
        step = len(useful_data) / self.bar_count
        
        current_levels = []
        for i in range(self.bar_count):
            idx = int(i * step)
            val = useful_data[idx] 
            boosted = math.sqrt(val) * 3 
            
            if boosted > self.decay[i]:
                self.decay[i] = boosted
            else:
                self.decay[i] = max(0, self.decay[i] - self.decay_speed)
            current_levels.append(self.decay[i])

        # Draw centered bars
        bar_width = width / self.bar_count
        gap = 1
        draw_width = max(1, bar_width - gap)
        
        painter.setBrush(QBrush(self.bar_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        for i, val in enumerate(current_levels):
            # Scale to button height
            pixel_height = min(height, val * height * 0.8)
            
            # Center mirrored
            y = mid_y - (pixel_height / 2)
            x = i * bar_width + (gap / 2)
            
            painter.drawRoundedRect(QRectF(x, y, draw_width, pixel_height), 1, 1)

    # Helper for paintEvent to use Style
    def initStyleOption_(self):
        # Create a QStyleOptionButton initialized from this widget
        from PyQt6.QtWidgets import QStyleOptionButton
        opt = QStyleOptionButton()
        opt.initFrom(self)
        opt.text = self.text()
        opt.icon = self.icon()
        opt.iconSize = self.iconSize()
        return opt
