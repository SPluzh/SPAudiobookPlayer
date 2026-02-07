
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QDialogButtonBox, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from translations import tr
from utils import get_icon

class MetadataEditDialog(QDialog):
    """Dialog for manually editing audiobook metadata"""
    
    def __init__(self, db_manager, audiobook_id, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.audiobook_id = audiobook_id
        
        self.setWindowTitle(tr("metadata.edit_title"))
        self.setModal(True)
        self.resize(450, 250)
        
        self.current_data = self.db.get_audiobook_metadata(self.audiobook_id)
        if not self.current_data:
            # If no data found (e.g. deleted), close immediately
            self.reject()
            return

        self.setup_ui()
        self.load_suggestions()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
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
        # Optional icon if available, generic "refresh" or "tag" icon could work 
        # self.from_tags_btn.setIcon(get_icon("tag")) 
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
        # We block signals to avoid triggering any accidental changes during load
        self.author_combo.blockSignals(True)
        self.title_combo.blockSignals(True)
        self.narrator_combo.blockSignals(True)
        
        
        # 1. Local Suggestions (from this book's files)
        # These match the actual file content, even if it's in the wrong tag
        local_tags = self.db.get_all_book_raw_tags(self.audiobook_id)
        
        # Helper to merge lists: [current_value] + [local_tags]
        def create_suggestion_list(current_val):
            items = []
            seen = set()
            
            # Current value first
            if current_val:
                items.append(current_val)
                seen.add(current_val)
            
            # Then local tags
            for tag in local_tags:
                if tag not in seen:
                    items.append(tag)
                    seen.add(tag)
                    
            return items

        # Populate Combos
        self.author_combo.addItems(create_suggestion_list(
            self.current_data.get('author')
        ))
        
        self.title_combo.addItems(create_suggestion_list(
            self.current_data.get('title')
        ))
        
        self.narrator_combo.addItems(create_suggestion_list(
            self.current_data.get('narrator')
        ))
        
        # Restore current text (addItems might change selection if current text is not first)
        if self.current_data.get('author'):
            self.author_combo.setCurrentText(self.current_data['author'])
        
        if self.current_data.get('title'):
            self.title_combo.setCurrentText(self.current_data['title'])
            
        if self.current_data.get('narrator'):
            self.narrator_combo.setCurrentText(self.current_data['narrator'])
            
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
                # Sometimes narrator is in composer or comment, but here we assume logic in scanner extracted it to tag_narrator
                self.narrator_combo.setCurrentText(tag_narrator)
                
    def get_data(self):
        """Return the entered metadata as a tuple"""
        return (
            self.author_combo.currentText().strip(),
            self.title_combo.currentText().strip(),
            self.narrator_combo.currentText().strip()
        )
