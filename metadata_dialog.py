from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QDialogButtonBox, QMessageBox, QFormLayout,
    QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from pathlib import Path

from translations import tr
from utils import get_icon

class CoverThumbnailWidget(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, cover_id, image_path, is_selected=False, parent=None):
        super().__init__(parent)
        self.cover_id = cover_id
        self.image_path = image_path
        self.is_selected = is_selected
        
        self.setFixedSize(110, 110)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_pixmap()
        
    def update_pixmap(self):
        from utils import load_icon
        
        cover_icon = None
        if self.image_path and Path(self.image_path).exists():
            cover_icon = load_icon(Path(self.image_path), 100, force_square=True)
        else:
            # Default cover image
            from utils import get_base_path
            default_cover_path = get_base_path() / "resources" / "icons" / "default_cover.png"
            if default_cover_path.exists():
                cover_icon = load_icon(default_cover_path, 100, force_square=True)
            
        if cover_icon and not cover_icon.isNull():
            pixmap = cover_icon.pixmap(100, 100)
            self.setPixmap(pixmap)
        else:
            self.setText(tr("metadata.no_cover_text", default="No Cover"))
            
    def set_selected(self, selected):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_selected:
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                from styles import StyleManager
                try:
                    _, accent_color = StyleManager.get_theme_property("delegate_accent")
                except Exception:
                    accent_color = QColor("#2ecc71") # Fallback emerald green
                
                pen = QPen(accent_color, 3)
                painter.setPen(pen)
                border_rect = QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
                painter.drawRoundedRect(border_rect, 4, 4)
            finally:
                painter.end()


class MetadataEditDialog(QDialog):
    """Dialog for manually editing audiobook metadata"""
    
    def __init__(self, db_manager, audiobook_id, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        
        self.setWindowTitle(tr("metadata.edit_title"))
        self.setModal(True)
        self.resize(480, 450)
        
        self.current_data = self.db.get_audiobook_metadata(self.audiobook_id)
        if not self.current_data:
            # If no data found (e.g. deleted), close immediately
            self.reject()
            return

        self.setup_ui()
        self.load_suggestions()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Cover selection section (at the top of the dialog)
        self.covers = self.db.get_audiobook_covers(self.audiobook_id)
        
        # Title/label for cover selection
        cover_label = QLabel(tr("metadata.select_cover", default="Select Cover:"))
        layout.addWidget(cover_label)
        
        # Scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(140)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setObjectName("coverScrollArea")
        
        scroll_content = QWidget()
        scroll_content.setObjectName("coverScrollContent")
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        scroll_layout.setSpacing(10)
        
        self.thumbnail_widgets = []
        
        # Find currently selected cover
        self.selected_cover_id = None
        for cov in self.covers:
            if cov['is_selected']:
                self.selected_cover_id = cov['id']
                
        # Add covers
        for cov in self.covers:
            thumb = CoverThumbnailWidget(
                cover_id=cov['id'],
                image_path=cov['cached_path'],
                is_selected=(cov['id'] == self.selected_cover_id),
                parent=self
            )
            thumb.clicked.connect(self.on_cover_clicked)
            scroll_layout.addWidget(thumb)
            self.thumbnail_widgets.append(thumb)
            
        # Add "No Cover" option at the end
        no_cover_thumb = CoverThumbnailWidget(
            cover_id=None,
            image_path=None,
            is_selected=(self.selected_cover_id is None),
            parent=self
        )
        no_cover_thumb.clicked.connect(self.on_cover_clicked)
        scroll_layout.addWidget(no_cover_thumb)
        self.thumbnail_widgets.append(no_cover_thumb)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Form fields
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Author Field
        self.author_combo = QComboBox()
        self.author_combo.setEditable(True)
        # Prevent resizing based on content
        self.author_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.author_combo.setMinimumWidth(300)
        # Allow inserting any text
        self.author_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.author_combo.setCurrentText(self.current_data.get('author') or "")
        form_layout.addRow(tr("metadata.author"), self.author_combo)
        
        # Title Field
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        self.title_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.title_combo.setMinimumWidth(300)
        self.title_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.title_combo.setCurrentText(self.current_data.get('title') or "")
        form_layout.addRow(tr("metadata.title"), self.title_combo)
        
        # Narrator Field
        self.narrator_combo = QComboBox()
        self.narrator_combo.setEditable(True)
        self.narrator_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.narrator_combo.setMinimumWidth(300)
        self.narrator_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.narrator_combo.setCurrentText(self.current_data.get('narrator') or "")
        form_layout.addRow(tr("metadata.narrator"), self.narrator_combo)
        
        layout.addLayout(form_layout)
        
        # Action Buttons
        
        # "Fill from Tags" Button
        tags_layout = QHBoxLayout()
        self.from_tags_btn = QPushButton(tr("metadata.from_tags"))
        self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip"))
        self.from_tags_btn.clicked.connect(self.fill_from_tags)
        tags_layout.addWidget(self.from_tags_btn)
        tags_layout.addStretch()
        layout.addLayout(tags_layout)
        
        layout.addStretch()
        
        # Standard Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # Customize button text via translation keys
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setText(tr("metadata.save", default="Save"))
        
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText(tr("metadata.cancel", default="Cancel"))
        
        layout.addWidget(buttons)
        
    def load_suggestions(self):
        """Populate comboboxes with existing values from the database"""
        self.author_combo.blockSignals(True)
        self.title_combo.blockSignals(True)
        self.narrator_combo.blockSignals(True)
        
        local_tags = self.db.get_all_book_raw_tags(self.audiobook_id)
        
        def create_suggestion_list(current_val):
            items = []
            seen = set()
            
            if current_val:
                items.append(current_val)
                seen.add(current_val)
            
            for tag in local_tags:
                if tag not in seen:
                    items.append(tag)
                    seen.add(tag)
                    
            return items

        self.author_combo.addItems(create_suggestion_list(
            self.current_data.get('author')
        ))
        
        self.title_combo.addItems(create_suggestion_list(
            self.current_data.get('title')
        ))
        
        self.narrator_combo.addItems(create_suggestion_list(
            self.current_data.get('narrator')
        ))
        
        self.author_combo.setCurrentText(self.current_data.get('author') or "")
        self.title_combo.setCurrentText(self.current_data.get('title') or "")
        self.narrator_combo.setCurrentText(self.current_data.get('narrator') or "")
            
        self.author_combo.blockSignals(False)
        self.title_combo.blockSignals(False)
        self.narrator_combo.blockSignals(False)

    def fill_from_tags(self):
        """Fill entry fields using the extracted ID3 tags"""
        if self.current_data:
            tag_author = self.current_data.get('tag_author')
            tag_title = self.current_data.get('tag_title')
            tag_narrator = self.current_data.get('tag_narrator')
            
            if tag_author:
                self.author_combo.setCurrentText(tag_author)
            if tag_title:
                self.title_combo.setCurrentText(tag_title)
            if tag_narrator:
                self.narrator_combo.setCurrentText(tag_narrator)
                
    def update_texts(self):
        """Update UI texts when language changes"""
        self.setWindowTitle(tr("metadata.edit_title"))
        self.from_tags_btn.setText(tr("metadata.from_tags"))
        self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip"))

    def get_data(self):
        """Return the entered metadata as a tuple"""
        return (
            self.author_combo.currentText().strip(),
            self.title_combo.currentText().strip(),
            self.narrator_combo.currentText().strip()
        )

    def on_cover_clicked(self):
        """Handle cover thumbnail clicks and toggle selection outline"""
        clicked_widget = self.sender()
        if not clicked_widget:
            return
        
        self.selected_cover_id = clicked_widget.cover_id
        
        # Update selection status for all thumbnails
        for thumb in self.thumbnail_widgets:
            thumb.set_selected(thumb.cover_id == self.selected_cover_id)

    def accept(self):
        """Save selected cover and close the dialog"""
        self.db.set_selected_audiobook_cover(self.audiobook_id, self.selected_cover_id)
        super().accept()
