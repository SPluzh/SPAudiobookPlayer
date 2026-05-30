from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QDialogButtonBox, QMessageBox, QFormLayout,
    QScrollArea, QWidget, QApplication
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
        self.resize(480, 380)
        
        self.current_data = self.db.get_audiobook_metadata(self.audiobook_id)
        if not self.current_data:
            # If no data found (e.g. deleted), close immediately
            self.reject()
            return

        self.setup_ui()
        self.load_suggestions()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title/label for cover selection
        cover_label = QLabel(tr("metadata.select_cover", default="Select Cover:"))
        layout.addWidget(cover_label)
        
        # Horizontal layout to hold button panel on the left and scroll_area on the right
        covers_layout = QHBoxLayout()
        covers_layout.setSpacing(10)
        
        # Vertical button layout
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(4)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Open folder button
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setObjectName("openFolderBtn")
        self.open_folder_btn.setIcon(get_icon("context_open_folder"))
        self.open_folder_btn.setIconSize(QSize(20, 20))
        self.open_folder_btn.setFixedSize(36, 36)
        self.open_folder_btn.setToolTip(tr("metadata.open_folder_tooltip", default="Open folder containing this book"))
        self.open_folder_btn.clicked.connect(self.on_open_folder)
        buttons_layout.addWidget(self.open_folder_btn)
        
        # Refresh button to the left of the cover list
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("refreshCoversBtn")
        self.refresh_btn.setIcon(get_icon("menu_reload"))
        self.refresh_btn.setIconSize(QSize(20, 20))
        self.refresh_btn.setFixedSize(36, 36)
        self.refresh_btn.setToolTip(tr("metadata.refresh_covers_tooltip", default="Scan folder for new covers"))
        self.refresh_btn.clicked.connect(self.on_refresh_covers)
        buttons_layout.addWidget(self.refresh_btn)
        
        # From Tags button under the refresh button
        self.from_tags_btn = QPushButton()
        self.from_tags_btn.setObjectName("fromTagsBtn")
        self.from_tags_btn.setIcon(get_icon("context_tags"))
        self.from_tags_btn.setIconSize(QSize(20, 20))
        self.from_tags_btn.setFixedSize(36, 36)
        self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip", default="Fill fields from file tags (ID3)"))
        self.from_tags_btn.clicked.connect(self.fill_from_tags)
        buttons_layout.addWidget(self.from_tags_btn)
        
        covers_layout.addLayout(buttons_layout)
        
        # Scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(140)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setObjectName("coverScrollArea")
        
        scroll_content = QWidget()
        scroll_content.setObjectName("coverScrollContent")
        self.scroll_layout = QHBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10)
        
        self.thumbnail_widgets = []
        
        # Load cover thumbnails
        self.populate_covers()
        
        scroll_area.setWidget(scroll_content)
        covers_layout.addWidget(scroll_area, 1)
        layout.addLayout(covers_layout)
        
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
        if hasattr(self, 'from_tags_btn') and self.from_tags_btn:
            self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip", default="Fill fields from file tags (ID3)"))
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.setToolTip(tr("metadata.refresh_covers_tooltip", default="Scan folder for new covers"))
        if hasattr(self, 'open_folder_btn') and self.open_folder_btn:
            self.open_folder_btn.setToolTip(tr("metadata.open_folder_tooltip", default="Open folder containing this book"))

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

    def populate_covers(self):
        """Load cover thumbnails from database and construct widgets"""
        # Clear existing thumbnail widgets
        if hasattr(self, 'thumbnail_widgets') and self.thumbnail_widgets:
            for widget in self.thumbnail_widgets:
                widget.deleteLater()
        self.thumbnail_widgets = []
        
        # Clear layout contents
        if hasattr(self, 'scroll_layout') and self.scroll_layout:
            while self.scroll_layout.count():
                item = self.scroll_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                    
        # Load covers from database
        self.covers = self.db.get_audiobook_covers(self.audiobook_id)
        
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
            self.scroll_layout.addWidget(thumb)
            self.thumbnail_widgets.append(thumb)
            
        # Add "No Cover" option at the end
        no_cover_thumb = CoverThumbnailWidget(
            cover_id=None,
            image_path=None,
            is_selected=(self.selected_cover_id is None),
            parent=self
        )
        no_cover_thumb.clicked.connect(self.on_cover_clicked)
        self.scroll_layout.addWidget(no_cover_thumb)
        self.thumbnail_widgets.append(no_cover_thumb)
        
        self.scroll_layout.addStretch()

    def on_open_folder(self):
        """Open the folder containing the current audiobook in the OS file explorer by reusing the parent's open_folder method"""
        try:
            import sqlite3
            from utils import tr
            
            conn = sqlite3.connect(self.db.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM audiobooks WHERE id = ?", (self.audiobook_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                relative_path = row[0]
                if self.parent() and hasattr(self.parent(), 'open_folder'):
                    self.parent().open_folder(relative_path)
                else:
                    QMessageBox.warning(self, tr("window.title"), "Parent window cannot open the folder.")
        except Exception as e:
            from utils import tr
            QMessageBox.critical(self, tr("window.title"), f"Error opening folder: {e}")

    def on_refresh_covers(self):
        """Scan the current audiobook folder for new covers and refresh the list"""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            import sqlite3
            from scanner import AudiobookScanner
            
            # Fetch the audiobook path and selected cover path from DB
            conn = sqlite3.connect(self.db.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT path, cached_cover_path FROM audiobooks WHERE id = ?", (self.audiobook_id,))
            row = cursor.fetchone()
            
            if row:
                relative_path, current_cached_cover = row[0], row[1]
                
                # Reconstruct the absolute path of the audiobook
                library_root = ""
                if self.parent() and hasattr(self.parent(), 'config') and self.parent().config:
                    library_root = self.parent().config.get("default_path", "")
                
                if not library_root:
                    import configparser
                    from utils import get_base_path
                    config = configparser.ConfigParser()
                    config_file = get_base_path() / "resources" / "settings.ini"
                    if config_file.exists():
                        config.read(config_file, encoding='utf-8')
                        library_root = config.get('Paths', 'library_path', fallback='')
                
                if library_root:
                    absolute_path = Path(library_root) / relative_path
                    if absolute_path.exists():
                        # Instantiate AudiobookScanner and run rescanning of covers
                        scanner = AudiobookScanner()
                        scanner._scan_and_save_all_covers(
                            conn=conn,
                            directory=absolute_path,
                            key=relative_path,
                            audiobook_id=self.audiobook_id,
                            selected_cover_cached_path=current_cached_cover
                        )
                        conn.commit()
            conn.close()
            
            # Refresh UI
            self.populate_covers()
            
        except Exception as e:
            QMessageBox.critical(self, tr("error"), f"Failed to refresh covers: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def accept(self):
        """Save selected cover and close the dialog"""
        self.db.set_selected_audiobook_cover(self.audiobook_id, self.selected_cover_id)
        super().accept()
