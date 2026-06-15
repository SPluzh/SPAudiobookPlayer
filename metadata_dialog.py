from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QDialogButtonBox, QMessageBox, QFormLayout,
    QScrollArea, QWidget, QApplication, QCheckBox, QLineEdit, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRectF, QThread
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from pathlib import Path
import sys

try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from translations import tr
from utils import get_icon

LANGUAGES_MAP = {
    "ar": "العربية (ar)",
    "be": "Беларуская (be)",
    "cs": "Čeština (cs)",
    "de": "Deutsch (de)",
    "en": "English (en)",
    "es": "Español (es)",
    "fi": "Suomi (fi)",
    "fr": "Français (fr)",
    "he": "עברית (he)",
    "hi": "हिन्दी (hi)",
    "hy": "Հայերեն (hy)",
    "it": "Italiano (it)",
    "ja": "日本語 (ja)",
    "ko": "한국어 (ko)",
    "pl": "Polski (pl)",
    "ro": "Română (ro)",
    "ru": "Русский (ru)",
    "th": "ไทย (th)",
    "tr": "Türkçe (tr)",
    "uk": "Українська (uk)",
    "zh": "中文 (zh)",
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
        
        if isinstance(audiobook_id, (list, tuple, set)):
            self.audiobook_ids = list(audiobook_id)
            self.is_bulk = True
            self.audiobook_id = self.audiobook_ids[0] if self.audiobook_ids else None
        else:
            self.audiobook_id = audiobook_id
            self.audiobook_ids = [audiobook_id] if audiobook_id else []
            self.is_bulk = False
            
        self.setWindowTitle(tr("metadata.edit_title"))
        self.setModal(True)
        if self.is_bulk:
            self.resize(480, 320)
        else:
            self.resize(480, 500)
        
        if not self.audiobook_id:
            self.reject()
            return
            
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
        
        if self.is_bulk:
            scroll_area.setVisible(False)
        
        # Form fields
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Helper to wrap combobox with QCheckBox
        def wrap_field_with_checkbox(combo, default_checked=False):
            cb = QCheckBox()
            cb.setChecked(not self.is_bulk or default_checked)
            cb.setVisible(self.is_bulk)
            cb.toggled.connect(combo.setEnabled)
            if self.is_bulk:
                combo.setEnabled(cb.isChecked())
            
            field_layout = QHBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(6)
            field_layout.addWidget(combo, 1)
            field_layout.addWidget(cb)
            return cb, field_layout

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
        self.author_cb, author_layout_field = wrap_field_with_checkbox(self.author_combo, False)
        form_layout.addRow(self.author_label, author_layout_field)
        
        # Title Field
        self.title_label = QLabel(tr("metadata.title"))
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        self.title_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.title_combo.setMinimumWidth(300)
        self.title_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.title_combo.setCurrentText(self.current_data.get('title') or "")
        self.title_cb, title_layout_field = wrap_field_with_checkbox(self.title_combo, False)
        form_layout.addRow(self.title_label, title_layout_field)
        
        # Narrator Field
        self.narrator_label = QLabel(tr("metadata.narrator"))
        self.narrator_combo = QComboBox()
        self.narrator_combo.setEditable(True)
        self.narrator_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.narrator_combo.setMinimumWidth(300)
        self.narrator_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.narrator_combo.setCurrentText(self.current_data.get('narrator') or "")
        self.narrator_cb, narrator_layout_field = wrap_field_with_checkbox(self.narrator_combo, False)
        form_layout.addRow(self.narrator_label, narrator_layout_field)

        # Language Field
        self.language_label = QLabel(tr("metadata.language", default="Book Language:"))
        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.language_combo.setMinimumWidth(300)
        self.language_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.language_cb, language_layout_field = wrap_field_with_checkbox(self.language_combo, True)
        form_layout.addRow(self.language_label, language_layout_field)

        # Year Written Field
        self.year_written_label = QLabel(tr("metadata.year_written", default="Year Written:"))
        self.year_written_combo = QComboBox()
        self.year_written_combo.setEditable(True)
        self.year_written_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.year_written_combo.setMinimumWidth(300)
        self.year_written_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.year_written_cb, year_written_layout_field = wrap_field_with_checkbox(self.year_written_combo, False)
        form_layout.addRow(self.year_written_label, year_written_layout_field)

        # Year Recorded Field
        self.year_recorded_label = QLabel(tr("metadata.year_recorded", default="Year Recorded:"))
        self.year_recorded_combo = QComboBox()
        self.year_recorded_combo.setEditable(True)
        self.year_recorded_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.year_recorded_combo.setMinimumWidth(300)
        self.year_recorded_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.year_recorded_cb, year_recorded_layout_field = wrap_field_with_checkbox(self.year_recorded_combo, False)
        form_layout.addRow(self.year_recorded_label, year_recorded_layout_field)
        
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
        if self.is_bulk:
            self.open_folder_btn.setVisible(False)
        
        # Refresh button
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("refreshCoversBtn")
        self.refresh_btn.setIcon(get_icon("menu_reload"))
        self.refresh_btn.setIconSize(QSize(20, 20))
        self.refresh_btn.setFixedSize(std_height, std_height)
        self.refresh_btn.setToolTip(tr("metadata.refresh_covers_tooltip", default="Scan folder for new covers"))
        self.refresh_btn.clicked.connect(self.on_refresh_covers)
        if self.is_bulk:
            self.refresh_btn.setVisible(False)
        
        # From Tags button
        self.from_tags_btn = QPushButton()
        self.from_tags_btn.setObjectName("fromTagsBtn")
        self.from_tags_btn.setIcon(get_icon("context_tags"))
        self.from_tags_btn.setIconSize(QSize(20, 20))
        self.from_tags_btn.setFixedSize(std_height, std_height)
        self.from_tags_btn.setToolTip(tr("metadata.from_tags_tooltip", default="Fill fields from file tags (ID3)"))
        self.from_tags_btn.clicked.connect(self.fill_from_tags)
        if self.is_bulk:
            self.from_tags_btn.setVisible(False)
        
        # Search Cover button
        self.search_cover_btn = QPushButton()
        self.search_cover_btn.setObjectName("searchCoverBtn")
        self.search_cover_btn.setIcon(get_icon("menu_scan"))
        self.search_cover_btn.setIconSize(QSize(20, 20))
        self.search_cover_btn.setFixedSize(std_height, std_height)
        self.search_cover_btn.setToolTip(tr("metadata.search_cover_tooltip", default="Search covers online"))
        self.search_cover_btn.clicked.connect(self.on_search_cover)
        if self.is_bulk:
            self.search_cover_btn.setVisible(False)
        
        # Combine buttons at the bottom: custom buttons on the left, standard on the right
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)
        
        bottom_layout.addWidget(self.open_folder_btn)
        bottom_layout.addWidget(self.refresh_btn)
        bottom_layout.addWidget(self.from_tags_btn)
        bottom_layout.addWidget(self.search_cover_btn)
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

    def get_enabled_fields(self):
        """Return a dict of enabled metadata fields and their values"""
        author, title, narrator, language, year_written, year_recorded = self.get_data()
        
        fields = {}
        if self.author_cb.isChecked():
            fields['author'] = author
        if self.title_cb.isChecked():
            fields['title'] = title
        if self.narrator_cb.isChecked():
            fields['narrator'] = narrator
        if self.language_cb.isChecked():
            fields['language'] = language
        if self.year_written_cb.isChecked():
            fields['year_written'] = year_written
        if self.year_recorded_cb.isChecked():
            fields['year_recorded'] = year_recorded
            
        return fields


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
        if self.is_bulk:
            return
            
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

    def get_audiobook_dir(self):
        """Return the absolute Path to the audiobook directory"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM audiobooks WHERE id = ?", (self.audiobook_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                relative_path = row[0]
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
                    return Path(library_root) / relative_path
        except Exception as e:
            print(f"Error getting audiobook directory: {e}")
        return None

    def apply_blur(self):
        """Walk parent chain to find and call apply_blur on the main window"""
        print("[MetadataDialog] apply_blur requested")
        p = self.parent()
        while p:
            if hasattr(p, 'apply_blur'):
                print(f"[MetadataDialog] delegating apply_blur to parent {p}")
                p.apply_blur()
                break
            p = p.parent()

    def remove_blur(self):
        """Walk parent chain to find and call remove_blur on the main window"""
        print("[MetadataDialog] remove_blur requested")
        p = self.parent()
        while p:
            if hasattr(p, 'remove_blur'):
                print(f"[MetadataDialog] delegating remove_blur to parent {p}")
                p.remove_blur()
                break
            p = p.parent()

    def on_search_cover(self):
        """Open the online cover search dialog and refresh covers on success"""
        print("[MetadataDialog] on_search_cover clicked")
        audiobook_dir = self.get_audiobook_dir()
        if not audiobook_dir:
            print("[MetadataDialog] Could not determine audiobook directory, falling back to temp directory")
            audiobook_dir = Path("c:/Users/user/Desktop/python/SPAudiobookPlayer/data/temp")
            try:
                audiobook_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"[MetadataDialog] Failed to create fallback temp directory: {e}")
            
        author = self.author_combo.currentText().strip()
        title = self.title_combo.currentText().strip()
        initial_query = f"{author} {title}".strip()
        print(f"[MetadataDialog] Search query: '{initial_query}', destination: {audiobook_dir}")
        
        try:
            dialog = CoverSearchDialog(initial_query, audiobook_dir, self)
            print("[MetadataDialog] CoverSearchDialog created successfully")
        except Exception as e:
            import traceback
            print("[MetadataDialog] Error creating CoverSearchDialog:")
            traceback.print_exc()
            QMessageBox.critical(self, tr("error"), f"Failed to initialize search: {e}")
            return
            
        self.apply_blur()
        try:
            print("[MetadataDialog] Executing CoverSearchDialog...")
            if dialog.exec() == QDialog.DialogCode.Accepted:
                print("[MetadataDialog] CoverSearchDialog accepted, refreshing covers")
                self.on_refresh_covers()
            else:
                print("[MetadataDialog] CoverSearchDialog rejected/cancelled")
        except Exception as e:
            import traceback
            print("[MetadataDialog] Error during CoverSearchDialog execution:")
            traceback.print_exc()
            QMessageBox.critical(self, tr("error"), f"Error during search execution: {e}")
        finally:
            self.remove_blur()

    def accept(self):
        """Save selected cover and close the dialog"""
        if not self.is_bulk:
            self.db.set_selected_audiobook_cover(self.audiobook_id, self.selected_cover_id)
        super().accept()


class SearchWorker(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query):
        super().__init__()
        self.query = query
        
    def run(self):
        import traceback
        import time
        try:
            print(f"[SearchWorker] Starting search for query: '{self.query}'")
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            
            litres_results = []
            direct_results = []
            
            try:
                print(f"[SearchWorker] Querying LitresScraper directly...")
                from litres_scraper import LitresScraper
                scraper = LitresScraper()
                litres_results = scraper.search(self.query)
                print(f"[SearchWorker] LitresScraper found {len(litres_results)} results")
                if litres_results:
                    for r in litres_results:
                        r['source'] = 'Litres'
                    self.results_found.emit(litres_results)
            except Exception as e:
                print(f"[SearchWorker] LitresScraper failed: {e}")
            
            try:
                print(f"[SearchWorker] Querying StorytelScraper directly...")
                from storytel_scraper import StorytelScraper
                scraper = StorytelScraper()
                storytel_res = scraper.search(self.query)
                print(f"[SearchWorker] StorytelScraper found {len(storytel_res)} results")
                if storytel_res:
                    for r in storytel_res:
                        r['source'] = 'Storytel'
                    direct_results.extend(storytel_res)
                    self.results_found.emit(storytel_res)
            except Exception as e:
                print(f"[SearchWorker] StorytelScraper failed: {e}")

            try:
                print(f"[SearchWorker] Querying GoodreadsScraper directly...")
                from goodreads_scraper import GoodreadsScraper
                scraper = GoodreadsScraper()
                goodreads_res = scraper.search(self.query)
                print(f"[SearchWorker] GoodreadsScraper found {len(goodreads_res)} results")
                if goodreads_res:
                    for r in goodreads_res:
                        r['source'] = 'Goodreads'
                    direct_results.extend(goodreads_res)
                    self.results_found.emit(goodreads_res)
            except Exception as e:
                print(f"[SearchWorker] GoodreadsScraper failed: {e}")

            try:
                print(f"[SearchWorker] Querying AudibleScraper...")
                from audible_scraper import AudibleScraper
                scraper = AudibleScraper()
                audible_res = scraper.search(self.query)
                print(f"[SearchWorker] AudibleScraper found {len(audible_res)} results")
                if audible_res:
                    for r in audible_res:
                        r['source'] = 'Audible'
                    direct_results.extend(audible_res)
                    self.results_found.emit(audible_res)
            except Exception as e:
                print(f"[SearchWorker] AudibleScraper failed: {e}")
            
            
            # Now run general search via DDGS
            general_results = []
            try:
                print(f"[SearchWorker] Querying general search via DDGS...")
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        with DDGS() as ddgs:
                            general_results = list(ddgs.images(self.query, safesearch='off', max_results=60))
                        if len(general_results) > 1:
                            break
                        print(f"[SearchWorker] General DDGS attempt {attempt + 1} returned {len(general_results)} results. Retrying...")
                    except Exception as e:
                        print(f"[SearchWorker] General DDGS attempt {attempt + 1} failed: {e}")
                        if attempt == max_attempts - 1 and not litres_results and not direct_results:
                            raise e
                    if attempt < max_attempts - 1:
                        time.sleep(1.0)
                
                for r in general_results:
                    r['source'] = 'Web'
            except Exception as e:
                print(f"[SearchWorker] DDGS general search failed: {e}")
                if not litres_results and not direct_results:
                    raise e
                    
            # Merge results, keeping litres/direct results first
            seen_images = set()
            results = []
            
            for res in litres_results:
                img_url = res.get('image')
                if img_url and img_url not in seen_images:
                    seen_images.add(img_url)
                    results.append(res)
                    
            for res in direct_results:
                img_url = res.get('image')
                if img_url and img_url not in seen_images:
                    seen_images.add(img_url)
                    results.append(res)
                    
            for res in general_results:
                img_url = res.get('image')
                if img_url and img_url not in seen_images:
                    seen_images.add(img_url)
                    results.append(res)
                    
            print(f"[SearchWorker] Search completed successfully, found {len(results)} results")
            self.results_found.emit(results)
        except Exception as e:
            print(f"[SearchWorker] Exception during search:")
            traceback.print_exc()
            self.error_occurred.emit(str(e))


class PreviewLoader(QThread):
    preview_ready = pyqtSignal(int, QPixmap)
    
    def __init__(self, index_url_pairs):
        super().__init__()
        self.index_url_pairs = index_url_pairs
        self.running = True
        
    def run(self):
        import urllib.request
        import traceback
        print(f"[PreviewLoader] Starting loading of {len(self.index_url_pairs)} previews")
        for idx, url in self.index_url_pairs:
            if not self.running:
                print("[PreviewLoader] Running flag set to False, stopping preview load")
                break
            try:
                print(f"[PreviewLoader] Downloading preview {idx + 1}/{len(self.index_url_pairs)} (index {idx}): {url}")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read()
                from PyQt6.QtGui import QImage
                image = QImage.fromData(data)
                if not image.isNull():
                    pixmap = QPixmap.fromImage(image)
                    self.preview_ready.emit(idx, pixmap)
                else:
                    print(f"[PreviewLoader] Image data is null for: {url}")
            except Exception as e:
                print(f"[PreviewLoader] Failed to download preview {idx} ({url}): {e}")


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int, str)
    
    def __init__(self, urls, destination_dir):
        super().__init__()
        self.urls = urls
        self.destination_dir = Path(destination_dir)
        
    def run(self):
        import traceback
        try:
            print(f"[DownloadWorker] Starting cover download of {len(self.urls)} images to {self.destination_dir}")
            if not self.destination_dir.exists():
                try:
                    self.destination_dir.mkdir(parents=True, exist_ok=True)
                    print(f"[DownloadWorker] Created directory: {self.destination_dir}")
                except Exception as e:
                    print(f"[DownloadWorker] Failed to create folder: {e}")
                    self.finished_signal.emit(0, f"Cannot create folder: {e}")
                    return
                    
            import urllib.request
            from urllib.parse import urlparse
            import posixpath
            
            success_count = 0
            error_msg = ""
            total = len(self.urls)
            
            for idx, url in enumerate(self.urls):
                self.progress.emit(idx + 1, total)
                try:
                    url_path = urlparse(url).path
                    ext = posixpath.splitext(url_path)[1].lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
                        ext = '.jpg'
                        
                    base_name = "cover"
                    dest_file = self.destination_dir / f"{base_name}{ext}"
                    
                    if dest_file.exists():
                        counter = 1
                        while True:
                            dest_file = self.destination_dir / f"{base_name}_{counter}{ext}"
                            if not dest_file.exists():
                                break
                            counter += 1
                            
                    print(f"[DownloadWorker] Downloading {idx + 1}/{total} from {url} to {dest_file}")
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                    with urllib.request.urlopen(req, timeout=15) as response:
                        data = response.read()
                        
                    with open(dest_file, 'wb') as f:
                        f.write(data)
                    
                    print(f"[DownloadWorker] Downloaded and saved: {dest_file}")
                    success_count += 1
                except Exception as e:
                    print(f"[DownloadWorker] Error downloading image from {url}:")
                    traceback.print_exc()
                    error_msg = f"Failed to download some covers: {e}"
                    
            self.finished_signal.emit(success_count, error_msg if success_count == 0 else "")
        except Exception as e:
            print("[DownloadWorker] Critical error inside worker thread:")
            traceback.print_exc()
            self.finished_signal.emit(0, str(e))


class HoverPreviewPopup(QLabel):
    def __init__(self, pixmap, parent=None):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        
        from styles import StyleManager
        try:
            _, accent_color = StyleManager.get_theme_property("delegate_accent")
            accent_hex = accent_color.name()
        except Exception:
            accent_hex = "#2ecc71"
            
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #1a1a1a;
                border: 2px solid {accent_hex};
                border-radius: 8px;
            }}
        """)
        
        scaled = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)
        self.setFixedSize(scaled.size() + QSize(4, 4))


class CoverSearchResultWidget(QWidget):
    clicked = pyqtSignal()
    
    def __init__(self, index, result_data, parent=None):
        super().__init__(parent)
        self.index = index
        self.result_data = result_data
        self.is_selected = False
        self.full_pixmap = None
        self.hover_popup = None
        
        self.setFixedSize(125, 155)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        
        self.image_label = QLabel()
        self.image_label.setFixedSize(115, 115)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1e1e1e; border-radius: 4px;")
        
        from utils import get_base_path
        from utils import load_icon
        default_cover_path = get_base_path() / "resources" / "icons" / "default_cover.png"
        if default_cover_path.exists():
            cover_icon = load_icon(default_cover_path, 100, force_square=True)
            if cover_icon and not cover_icon.isNull():
                self.image_label.setPixmap(cover_icon.pixmap(100, 100))
        
        layout.addWidget(self.image_label)
        
        source = result_data.get('source', '')
        if not source:
            from urllib.parse import urlparse
            domain = urlparse(result_data.get('image', '')).netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            if len(domain) > 15:
                domain = domain[:12] + "..."
            source = domain
        elif source == 'Web':
            from urllib.parse import urlparse
            domain = urlparse(result_data.get('image', '')).netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            if len(domain) > 12:
                domain = domain[:9] + "..."
            source = f"Web ({domain})"
            
        width = result_data.get('width', '?')
        height = result_data.get('height', '?')
        
        self.info_label = QLabel(f"<b>{source}</b><br>{width}x{height}")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #aaaaaa; font-size: 9px;")
        layout.addWidget(self.info_label)
        
    def set_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.full_pixmap = pixmap
            scaled_pixmap = pixmap.scaled(115, 115, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            
    def set_selected(self, selected):
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"[CoverSearchResultWidget] Widget at index {self.index} clicked")
            self.clicked.emit()
            
    def enterEvent(self, event):
        super().enterEvent(event)
        if self.full_pixmap and not self.full_pixmap.isNull():
            self.show_hover_popup()
            
    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hide_hover_popup()
        
    def hideEvent(self, event):
        super().hideEvent(event)
        self.hide_hover_popup()
        
    def closeEvent(self, event):
        self.hide_hover_popup()
        super().closeEvent(event)
        
    def show_hover_popup(self):
        self.hide_hover_popup()
        if not self.full_pixmap or self.full_pixmap.isNull():
            return
            
        self.hover_popup = HoverPreviewPopup(self.full_pixmap, self)
        
        widget_rect = self.rect()
        global_pos = self.mapToGlobal(widget_rect.topRight())
        
        screen_geo = QApplication.primaryScreen().geometry()
        popup_size = self.hover_popup.size()
        
        x = global_pos.x() + 10
        if x + popup_size.width() > screen_geo.right():
            x = self.mapToGlobal(widget_rect.topLeft()).x() - popup_size.width() - 10
            
        y = self.mapToGlobal(widget_rect.topLeft()).y()
        if y + popup_size.height() > screen_geo.bottom():
            y = screen_geo.bottom() - popup_size.height() - 10
            
        self.hover_popup.move(max(0, x), max(0, y))
        self.hover_popup.show()
        
    def hide_hover_popup(self):
        if self.hover_popup:
            try:
                self.hover_popup.close()
                self.hover_popup.deleteLater()
            except Exception:
                pass
            self.hover_popup = None
            
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
                    accent_color = QColor("#2ecc71")
                
                pen = QPen(accent_color, 3)
                painter.setPen(pen)
                border_rect = QRectF(1.5, 1.5, self.width() - 3.0, self.height() - 3.0)
                painter.drawRoundedRect(border_rect, 6, 6)
            finally:
                painter.end()


class CoverSearchDialog(QDialog):
    def __init__(self, initial_query, audiobook_dir, parent=None):
        super().__init__(parent)
        self.audiobook_dir = audiobook_dir
        self.initial_query = initial_query
        
        self.setWindowTitle(tr("metadata.cover_search_title", default="Search Covers Online"))
        self.resize(460, 500)
        self.setModal(True)
        
        self.results = []
        self.result_widgets = []
        self.loaded_indices = set()
        self.preview_loader = None
        self.search_worker = None
        self.download_worker = None
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        
        query_label = QLabel(tr("metadata.search_query_label", default="Query:"))
        self.query_edit = QLineEdit(self.initial_query)
        self.query_edit.setMinimumHeight(30)
        
        self.search_btn = QPushButton(tr("metadata.search_btn", default="Search"))
        self.search_btn.setMinimumHeight(30)
        self.search_btn.clicked.connect(self.start_search)
        
        search_layout.addWidget(query_label)
        search_layout.addWidget(self.query_edit, 1)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(300)
        self.scroll_area.setStyleSheet("background-color: #121212; border: 1px solid #2d2d2d; border-radius: 4px;")
        
        self.scroll_widget = QWidget()
        self.grid_layout = QGridLayout(self.scroll_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.status_label)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        self.download_btn = QPushButton(tr("metadata.download_selected", default="Download Selected"))
        self.download_btn.setMinimumHeight(32)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.start_download)
        
        self.cancel_btn = QPushButton(tr("dialog.cancel", default="Cancel"))
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.clicked.connect(self.reject)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.download_btn)
        bottom_layout.addWidget(self.cancel_btn)
        layout.addLayout(bottom_layout)
        
        self.start_search()
        
    def start_search(self):
        try:
            print("[CoverSearchDialog] start_search called")
            self.stop_threads()
            self.clear_grid()
            
            query = self.query_edit.text().strip()
            print(f"[CoverSearchDialog] Initiating search for query: '{query}'")
            if not query:
                print("[CoverSearchDialog] Search query is empty. Skipping.")
                return
                
            self.status_label.setText(tr("metadata.searching", default="Searching..."))
            self.search_btn.setEnabled(False)
            self.download_btn.setEnabled(False)
            
            self.search_worker = SearchWorker(query)
            self.search_worker.results_found.connect(self.on_search_success)
            self.search_worker.error_occurred.connect(self.on_search_error)
            self.search_worker.finished.connect(self.on_search_finished)
            self.search_worker.start()
            print("[CoverSearchDialog] Search worker thread successfully started")
        except Exception as e:
            import traceback
            print("[CoverSearchDialog] Error inside start_search:")
            traceback.print_exc()
            self.status_label.setText(f"Error starting search: {e}")
            self.search_btn.setEnabled(True)
        
    def on_search_success(self, results):
        try:
            print(f"[CoverSearchDialog] on_search_success received {len(results)} results")
            
            # Find which results are actually new
            existing_urls = {res.get('image') for res in self.results}
            new_results = []
            for res in results:
                img_url = res.get('image')
                if img_url and img_url not in existing_urls:
                    new_results.append(res)
                    
            if not new_results:
                if not self.results and not results:
                    self.status_label.setText(tr("metadata.no_covers_found", default="No covers found"))
                return
                
            start_idx = len(self.results)
            self.results.extend(new_results)
            
            self.status_label.setText(f"Found {len(self.results)} covers. Loading previews...")
            
            for i, res in enumerate(new_results):
                idx = start_idx + i
                widget = CoverSearchResultWidget(idx, res, self)
                widget.clicked.connect(self.on_widget_clicked)
                self.result_widgets.append(widget)
                
            self.rearrange_grid()
            
            # Restart PreviewLoader for all not-yet-loaded images
            if self.preview_loader:
                self.preview_loader.running = False
                self.preview_loader.wait()
                self.preview_loader = None
                
            index_url_pairs = [
                (i, res.get('image'))
                for i, res in enumerate(self.results)
                if i not in self.loaded_indices
            ]
            if index_url_pairs:
                print(f"[CoverSearchDialog] Starting PreviewLoader for {len(index_url_pairs)} pending previews")
                self.preview_loader = PreviewLoader(index_url_pairs)
                self.preview_loader.preview_ready.connect(self.on_preview_ready)
                self.preview_loader.start()
        except Exception as e:
            import traceback
            print("[CoverSearchDialog] Error inside on_search_success:")
            traceback.print_exc()
            self.status_label.setText(f"Error loading results: {e}")
        
    def on_search_error(self, err_msg):
        print(f"[CoverSearchDialog] on_search_error received: '{err_msg}'")
        self.status_label.setText(f"Search error: {err_msg}")
        
    def on_search_finished(self):
        print("[CoverSearchDialog] Search worker finished")
        self.search_btn.setEnabled(True)
        
    def on_preview_ready(self, idx, pixmap):
        try:
            if idx < len(self.result_widgets):
                self.result_widgets[idx].set_pixmap(pixmap)
                self.loaded_indices.add(idx)
        except Exception as e:
            print(f"[CoverSearchDialog] Error setting preview pixmap at index {idx}: {e}")
            
    def on_widget_clicked(self):
        try:
            sender = self.sender()
            if sender:
                sender.set_selected(not sender.is_selected)
                print(f"[CoverSearchDialog] Selection state of item {sender.index} changed to {sender.is_selected}")
                
            any_selected = any(w.is_selected for w in self.result_widgets)
            self.download_btn.setEnabled(any_selected)
        except Exception as e:
            print(f"[CoverSearchDialog] Error processing widget click: {e}")
        
    def start_download(self):
        try:
            selected_urls = []
            for w in self.result_widgets:
                if w.is_selected:
                    selected_urls.append(w.result_data.get('image'))
                    
            print(f"[CoverSearchDialog] start_download with {len(selected_urls)} items")
            if not selected_urls:
                print("[CoverSearchDialog] No items selected for download. Skipping.")
                return
                
            self.status_label.setText(tr("metadata.downloading", default="Downloading..."))
            self.download_btn.setEnabled(False)
            self.search_btn.setEnabled(False)
            
            self.download_worker = DownloadWorker(selected_urls, self.audiobook_dir)
            self.download_worker.progress.connect(self.on_download_progress)
            self.download_worker.finished_signal.connect(self.on_download_finished)
            self.download_worker.start()
            print("[CoverSearchDialog] Download worker thread successfully started")
        except Exception as e:
            import traceback
            print("[CoverSearchDialog] Error starting download worker:")
            traceback.print_exc()
            self.status_label.setText(f"Error starting download: {e}")
            self.download_btn.setEnabled(True)
            self.search_btn.setEnabled(True)
        
    def on_download_progress(self, current, total):
        self.status_label.setText(f"Downloading cover {current} of {total}...")
        
    def on_download_finished(self, success_count, err_msg):
        try:
            print(f"[CoverSearchDialog] on_download_finished received: success_count={success_count}, error='{err_msg}'")
            self.download_btn.setEnabled(True)
            self.search_btn.setEnabled(True)
            
            if err_msg and success_count == 0:
                print(f"[CoverSearchDialog] Download failed completely: {err_msg}")
                QMessageBox.critical(self, tr("error"), err_msg)
                self.status_label.setText(f"Download error: {err_msg}")
            else:
                print(f"[CoverSearchDialog] Download finished. Successfully saved {success_count} covers.")
                self.accept()
        except Exception as e:
            import traceback
            print("[CoverSearchDialog] Error inside on_download_finished:")
            traceback.print_exc()
            
    def stop_threads(self):
        print("[CoverSearchDialog] stop_threads called")
        if self.search_worker and self.search_worker.isRunning():
            print("[CoverSearchDialog] Terminating search worker thread...")
            self.search_worker.terminate()
            self.search_worker.wait()
            print("[CoverSearchDialog] Search worker thread terminated.")
        self.search_worker = None
        
        if self.preview_loader:
            print("[CoverSearchDialog] Stopping preview loader thread...")
            self.preview_loader.running = False
            self.preview_loader.wait()
            print("[CoverSearchDialog] Preview loader thread stopped.")
        self.preview_loader = None
        
        if self.download_worker and self.download_worker.isRunning():
            print("[CoverSearchDialog] Terminating download worker thread...")
            self.download_worker.terminate()
            self.download_worker.wait()
            print("[CoverSearchDialog] Download worker thread terminated.")
        self.download_worker = None
        
    def clear_grid(self):
        print("[CoverSearchDialog] clear_grid called")
        for widget in self.result_widgets:
            widget.deleteLater()
        self.result_widgets = []
        self.results = []
        self.loaded_indices.clear()
        if hasattr(self, '_current_cols'):
            delattr(self, '_current_cols')
        if hasattr(self, '_current_widget_count'):
            delattr(self, '_current_widget_count')
        
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
    def closeEvent(self, event):
        print("[CoverSearchDialog] closeEvent triggered")
        self.stop_threads()
        super().closeEvent(event)
        
    def reject(self):
        print("[CoverSearchDialog] reject triggered")
        self.stop_threads()
        super().reject()

    def rearrange_grid(self):
        """Rearrange the search results grid dynamically based on the current width of the scroll area."""
        if not self.result_widgets:
            return
            
        avail_width = self.scroll_area.viewport().width()
        if avail_width <= 0:
            avail_width = self.scroll_area.width()
        if avail_width <= 0:
            avail_width = self.width() - 30
            
        cols = max(1, (avail_width - 10) // 135)
        
        if (hasattr(self, '_current_cols') and self._current_cols == cols and
                hasattr(self, '_current_widget_count') and self._current_widget_count == len(self.result_widgets)):
            return
        self._current_cols = cols
        self._current_widget_count = len(self.result_widgets)
        
        self.scroll_widget.setUpdatesEnabled(False)
        try:
            while self.grid_layout.count():
                self.grid_layout.takeAt(0)
                
            for idx, widget in enumerate(self.result_widgets):
                row = idx // cols
                col = idx % cols
                self.grid_layout.addWidget(widget, row, col)
        finally:
            self.scroll_widget.setUpdatesEnabled(True)

    def resizeEvent(self, event):
        """Handle resize events to dynamically update the columns in the search grid."""
        super().resizeEvent(event)
        self.rearrange_grid()

