from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QPushButton, QInputDialog, QMessageBox, QColorDialog, QLabel, 
    QWidget, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter

from translations import tr
from utils import get_icon
from styles import StyleManager

class TagEditDialog(QDialog):
    """Dialog for creating or editing a tag"""
    def __init__(self, parent=None, name="", color=None):
        super().__init__(parent)
        self.setWindowTitle(tr("tags.edit_title") if name else tr("tags.create_title"))
        self.setModal(True)
        self.name = name
        
        # Default teal from theme
        _, accent_color = StyleManager.get_theme_property('delegate_accent')
        self.color = color or accent_color.name()
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Preview Area (Top)
        preview_container = QHBoxLayout()
        preview_container.addStretch()
        self.preview_label = QLabel()
        self.preview_label.setObjectName("tagPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_container.addWidget(self.preview_label)
        preview_container.addStretch()
        layout.addLayout(preview_container)
        
        layout.addSpacing(10)
        
        # 2. Name Edit
        self.name_edit = QLineEdit(self.name)
        self.name_edit.setPlaceholderText(tr("tags.name_label").replace(":", "")) # Remove colon if present
        self.name_edit.textChanged.connect(self.update_tag_preview)
        layout.addWidget(self.name_edit)
        
        # 3. Color Picker
        color_layout = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(24, 24)
        self.update_color_preview()
        
        self.color_btn = QPushButton(tr("tags.select_color"))
        self.color_btn.clicked.connect(self.select_color)
        
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        
        layout.addLayout(color_layout)
        
        # Initialize preview
        self.update_tag_preview()
        
        layout.addStretch()
        
        # 4. Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def update_color_preview(self):
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(self.color))
        self.color_preview.setPixmap(pixmap)
        
    def update_tag_preview(self):
        text = self.name_edit.text().strip() or tr("tags.preview_placeholder")
        if text == "tags.preview_placeholder": # Fallback if translation missing
             text = "Tag Preview"
             
        self.preview_label.setText(text)
        
        bg_color = QColor(self.color)
        # Contrast logic matching library.py
        text_color = "#FFFFFF" if bg_color.lightness() < 130 else "#000000"
        
        # Only set dynamic colors, static props are in QSS #tagPreview
        self.preview_label.setStyleSheet(f"""
            background-color: {bg_color.name()};
            color: {text_color};
        """)

    def select_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, tr("tags.select_color"))
        if color.isValid():
            self.color = color.name()
            self.update_color_preview()
            self.update_tag_preview()
            
    def get_data(self):
        return self.name_edit.text().strip(), self.color

class TagManagerDialog(QDialog):
    """Dialog to manage all tags (add, edit, delete) AND assign them to an optional audiobook"""
    def __init__(self, db_manager, parent=None, audiobook_id=None):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        
        # Title depends on context
        title = tr("tags.manager_title")
        if self.audiobook_id:
             title = tr("tags.assign_title") # Or a combined string like "Manage & Assign Tags"
             
        self.setWindowTitle(title)
        self.resize(400, 500)
        self.setModal(True)
        
        self.setup_ui()
        self.load_tags()
        
    def setup_ui(self):
        # Main layout is vertical
        layout = QVBoxLayout(self)
        
        # Help label if in assignment mode
        if self.audiobook_id:
            lbl = QLabel(tr("tags.assign_help"))
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            
        # Middle area (List + Side Buttons)
        middle_layout = QHBoxLayout()
        
        self.list_widget = QListWidget()
        # Explicitly enable selection highlight to override global theme
        self.list_widget.setObjectName("tagsList")
        middle_layout.addWidget(self.list_widget)
        
        # Management Controls (Vertical on the right)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        # removed top stretch to align to top
        
        btn_size = QSize(32, 32)
        
        self.add_btn = QPushButton()
        self.add_btn.setIcon(get_icon("add"))
        self.add_btn.setFixedSize(btn_size)
        self.add_btn.setToolTip(tr("tags.add_btn"))
        self.add_btn.clicked.connect(self.add_tag)
        
        self.edit_btn = QPushButton()
        self.edit_btn.setIcon(get_icon("edit"))
        self.edit_btn.setFixedSize(btn_size)
        self.edit_btn.setToolTip(tr("tags.edit_btn"))
        self.edit_btn.clicked.connect(self.edit_tag)
        
        self.del_btn = QPushButton()
        self.del_btn.setIcon(get_icon("delete"))
        self.del_btn.setFixedSize(btn_size)
        self.del_btn.setToolTip(tr("tags.delete_btn"))
        self.del_btn.clicked.connect(self.delete_tag)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addStretch()
        
        middle_layout.addLayout(btn_layout)
        layout.addLayout(middle_layout)
        
        # Dialog Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        from PyQt6.QtWidgets import QSizePolicy
        
        if self.audiobook_id:
            # Assign Button
            self.assign_btn = QPushButton(tr("tags.assign_btn"))
            self.assign_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.assign_btn.clicked.connect(self.save_selection)
            bottom_layout.addWidget(self.assign_btn)
            
            # Close Button
            self.close_btn = QPushButton(tr("tags.close_btn"))
            self.close_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.close_btn.clicked.connect(self.reject)
            bottom_layout.addWidget(self.close_btn)
        else:
            # Just Close button for pure management
            self.close_btn = QPushButton(tr("tags.close_btn"))
            self.close_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.close_btn.clicked.connect(self.accept)
            bottom_layout.addWidget(self.close_btn)
            
        layout.addLayout(bottom_layout)
        
    def load_tags(self):
        self.list_widget.clear()
        
        all_tags = self.db.get_all_tags()
        
        # If in assignment mode, get currently assigned tags
        assigned_ids = set()
        if self.audiobook_id:
            assigned_tags = self.db.get_tags_for_audiobook(self.audiobook_id)
            assigned_ids = {t['id'] for t in assigned_tags}
        
        for tag in all_tags:
            item = QListWidgetItem(tag['name'])
            
            # Icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(tag['color'] or "#FFFFFF"))
            item.setIcon(QIcon(pixmap))
            
            # Store full data
            item.setData(Qt.ItemDataRole.UserRole, tag)
            
            # Checkbox logic
            if self.audiobook_id:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                check_state = Qt.CheckState.Checked if tag['id'] in assigned_ids else Qt.CheckState.Unchecked
                item.setCheckState(check_state)
            
            self.list_widget.addItem(item)
            
    def add_tag(self):
        dialog = TagEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.get_data()
            if name:
                new_id = self.db.create_tag(name, color)
                if new_id:
                    self.load_tags()
                    
                    # If we added a tag during assignment, maybe we want to select it automatically?
                    # For now, let user select it.
                else:
                    QMessageBox.warning(self, tr("error"), tr("tags.error_create"))
                    
    def edit_tag(self):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        data = item.data(Qt.ItemDataRole.UserRole)
        dialog = TagEditDialog(self, data['name'], data['color'])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.get_data()
            if name:
                self.db.update_tag(data['id'], name, color)
                self.load_tags()
                
    def delete_tag(self):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        if QMessageBox.question(self, tr("tags.confirm_delete_title"), 
                              tr("tags.confirm_delete_msg")) == QMessageBox.StandardButton.Yes:
            data = item.data(Qt.ItemDataRole.UserRole)
            self.db.delete_tag(data['id'])
            self.load_tags()

    def save_selection(self):
        if not self.audiobook_id:
            self.accept()
            return
            
        current_assigned = {t['id'] for t in self.db.get_tags_for_audiobook(self.audiobook_id)}
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tag = item.data(Qt.ItemDataRole.UserRole)
            tag_id = tag['id']
            
            is_checked = item.checkState() == Qt.CheckState.Checked
            
            if is_checked and tag_id not in current_assigned:
                self.db.add_tag_to_audiobook(self.audiobook_id, tag_id)
            elif not is_checked and tag_id in current_assigned:
                self.db.remove_tag_from_audiobook(self.audiobook_id, tag_id)
                
        self.accept()
