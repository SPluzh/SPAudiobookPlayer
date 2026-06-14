import pytest
from PyQt6.QtCore import QEventLoop
from goodreads_scraper import GoodreadsScraper, GoodreadsSearchWorker

def test_goodreads_scraper_direct_parsing(monkeypatch):
    """Test GoodreadsScraper direct HTML parsing when the search succeeds without a block."""
    mock_html = """
    <html>
    <body>
        <table class="tableList">
            <tr itemscope="" itemtype="http://schema.org/Book">
                <td>
                    <a class="bookTitle" href="/book/show/12345-test-book">
                        <span>Test Book Title</span>
                    </a>
                    <a class="authorName" href="/author/show/6789-test-author">
                        <span>Test Author Name</span>
                    </a>
                    <img class="bookCover" src="https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/123456789i/12345._SY75_.jpg">
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    def mock_fetch(self, url):
        return mock_html
        
    monkeypatch.setattr(GoodreadsScraper, "_fetch", mock_fetch)
    
    scraper = GoodreadsScraper()
    results = scraper.search("Test Book", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "12345"
    assert result["title"] == "[Goodreads] Test Book Title - Test Author Name"
    assert result["url"] == "https://www.goodreads.com/book/show/12345-test-book"
    # Ensure the cover image suffix was stripped to get the larger image
    assert result["image"] == "https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/123456789i/12345.jpg"
    assert result["width"] == 300
    assert result["height"] == 450
    assert result["type"] == "book"


def test_goodreads_scraper_ddg_fallback(monkeypatch):
    """Test GoodreadsScraper fallback to DuckDuckGo when direct fetch fails/is blocked."""
    # Direct fetch returns None (or blocked page)
    def mock_fetch(self, url):
        return "Blocked by WAF challenge"
        
    monkeypatch.setattr(GoodreadsScraper, "_fetch", mock_fetch)
    
    mock_ddg_results = [
        {
            "title": "Harry Potter and the Sorcerer's Stone by J.K. Rowling | Goodreads",
            "image": "https://images-na.ssl-images-amazon.com/images/S/compressed.photo.goodreads.com/books/1660062770i/61917439._SY75_.jpg",
            "url": "https://www.goodreads.com/book/show/61917439-harry-potter-and-the-deathly-hallows",
            "width": 100,
            "height": 150
        }
    ]
    
    class MockDDGS:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def images(self, query, *args, **kwargs):
            assert "site:goodreads.com" in query
            return mock_ddg_results
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = GoodreadsScraper()
    results = scraper.search("Harry Potter", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "61917439"
    # Suffix | Goodreads should be stripped
    assert result["title"] == "[Goodreads] Harry Potter and the Sorcerer's Stone by J.K. Rowling"
    assert result["url"] == "https://www.goodreads.com/book/show/61917439-harry-potter-and-the-deathly-hallows"
    # Suffix `_SY75_` should be stripped
    assert result["image"] == "https://images-na.ssl-images-amazon.com/images/S/compressed.photo.goodreads.com/books/1660062770i/61917439.jpg"


def test_goodreads_search_worker(monkeypatch):
    """Test GoodreadsSearchWorker QThread executes and emits signals."""
    mock_data = [{"title": "Thread Book", "image": "http://example.com/cover.jpg", "url": "http://example.com", "width": 300, "height": 450, "type": "book", "id": "999"}]
    
    class MockScraper:
        def search(self, query):
            return mock_data
            
    monkeypatch.setattr("goodreads_scraper.GoodreadsScraper", MockScraper)
    
    worker = GoodreadsSearchWorker("query")
    results = []
    
    worker.results_found.connect(results.extend)
    worker.run()
    
    assert results == mock_data
