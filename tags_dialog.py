from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QPushButton, QInputDialog, QMessageBox, QColorDialog, QLabel, 
    QWidget, QFormLayout, QLineEdit, QDialogButtonBox, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter

from translations import tr
from utils import get_icon
from styles import StyleManager

class ColorPickerPopup(QDialog):
    """Custom popup for selecting from 16 predefined colors"""
    colorSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def setup_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("colorPickerContainer")
        # Assuming styling is handled via globally loaded QSS, but adding some fallback style
        self.container.setStyleSheet("""
            QWidget#colorPickerContainer {
                background-color: #2D2D2D;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QPushButton.colorCell {
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 0px;
            }
            QPushButton.colorCell:hover {
                border: 1px solid white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Force the dialog to fit the content size exactly
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(self.container)
        
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(8, 8, 8, 8)

        colors = [
            "#FFC8C8", "#FFD1B3", "#FFE4B3", "#FFFFBA", # Row 1
            "#EEFFB3", "#B3FFB3", "#BAFFC9", "#B3FFE4", # Row 2
            "#B3FFFF", "#BAE1FF", "#B3D4FF", "#B3B3FF", # Row 3
            "#D4B3FF", "#FFB3FF", "#FFB3D4", "#FFB3BA"  # Row 4
        ]

        for i, color_hex in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setProperty("class", "colorCell")
            btn.setStyleSheet(f"background-color: {color_hex}; border: none;")
            btn.clicked.connect(lambda checked, c=color_hex: self.on_color_clicked(c))
            # Align center within the grid cell to prevent any potential stretching
            self.grid.addWidget(btn, i // 4, i % 4, Qt.AlignmentFlag.AlignCenter)

    def on_color_clicked(self, color_hex):
        self.colorSelected.emit(color_hex)
        self.accept()

class TagManagerDialog(QDialog):
    """Dialog to manage all tags (add, edit, delete) AND assign them to an optional audiobook"""
    def __init__(self, db_manager, parent=None, audiobook_id=None):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        
        # Default color from new palette (Coral)
        self.current_color = "#FFC8C8"
        
        # Title depends on context
        title = tr("tags.manager_title")
        if self.audiobook_id:
             title = tr("tags.assign_title")
             
        self.setWindowTitle(title)
        self.resize(450, 500)
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
            
        # New Tag Edit Row (Moved above list)
        edit_layout = QHBoxLayout()
        edit_layout.setSpacing(5)
        edit_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(30, 30)
        self.color_btn.setToolTip(tr("tags.select_color"))
        self.color_btn.clicked.connect(self.select_color)
        self.update_color_preview()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("tags.name_label").replace(":", ""))
        self.name_edit.setFixedHeight(38)
        
        btn_size = QSize(30, 30)
        
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
        self.edit_btn.setEnabled(False)
        
        self.del_btn = QPushButton()
        self.del_btn.setIcon(get_icon("delete"))
        self.del_btn.setFixedSize(btn_size)
        self.del_btn.setToolTip(tr("tags.delete_btn"))
        self.del_btn.clicked.connect(self.delete_tag)
        self.del_btn.setEnabled(False)
        
        edit_layout.addWidget(self.color_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        edit_layout.addWidget(self.name_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        edit_layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        edit_layout.addWidget(self.edit_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        edit_layout.addWidget(self.del_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        layout.addLayout(edit_layout)
        layout.addSpacing(5)
        
        # Middle area (List)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("tagsList")
        self.list_widget.currentItemChanged.connect(self.on_selection_changed)
        layout.addWidget(self.list_widget)
        
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
        self.name_edit.clear()
        self.current_color = "#FFC8C8"
        self.update_color_preview()
        
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
            pixmap.fill(QColor(tag['color'] or self.current_color))
            item.setIcon(QIcon(pixmap))
            
            # Store full data
            item.setData(Qt.ItemDataRole.UserRole, tag)
            
            # Checkbox logic
            if self.audiobook_id:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
                check_state = Qt.CheckState.Checked if tag['id'] in assigned_ids else Qt.CheckState.Unchecked
                item.setCheckState(check_state)
            
            self.list_widget.addItem(item)
            
    def select_color(self):
        popup = ColorPickerPopup(self)
        
        # Position the popup below the color button
        btn_pos = self.color_btn.mapToGlobal(QPoint(0, self.color_btn.height()))
        popup.move(btn_pos)
        
        popup.colorSelected.connect(self.on_color_selected)
        popup.exec()
            
    def on_color_selected(self, color_hex):
        self.current_color = color_hex
        self.update_color_preview()

            
    def update_color_preview(self):
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(self.current_color))
        self.color_btn.setIcon(QIcon(pixmap))
        
    def on_selection_changed(self, current, previous):
        if not current:
            self.name_edit.clear()
            self.edit_btn.setEnabled(False)
            self.del_btn.setEnabled(False)
            return
            
        data = current.data(Qt.ItemDataRole.UserRole)
        self.name_edit.setText(data['name'])
        self.current_color = data['color']
        self.update_color_preview()
        
        self.edit_btn.setEnabled(True)
        self.del_btn.setEnabled(True)
        
    def add_tag(self):
        name = self.name_edit.text().strip()
        color = self.current_color
        if name:
            new_id = self.db.create_tag(name, color)
            if new_id:
                self.load_tags()
            else:
                QMessageBox.warning(self, tr("error"), tr("tags.error_create"))
                    
    def edit_tag(self):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        data = item.data(Qt.ItemDataRole.UserRole)
        name = self.name_edit.text().strip()
        color = self.current_color
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

