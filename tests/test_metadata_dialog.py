import pytest
import sqlite3
from PyQt6.QtWidgets import QApplication
from database import DatabaseManager, init_database
from metadata_dialog import MetadataEditDialog

def test_database_metadata_operations(temp_db):
    """Test retrieving and updating audiobook metadata in database."""
    init_database(str(temp_db))
    db = DatabaseManager(str(temp_db))
    
    # Insert a dummy audiobook
    conn = sqlite3.connect(db.db_file)
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book_path", "Test Name", "Test Author", "Test Title", "Test Narrator", "ru", "1995", "2010", "2010", 0))
        audiobook_id = c.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    # Fetch metadata
    metadata = db.get_audiobook_metadata(audiobook_id)
    assert metadata is not None
    assert metadata['author'] == "Test Author"
    assert metadata['title'] == "Test Title"
    assert metadata['narrator'] == "Test Narrator"
    assert metadata['language'] == "ru"
    assert metadata['year_written'] == "1995"
    assert metadata['year_recorded'] == "2010"
    assert metadata['tag_year'] == "2010"
    
    # Update metadata
    db.update_audiobook_metadata(audiobook_id, "New Author", "New Title", "New Narrator", "en", "2001", "2023")
    
    # Re-fetch metadata and check values
    metadata = db.get_audiobook_metadata(audiobook_id)
    assert metadata['author'] == "New Author"
    assert metadata['title'] == "New Title"
    assert metadata['narrator'] == "New Narrator"
    assert metadata['language'] == "en"
    assert metadata['year_written'] == "2001"
    assert metadata['year_recorded'] == "2023"

def test_metadata_dialog_ui(temp_db):
    """Test MetadataEditDialog GUI population, suggestion loading, and get_data."""
    app = QApplication.instance() or QApplication([])
    init_database(str(temp_db))
    db = DatabaseManager(str(temp_db))
    
    # Insert audiobook with some tags
    conn = sqlite3.connect(db.db_file)
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book_path", "Author A - Title T", "Author A", "Title T", "Narrator N", "de", "1890", "", "1890", 0))
        audiobook_id = c.lastrowid
        conn.commit()
    finally:
        conn.close()
    
    # Create the dialog
    dialog = MetadataEditDialog(db, audiobook_id)
    
    # Check fields are populated
    assert dialog.author_combo.currentText() == "Author A"
    assert dialog.title_combo.currentText() == "Title T"
    assert dialog.narrator_combo.currentText() == "Narrator N"
    
    # Check language combo shows mapped name "Deutsch (de)"
    assert dialog.language_combo.currentText() == "Deutsch (de)"
    
    # Check year combos
    assert dialog.year_written_combo.currentText() == "1890"
    assert dialog.year_recorded_combo.currentText() == ""
    
    # Test changing fields
    dialog.author_combo.setCurrentText("Changed Author")
    dialog.language_combo.setCurrentText("Русский (ru)")  # Select mapped language
    dialog.year_written_combo.setCurrentText("1950")
    dialog.year_recorded_combo.setCurrentText("2015")
    
    # Get data and check mapped language code is returned
    author, title, narrator, language, year_written, year_recorded = dialog.get_data()
    assert author == "Changed Author"
    assert language == "ru"
    assert year_written == "1950"
    assert year_recorded == "2015"
    
    # Test setting custom language (unmapped)
    dialog.language_combo.setCurrentText("CustomLang")
    _, _, _, language, _, _ = dialog.get_data()
    assert language == "CustomLang"
    
    # Test fill_from_tags
    # In this case tag_year is "1890". Click From Tags should populate year_recorded_combo
    dialog.year_recorded_combo.setCurrentText("")
    dialog.fill_from_tags()
    assert dialog.year_recorded_combo.currentText() == "1890"

def test_database_bulk_metadata_operations(temp_db):
    """Test updating multiple audiobooks' metadata fields in one database transaction."""
    init_database(str(temp_db))
    db = DatabaseManager(str(temp_db))
    
    # Insert two dummy audiobooks
    conn = sqlite3.connect(db.db_file)
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book1", "Book 1", "Author 1", "Title 1", "Narrator 1", "ru", "1990", "2000", "2000", 0))
        id1 = c.lastrowid
        
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book2", "Book 2", "Author 2", "Title 2", "Narrator 2", "en", "1995", "2005", "2005", 0))
        id2 = c.lastrowid
        
        conn.commit()
    finally:
        conn.close()

    # Bulk update: only change language and narrator
    fields = {
        'language': 'de',
        'narrator': 'Bulk Narrator'
    }
    db.update_multiple_audiobooks_metadata_fields([id1, id2], fields)

    # Check first audiobook: updated language and narrator, other fields unchanged
    meta1 = db.get_audiobook_metadata(id1)
    assert meta1['language'] == 'de'
    assert meta1['narrator'] == 'Bulk Narrator'
    assert meta1['author'] == 'Author 1'
    assert meta1['title'] == 'Title 1'

    # Check second audiobook: updated language and narrator, other fields unchanged
    meta2 = db.get_audiobook_metadata(id2)
    assert meta2['language'] == 'de'
    assert meta2['narrator'] == 'Bulk Narrator'
    assert meta2['author'] == 'Author 2'
    assert meta2['title'] == 'Title 2'

def test_metadata_dialog_bulk_mode_ui(temp_db):
    """Test MetadataEditDialog GUI behavior in bulk editing mode."""
    app = QApplication.instance() or QApplication([])
    init_database(str(temp_db))
    db = DatabaseManager(str(temp_db))
    
    # Insert two dummy audiobooks
    conn = sqlite3.connect(db.db_file)
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book1", "Book 1", "Author 1", "Title 1", "Narrator 1", "ru", "1990", "2000", "2000", 0))
        id1 = c.lastrowid
        
        c.execute("""
            INSERT INTO audiobooks (path, name, author, title, narrator, language, year_written, year_recorded, tag_year, is_folder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("book2", "Book 2", "Author 2", "Title 2", "Narrator 2", "en", "1995", "2005", "2005", 0))
        id2 = c.lastrowid
        
        conn.commit()
    finally:
        conn.close()

    # Create dialog in bulk mode by passing a list of IDs
    dialog = MetadataEditDialog(db, [id1, id2])
    
    # Verify is_bulk is True
    assert dialog.is_bulk is True
    
    # Check default checkbox states in bulk mode
    assert dialog.language_cb.isChecked() is True
    assert dialog.author_cb.isChecked() is False
    assert dialog.title_cb.isChecked() is False
    assert dialog.narrator_cb.isChecked() is False
    assert dialog.year_written_cb.isChecked() is False
    assert dialog.year_recorded_cb.isChecked() is False
    
    # Check enabled state of fields based on default checkbox states
    assert dialog.language_combo.isEnabled() is True
    assert dialog.author_combo.isEnabled() is False
    assert dialog.title_combo.isEnabled() is False
    assert dialog.narrator_combo.isEnabled() is False
    assert dialog.year_written_combo.isEnabled() is False
    assert dialog.year_recorded_combo.isEnabled() is False

    # Check get_enabled_fields outputs only language by default
    dialog.language_combo.setCurrentText("Deutsch (de)")
    enabled = dialog.get_enabled_fields()
    assert 'language' in enabled
    assert enabled['language'] == 'de'
    assert 'author' not in enabled
    assert 'narrator' not in enabled
    
    # Toggle some checkboxes and check
    dialog.author_cb.setChecked(True)
    dialog.author_combo.setCurrentText("Bulk Author")
    assert dialog.author_combo.isEnabled() is True
    
    enabled = dialog.get_enabled_fields()
    assert enabled['language'] == 'de'
    assert enabled['author'] == 'Bulk Author'
    assert 'narrator' not in enabled

