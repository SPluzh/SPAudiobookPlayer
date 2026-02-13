from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QListWidget, QListWidgetItem, 
    QMenu, QMessageBox, QWidget, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QAction

from translations import tr, trf
from utils import get_icon, format_time_short

class BookmarkEditorDialog(QDialog):
    """Dialog for adding or editing a bookmark"""
    def __init__(self, parent=None, title="", description="", files_list=None, current_index=0, position=0):
        super().__init__(parent)
        self.setWindowTitle(tr("bookmarks.edit_title"))
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Title input
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText(tr("bookmarks.title_placeholder"))
        layout.addWidget(QLabel(tr("bookmarks.title_label")))
        layout.addWidget(self.title_edit)
        
        # Description input
        self.desc_edit = QTextEdit(description)
        self.desc_edit.setPlaceholderText(tr("bookmarks.desc_placeholder"))
        self.desc_edit.setMaximumHeight(100)
        layout.addWidget(QLabel(tr("bookmarks.desc_label")))
        layout.addWidget(self.desc_edit)
        
        # Info label (read-only)
        if files_list:
            file_name = files_list[current_index]['name']
            time_str = format_time_short(position)
            info_text = f"{file_name} @ {time_str}"
            info_label = QLabel(info_text)
            info_label.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(info_label)
            
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton(tr("dialog.save"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("dialog.cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def get_data(self):
        return self.title_edit.text(), self.desc_edit.toPlainText()


class BookmarksListDialog(QDialog):
    """Dialog to list and manage bookmarks"""
    bookmark_selected = pyqtSignal(int) # bookmark_id
    
    def __init__(self, parent, db_manager, audiobook_id, current_file_index, current_file_name, current_position):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        self.current_file_index = current_file_index
        self.current_file_name = current_file_name
        self.current_position = current_position
        
        self.setWindowTitle(tr("bookmarks.list_title"))
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        icon_size = QSize(20, 20)
        
        add_btn = QPushButton()
        add_btn.setIcon(get_icon("add"))
        add_btn.setIconSize(icon_size)
        add_btn.setToolTip(tr("bookmarks.add"))
        add_btn.clicked.connect(self.add_bookmark)
        
        play_btn = QPushButton()
        play_btn.setIcon(get_icon("play"))
        play_btn.setIconSize(icon_size)
        play_btn.setToolTip(tr("bookmarks.play"))
        play_btn.clicked.connect(self.on_play_clicked)
        
        edit_btn = QPushButton()
        edit_btn.setIcon(get_icon("edit"))
        edit_btn.setIconSize(icon_size)
        edit_btn.setToolTip(tr("bookmarks.edit"))
        edit_btn.clicked.connect(self.edit_bookmark)
        
        delete_btn = QPushButton()
        delete_btn.setIcon(get_icon("delete"))
        delete_btn.setIconSize(icon_size)
        delete_btn.setToolTip(tr("bookmarks.delete"))
        delete_btn.clicked.connect(self.delete_bookmark)
        
        close_btn = QPushButton(tr("dialog.close"))
        close_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(play_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        self.load_bookmarks()
        
    def load_bookmarks(self):
        self.list_widget.clear()
        bookmarks = self.db.get_bookmarks(self.audiobook_id)
        
        for b in bookmarks:
            item = QListWidgetItem()
            # Format: 'Title (File @ Time)'
            display_title = b['title'] if b['title'] else tr("bookmarks.untitled")
            time_str = format_time_short(b['time_position'])
            
            # We assume file_name is available
            text = f"{display_title}\n{b['file_name']} @ {time_str}"
            if b['description']:
                 text += f"\n{b['description']}"
            
            item.setText(text)
            item.setData(Qt.ItemDataRole.UserRole, b['id'])
            self.list_widget.addItem(item)
            
    def on_item_double_clicked(self, item):
        bookmark_id = item.data(Qt.ItemDataRole.UserRole)
        self.bookmark_selected.emit(bookmark_id)
        self.accept()
        
    def on_play_clicked(self):
        item = self.list_widget.currentItem()
        if item:
            self.on_item_double_clicked(item)
            
    def add_bookmark(self):
        # Use current position data passed in __init__
        timestamp = format_time_short(self.current_position) # Absolute position in file
        default_title = f"{tr('bookmarks.bookmark_at')} {timestamp}"
        
        dlg = BookmarkEditorDialog(
            self, 
            title=default_title,
            description="",
            files_list=None, 
            current_index=self.current_file_index,
            position=self.current_position
        )
        dlg.setWindowTitle(tr("bookmarks.add_title"))
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            title, desc = dlg.get_data()
            if not title:
                title = default_title
                
            self.db.add_bookmark(
                self.audiobook_id,
                self.current_file_name,
                self.current_position,
                title,
                desc
            )
            self.load_bookmarks()

    def edit_bookmark(self):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        bookmark_id = item.data(Qt.ItemDataRole.UserRole)
        bookmarks = self.db.get_bookmarks(self.audiobook_id)
        target = next((b for b in bookmarks if b['id'] == bookmark_id), None)
        
        if target:
            dlg = BookmarkEditorDialog(
                self, 
                title=target['title'], 
                description=target['description']
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                new_title, new_desc = dlg.get_data()
                self.db.update_bookmark(bookmark_id, new_title, new_desc)
                self.load_bookmarks()

    def delete_bookmark(self):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        if QMessageBox.question(self, tr("confirm"), tr("bookmarks.confirm_delete")) == QMessageBox.StandardButton.Yes:
            bookmark_id = item.data(Qt.ItemDataRole.UserRole)
            self.db.delete_bookmark(bookmark_id)
            self.load_bookmarks()

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
            
        menu = QMenu(self)
        play_action = QAction(tr("bookmarks.play"), self)
        play_action.triggered.connect(lambda: self.on_item_double_clicked(item))
        menu.addAction(play_action)
        
        edit_action = QAction(tr("bookmarks.edit"), self)
        edit_action.triggered.connect(self.edit_bookmark)
        menu.addAction(edit_action)
        
        del_action = QAction(tr("bookmarks.delete"), self)
        del_action.triggered.connect(self.delete_bookmark)
        menu.addAction(del_action)
        
        menu.exec(self.list_widget.mapToGlobal(pos))
