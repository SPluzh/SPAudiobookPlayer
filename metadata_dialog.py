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

LANGUAGES_MAP = {
    "ru": "Русский (ru)",
    "en": "English (en)",
    "de": "Deutsch (de)",
    "fr": "Français (fr)",
    "es": "Español (es)",
    "it": "Italiano (it)",
    "uk": "Українська (uk)",
    "be": "Беларуская (be)",
    "zh": "中文 (zh)",
    "ja": "日本語 (ja)",
    "ko": "한국어 (ko)",
    "pl": "Polski (pl)",
    "tr": "Türkçe (tr)",
    "ar": "العربية (ar)",
    "hi": "हिन्दी (hi)",
    "he": "עברית (he)",
    "hy": "Հայերեն (hy)",
    "th": "ไทย (th)",
    "cs": "Čeština (cs)",
    "fi": "Suomi (fi)",
    "ro": "Română (ro)",
}

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
                
                pen = QPen(accent_color, 4)
                painter.setPen(pen)
                border_rect = QRectF(2.0, 2.0, self.width() - 4.0, self.height() - 4.0)
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
        self.resize(480, 500)
        
        self.current_data = self.db.get_audiobook_metadata(self.audiobook_id)
        if not self.current_data:
            # If no data found (e.g. deleted), close immediately
            self.reject()
            return

        self.setup_ui()
        self.load_suggestions()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
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
        layout.addWidget(scroll_area)
        
        # Form fields
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Author Field
        self.author_label = QLabel(tr("metadata.author"))
        self.author_combo = QComboBox()
        self.author_combo.setEditable(True)
        # Prevent resizing based on content
        self.author_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.author_combo.setMinimumWidth(300)
        # Allow inserting any text
        self.author_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.author_combo.setCurrentText(self.current_data.get('author') or "")
        form_layout.addRow(self.author_label, self.author_combo)
        
        # Title Field
        self.title_label = QLabel(tr("metadata.title"))
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        self.title_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.title_combo.setMinimumWidth(300)
        self.title_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.title_combo.setCurrentText(self.current_data.get('title') or "")
        form_layout.addRow(self.title_label, self.title_combo)
        
        # Narrator Field
        self.narrator_label = QLabel(tr("metadata.narrator"))
        self.narrator_combo = QComboBox()
        self.narrator_combo.setEditable(True)
        self.narrator_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.narrator_combo.setMinimumWidth(300)
        self.narrator_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.narrator_combo.setCurrentText(self.current_data.get('narrator') or "")
        form_layout.addRow(self.narrator_label, self.narrator_combo)

        # Language Field
        self.language_label = QLabel(tr("metadata.language", default="Book Language:"))
        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.language_combo.setMinimumWidth(300)
        self.language_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        form_layout.addRow(self.language_label, self.language_combo)

        # Year Written Field
        self.year_written_label = QLabel(tr("metadata.year_written", default="Year Written:"))
        self.year_written_combo = QComboBox()
        self.year_written_combo.setEditable(True)
        self.year_written_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.year_written_combo.setMinimumWidth(300)
        self.year_written_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        form_layout.addRow(self.year_written_label, self.year_written_combo)

        # Year Recorded Field
        self.year_recorded_label = QLabel(tr("metadata.year_recorded", default="Year Recorded:"))
        self.year_recorded_combo = QComboBox()
        self.year_recorded_combo.setEditable(True)
        self.year_recorded_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.year_recorded_combo.setMinimumWidth(300)
        self.year_recorded_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        form_layout.addRow(self.year_recorded_label, self.year_recorded_combo)
        
        layout.addLayout(form_layout)
        
        layout.addStretch()
        
        # Standard Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        
        # Customize button text via translation keys
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setText(tr("metadata.save", default="Save"))
        
        # Get standard button height from the style or size hint
        std_height = save_btn.sizeHint().height()
        if std_height <= 0:
            std_height = 36
            
        # Custom cover/tags buttons
        # Open folder button
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setObjectName("openFolderBtn")
        self.open_folder_btn.setIcon(get_icon("context_open_folder"))
        self.open_folder_btn.setIconSize(QSize(20, 20))
        self.open_folder_btn.setFixedSize(std_height, std_height)
        self.open_folder_btn.setToolTip(tr("metadata.open_folder_tooltip", default="Open folder containing this book"))
        self.open_folder_btn.clicked.connect(self.on_open_folder)
        
        # Refresh button
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("refreshCoversBtn")
        self.refresh_btn.setIcon(get_icon("menu_reload"))
        self.refresh_btn.setIconSize(QSize(20, 20))
        self.refresh_btn.setFixedSize(std_height, std_height)
        self.refresh_btn.setToolTip(tr("metadata.refresh_covers_tooltip", default="Scan folder for new covers"))
        self.refresh_btn.clicked.connect(self.on_refresh_covers)
        
        # From Tags button
        self.from_tags_btn = QPushButton()
        self.from_tags_btn.setObjectName("fromTagsBtn")
        self.from_tags_btn.setIcon(get_icon("context_tags"))
        self.from_tags_btn.setIconSize(QSize(20, 20))
        self.from_tags_btn.setFixedSize(std_height, std_height)
        self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip", default="Fill fields from file tags (ID3)"))
        self.from_tags_btn.clicked.connect(self.fill_from_tags)
        
        # Combine buttons at the bottom: custom buttons on the left, standard on the right
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)
        
        bottom_layout.addWidget(self.open_folder_btn)
        bottom_layout.addWidget(self.refresh_btn)
        bottom_layout.addWidget(self.from_tags_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(buttons)
        
        layout.addLayout(bottom_layout)
        
    def load_suggestions(self):
        """Populate comboboxes with existing values from the database"""
        self.author_combo.blockSignals(True)
        self.title_combo.blockSignals(True)
        self.narrator_combo.blockSignals(True)
        self.language_combo.blockSignals(True)
        self.year_written_combo.blockSignals(True)
        self.year_recorded_combo.blockSignals(True)
        
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

        # Populate language combo
        lang_items = []
        seen_langs = set()
        
        curr_lang = self.current_data.get('language') or ""
        curr_lang_display = LANGUAGES_MAP.get(curr_lang, curr_lang)
        
        if curr_lang_display:
            lang_items.append(curr_lang_display)
            seen_langs.add(curr_lang_display)
            
        for code, display in LANGUAGES_MAP.items():
            if display not in seen_langs:
                lang_items.append(display)
                seen_langs.add(display)
                
        self.language_combo.addItems(lang_items)
        self.language_combo.setCurrentText(curr_lang_display)

        # Populate Year Written combo
        written_items = []
        seen_written = set()
        curr_written = self.current_data.get('year_written') or ""
        if curr_written:
            written_items.append(curr_written)
            seen_written.add(curr_written)
        tag_year = self.current_data.get('tag_year') or ""
        if tag_year and tag_year not in seen_written:
            written_items.append(tag_year)
            seen_written.add(tag_year)
        for tag in local_tags:
            if tag.isdigit() and len(tag) == 4 and tag not in seen_written:
                written_items.append(tag)
                seen_written.add(tag)
        self.year_written_combo.addItems(written_items)
        self.year_written_combo.setCurrentText(curr_written)

        # Populate Year Recorded combo
        recorded_items = []
        seen_recorded = set()
        curr_recorded = self.current_data.get('year_recorded') or ""
        if curr_recorded:
            recorded_items.append(curr_recorded)
            seen_recorded.add(curr_recorded)
        if tag_year and tag_year not in seen_recorded:
            recorded_items.append(tag_year)
            seen_recorded.add(tag_year)
        for tag in local_tags:
            if tag.isdigit() and len(tag) == 4 and tag not in seen_recorded:
                recorded_items.append(tag)
                seen_recorded.add(tag)
        self.year_recorded_combo.addItems(recorded_items)
        self.year_recorded_combo.setCurrentText(curr_recorded)
        
        self.author_combo.setCurrentText(self.current_data.get('author') or "")
        self.title_combo.setCurrentText(self.current_data.get('title') or "")
        self.narrator_combo.setCurrentText(self.current_data.get('narrator') or "")
            
        self.author_combo.blockSignals(False)
        self.title_combo.blockSignals(False)
        self.narrator_combo.blockSignals(False)
        self.language_combo.blockSignals(False)
        self.year_written_combo.blockSignals(False)
        self.year_recorded_combo.blockSignals(False)

    def fill_from_tags(self):
        """Fill entry fields using the extracted ID3 tags"""
        if self.current_data:
            tag_author = self.current_data.get('tag_author')
            tag_title = self.current_data.get('tag_title')
            tag_narrator = self.current_data.get('tag_narrator')
            tag_year = self.current_data.get('tag_year')
            
            if tag_author:
                self.author_combo.setCurrentText(tag_author)
            if tag_title:
                self.title_combo.setCurrentText(tag_title)
            if tag_narrator:
                self.narrator_combo.setCurrentText(tag_narrator)
            if tag_year:
                self.year_recorded_combo.setCurrentText(tag_year)
                
    def update_texts(self):
        """Update UI texts when language changes"""
        self.setWindowTitle(tr("metadata.edit_title"))
        if hasattr(self, 'author_label') and self.author_label:
            self.author_label.setText(tr("metadata.author"))
        if hasattr(self, 'title_label') and self.title_label:
            self.title_label.setText(tr("metadata.title"))
        if hasattr(self, 'narrator_label') and self.narrator_label:
            self.narrator_label.setText(tr("metadata.narrator"))
        if hasattr(self, 'language_label') and self.language_label:
            self.language_label.setText(tr("metadata.language", default="Book Language:"))
        if hasattr(self, 'year_written_label') and self.year_written_label:
            self.year_written_label.setText(tr("metadata.year_written", default="Year Written:"))
        if hasattr(self, 'year_recorded_label') and self.year_recorded_label:
            self.year_recorded_label.setText(tr("metadata.year_recorded", default="Year Recorded:"))

        if hasattr(self, 'from_tags_btn') and self.from_tags_btn:
            self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip", default="Fill fields from file tags (ID3)"))
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.setToolTip(tr("metadata.refresh_covers_tooltip", default="Scan folder for new covers"))
        if hasattr(self, 'open_folder_btn') and self.open_folder_btn:
            self.open_folder_btn.setToolTip(tr("metadata.open_folder_tooltip", default="Open folder containing this book"))

    def get_data(self):
        """Return the entered metadata as a tuple"""
        lang_text = self.language_combo.currentText().strip()
        save_lang = lang_text
        for code, display in LANGUAGES_MAP.items():
            if lang_text == display or lang_text.lower() == code:
                save_lang = code
                break

        return (
            self.author_combo.currentText().strip(),
            self.title_combo.currentText().strip(),
            self.narrator_combo.currentText().strip(),
            save_lang,
            self.year_written_combo.currentText().strip(),
            self.year_recorded_combo.currentText().strip()
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

    def apply_blur(self):
        """Proxy blur request to parent window if supported"""
        if self.parent() and hasattr(self.parent(), 'apply_blur'):
            self.parent().apply_blur()

    def remove_blur(self):
        """Proxy blur remove request to parent window if supported"""
        if self.parent() and hasattr(self.parent(), 'remove_blur'):
            self.parent().remove_blur()

    def accept(self):
        """Save selected cover and close the dialog"""
        self.db.set_selected_audiobook_cover(self.audiobook_id, self.selected_cover_id)
        super().accept()
