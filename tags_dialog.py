from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QPushButton, QInputDialog, QMessageBox, QColorDialog, QLabel, 
    QWidget, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter

from translations import tr
from utils import get_icon

class TagEditDialog(QDialog):
    """Dialog for creating or editing a tag"""
    def __init__(self, parent=None, name="", color=None):
        super().__init__(parent)
        self.setWindowTitle(tr("tags.edit_title") if name else tr("tags.create_title"))
        self.setModal(True)
        self.name = name
        self.color = color or "#018574" # Default teal
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.name_edit = QLineEdit(self.name)
        form.addRow(tr("tags.name_label"), self.name_edit)
        
        # Color picker
        color_layout = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(24, 24)
        self.update_color_preview()
        
        self.color_btn = QPushButton(tr("tags.select_color"))
        self.color_btn.clicked.connect(self.select_color)
        
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        
        form.addRow(tr("tags.color_label"), color_layout)
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def update_color_preview(self):
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(self.color))
        self.color_preview.setPixmap(pixmap)
        
    def select_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, tr("tags.select_color"))
        if color.isValid():
            self.color = color.name()
            self.update_color_preview()
            
    def get_data(self):
        return self.name_edit.text().strip(), self.color

class TagManagerDialog(QDialog):
    """Dialog to manage all tags (add, edit, delete)"""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle(tr("tags.manager_title"))
        self.resize(400, 500)
        self.setup_ui()
        self.load_tags()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton(tr("tags.add_btn"))
        self.add_btn.clicked.connect(self.add_tag)
        
        self.edit_btn = QPushButton(tr("tags.edit_btn"))
        self.edit_btn.clicked.connect(self.edit_tag)
        
        self.del_btn = QPushButton(tr("tags.delete_btn"))
        self.del_btn.clicked.connect(self.delete_tag)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.del_btn)
        
        layout.addLayout(btn_layout)
        
        close_btn = QPushButton(tr("scan_dialog.close")) # Reuse existing string
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
    def load_tags(self):
        self.list_widget.clear()
        tags = self.db.get_all_tags()
        for tag in tags:
            item = QListWidgetItem(tag['name'])
            # Create a colored icon for the specific tag
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(tag['color'] or "#FFFFFF"))
            item.setIcon(QIcon(pixmap))
            item.setData(Qt.ItemDataRole.UserRole, tag) # Store full tag dict
            self.list_widget.addItem(item)
            
    def add_tag(self):
        dialog = TagEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, color = dialog.get_data()
            if name:
                if self.db.create_tag(name, color):
                    self.load_tags()
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

class TagSelectionDialog(QDialog):
    """Dialog to assign tags to an audiobook"""
    def __init__(self, db_manager, audiobook_id, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        self.setWindowTitle(tr("tags.assign_title"))
        self.resize(300, 400)
        self.setup_ui()
        self.load_tags()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        # Manage button shortcut
        manage_btn = QPushButton(tr("tags.manage_link"))
        manage_btn.setFlat(True)
        manage_btn.setStyleSheet("text-align: left; color: #0078d7;")
        manage_btn.clicked.connect(self.open_manager)
        layout.addWidget(manage_btn)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def load_tags(self):
        self.list_widget.clear()
        all_tags = self.db.get_all_tags()
        assigned_tags = self.db.get_tags_for_audiobook(self.audiobook_id)
        assigned_ids = {t['id'] for t in assigned_tags}
        
        for tag in all_tags:
            item = QListWidgetItem(tag['name'])
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(tag['color'] or "#FFFFFF"))
            item.setIcon(QIcon(pixmap))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if tag['id'] in assigned_ids else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, tag['id'])
            self.list_widget.addItem(item)
            
    def open_manager(self):
        manager = TagManagerDialog(self.db, self)
        manager.exec()
        self.load_tags() # Refresh list
        
    def save_selection(self):
        # We can implement smart sync (add missing, remove unselected)
        # Or simplistic: remove all, add selected.
        # Smart sync is better.
        
        current_assigned = {t['id'] for t in self.db.get_tags_for_audiobook(self.audiobook_id)}
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tag_id = item.data(Qt.ItemDataRole.UserRole)
            is_checked = item.checkState() == Qt.CheckState.Checked
            
            if is_checked and tag_id not in current_assigned:
                self.db.add_tag_to_audiobook(self.audiobook_id, tag_id)
            elif not is_checked and tag_id in current_assigned:
                self.db.remove_tag_from_audiobook(self.audiobook_id, tag_id)
                
        self.accept()
