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
