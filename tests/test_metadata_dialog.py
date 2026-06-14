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

def test_cover_search_features(temp_db, temp_dir, monkeypatch):
    """Test the cover search button visibility, worker search, and download processes."""
    from PyQt6.QtWidgets import QWidget
    app = QApplication.instance() or QApplication([])
    init_database(str(temp_db))
    db = DatabaseManager(str(temp_db))
    
    # 1. Insert an audiobook
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

    class MockParent(QWidget):
        def __init__(self, lib_path):
            super().__init__()
            self.config = {"default_path": str(lib_path)}
            
        def apply_blur(self):
            pass
            
        def remove_blur(self):
            pass

    # 2. Check search button is visible in single edit mode
    mock_parent = MockParent(temp_dir)
    dialog = MetadataEditDialog(db, audiobook_id, parent=mock_parent)
    assert dialog.search_cover_btn.isHidden() is False
    
    # Check search button is NOT visible in bulk edit mode
    bulk_dialog = MetadataEditDialog(db, [audiobook_id], parent=mock_parent)
    assert bulk_dialog.search_cover_btn.isHidden() is True
    
    # 3. Test get_audiobook_dir
    assert dialog.get_audiobook_dir() == temp_dir / "book_path"
    
    # 4. Test SearchWorker with mocked duckduckgo_search
    from metadata_dialog import SearchWorker, DownloadWorker
    import time
    monkeypatch.setattr(time, "sleep", lambda x: None)
    
    class MockGoodreadsScraper:
        def search(self, query, limit=40):
            return []
            
    class MockStorytelScraper:
        def search(self, query, limit=40):
            return []

    class MockAudibleScraper:
        def search(self, query, limit=40):
            return []
            
    class MockLitresScraper:
        def search(self, query):
            return []
            
    monkeypatch.setattr("goodreads_scraper.GoodreadsScraper", MockGoodreadsScraper)
    monkeypatch.setattr("storytel_scraper.StorytelScraper", MockStorytelScraper)
    monkeypatch.setattr("audible_scraper.AudibleScraper", MockAudibleScraper)
    monkeypatch.setattr("litres_scraper.LitresScraper", MockLitresScraper)
    
    mock_results = [
        {"title": "Cover 1", "image": "http://example.com/cover1.jpg", "width": 100, "height": 100},
        {"title": "Cover 2", "image": "http://example.com/cover2.jpg", "width": 200, "height": 200}
    ]
    
    captured_kwargs = []
    
    class MockDDGS:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def images(self, query, *args, **kwargs):
            captured_kwargs.append((query, kwargs))
            return mock_results
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    # Test standard search
    worker = SearchWorker("test query")
    results = []
    worker.results_found.connect(results.extend)
    worker.run()
    assert results == mock_results
    assert len(captured_kwargs) == 1
    assert 'region' not in captured_kwargs[0][1]
    
    # Test Cyrillic query search
    captured_kwargs.clear()
    
    worker_ru = SearchWorker("Макс Фрай")
    results_ru = []
    worker_ru.results_found.connect(results_ru.extend)
    worker_ru.run()
    assert len(results_ru) > 0
    assert len(captured_kwargs) == 1
    assert captured_kwargs[0][0] == "Макс Фрай"
    assert 'region' not in captured_kwargs[0][1]

    # Test retry logic: first attempt returns 1 result, second attempt returns 2 results
    retry_results = [
        [{"title": "Ad", "image": "http://example.com/ad.jpg", "width": 50, "height": 50}],
        mock_results
    ]
    retry_calls = 0
    
    class MockDDGSRetry:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def images(self, query, *args, **kwargs):
            nonlocal retry_calls
            res = retry_results[retry_calls]
            retry_calls += 1
            return res
            
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGSRetry)
    try:
        monkeypatch.setattr("ddgs.DDGS", MockDDGSRetry)
    except ImportError:
        pass
        
    worker_retry = SearchWorker("retry test")
    results_retry = []
    worker_retry.results_found.connect(results_retry.extend)
    worker_retry.run()
    
    assert retry_calls == 2
    assert results_retry == mock_results
    
    # Test successful LitresScraper path
    mock_litres_results = [
        {"title": "Litres Cover", "image": "https://cdn.litres.ru/pub/c/cover/123.jpg", "width": 300, "height": 400}
    ]
    class MockLitresScraperSuccess:
        def search(self, query):
            return mock_litres_results
    monkeypatch.setattr("litres_scraper.LitresScraper", MockLitresScraperSuccess)
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    try:
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    
    worker_litres = SearchWorker("Макс Фрай")
    emitted_events = []
    worker_litres.results_found.connect(emitted_events.append)
    worker_litres.run()
    assert len(emitted_events) == 2
    assert emitted_events[0] == mock_litres_results
    assert emitted_events[1] == mock_litres_results + mock_results

    # 5. Test DownloadWorker with mocked urlopen
    class MockResponse:
        def __init__(self, data):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def read(self):
            return self.data
            
    def mock_urlopen(req, timeout=15):
        return MockResponse(b"fake image data")
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    book_dir = temp_dir / "book_path"
    book_dir.mkdir(parents=True, exist_ok=True)
    
    urls = ["http://example.com/some_cover.jpg", "http://example.com/another_cover.jpg"]
    download_worker = DownloadWorker(urls, book_dir)
    
    finished_args = []
    def on_finished(count, err):
        finished_args.append((count, err))
        
    download_worker.finished_signal.connect(on_finished)
    download_worker.run()
    
    assert finished_args == [(2, "")]
    
    # Check files created and uniquely named
    assert (book_dir / "cover.jpg").exists()
    assert (book_dir / "cover_1.jpg").exists()

def test_cover_search_dialog_rearrange_grid(temp_db, temp_dir, monkeypatch):
    """Test that CoverSearchDialog dynamically rearranges results when viewport size changes."""
    from PyQt6.QtWidgets import QApplication
    from metadata_dialog import CoverSearchDialog, CoverSearchResultWidget
    
    app = QApplication.instance() or QApplication([])
    
    # Mock start_search so it doesn't run the actual network search on creation
    monkeypatch.setattr(CoverSearchDialog, "start_search", lambda self: None)
    
    dialog = CoverSearchDialog("query", temp_dir)
    
    # Manually add some mock results to test rearrange_grid
    results = [
        {"image": "http://example.com/1.jpg", "width": 100, "height": 100},
        {"image": "http://example.com/2.jpg", "width": 100, "height": 100},
        {"image": "http://example.com/3.jpg", "width": 100, "height": 100},
        {"image": "http://example.com/4.jpg", "width": 100, "height": 100},
        {"image": "http://example.com/5.jpg", "width": 100, "height": 100},
    ]
    
    for idx, res in enumerate(results):
        w = CoverSearchResultWidget(idx, res, dialog)
        dialog.result_widgets.append(w)
        dialog.grid_layout.addWidget(w, idx // 3, idx % 3)
        
    # 1. Mock viewport width to be 400.
    # N = (400 - 10) // 135 = 2.
    monkeypatch.setattr(dialog.scroll_area.viewport(), "width", lambda: 400)
    dialog.rearrange_grid()
    
    # Assert _current_cols is 2
    assert dialog._current_cols == 2
    # Verify the layout positions
    assert dialog.grid_layout.getItemPosition(0) == (0, 0, 1, 1)
    assert dialog.grid_layout.getItemPosition(1) == (0, 1, 1, 1)
    assert dialog.grid_layout.getItemPosition(2) == (1, 0, 1, 1)
    assert dialog.grid_layout.getItemPosition(3) == (1, 1, 1, 1)
    assert dialog.grid_layout.getItemPosition(4) == (2, 0, 1, 1)
    
    # 2. Mock viewport width to be 550.
    # N = (550 - 10) // 135 = 4.
    monkeypatch.setattr(dialog.scroll_area.viewport(), "width", lambda: 550)
    dialog.rearrange_grid()
    
    assert dialog._current_cols == 4
    assert dialog.grid_layout.getItemPosition(0) == (0, 0, 1, 1)
    assert dialog.grid_layout.getItemPosition(1) == (0, 1, 1, 1)
    assert dialog.grid_layout.getItemPosition(2) == (0, 2, 1, 1)
    assert dialog.grid_layout.getItemPosition(3) == (0, 3, 1, 1)
    assert dialog.grid_layout.getItemPosition(4) == (1, 0, 1, 1)
    
    # 3. Test cleanup in clear_grid
    dialog.clear_grid()
    assert not hasattr(dialog, '_current_cols')
    assert len(dialog.result_widgets) == 0
    assert dialog.grid_layout.count() == 0


