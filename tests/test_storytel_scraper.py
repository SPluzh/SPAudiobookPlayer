import pytest
from PyQt6.QtCore import QEventLoop
import json
from storytel_scraper import StorytelScraper, StorytelSearchWorker

def test_storytel_scraper_direct_parsing(monkeypatch):
    """Test StorytelScraper direct API parsing when the search succeeds."""
    mock_response = {
        "items": [
            {
                "id": "117903",
                "deepLink": "storytel://books/85100",
                "title": "Harry Potter and the Chamber of Secrets",
                "bookId": 85100,
                "shareUrl": "https://www.storytel.com/books/harry-potter-and-the-chamber-of-secrets-117903",
                "language": "en",
                "authors": [
                    {"id": "1998", "name": "J.K. Rowling"}
                ],
                "narrators": [
                    {"id": "2414", "name": "Stephen Fry"}
                ],
                "formats": [
                    {
                        "type": "abook",
                        "cover": {
                            "url": "https://covers.storytel.com/jpg-640/9781781102374.jpg",
                            "width": 640,
                            "height": 640
                        }
                    }
                ],
                "resultType": "book"
            }
        ]
    }
    
    def mock_fetch(self, url):
        return json.dumps(mock_response)
        
    monkeypatch.setattr(StorytelScraper, "_fetch", mock_fetch)
    
    scraper = StorytelScraper()
    results = scraper.search("Harry Potter", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "117903"
    assert result["title"] == "[Storytel] [Audiobook] Harry Potter and the Chamber of Secrets - J.K. Rowling (Чтец: Stephen Fry)"
    assert result["url"] == "https://www.storytel.com/books/harry-potter-and-the-chamber-of-secrets-117903"
    assert result["image"] == "https://covers.storytel.com/jpg-640/9781781102374.jpg"
    assert result["width"] == 640
    assert result["height"] == 640
    assert result["type"] == "abook"


def test_storytel_scraper_ddg_fallback(monkeypatch):
    """Test StorytelScraper fallback to DuckDuckGo when direct API fetch fails/returns nothing."""
    # Direct fetch returns None
    def mock_fetch(self, url):
        return None
        
    monkeypatch.setattr(StorytelScraper, "_fetch", mock_fetch)
    
    mock_ddg_results = [
        {
            "title": "Harry Potter and the Chamber of Secrets | Storytel",
            "image": "https://covers.storytel.com/jpg-640/9781781102374.jpg",
            "url": "https://www.storytel.com/books/harry-potter-and-the-chamber-of-secrets-117903",
            "width": 640,
            "height": 640
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
            assert "site:storytel.com" in query
            return mock_ddg_results
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = StorytelScraper()
    results = scraper.search("Harry Potter", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "117903"
    assert result["title"] == "[Storytel] Harry Potter and the Chamber of Secrets"
    assert result["url"] == "https://www.storytel.com/books/harry-potter-and-the-chamber-of-secrets-117903"
    assert result["image"] == "https://covers.storytel.com/jpg-640/9781781102374.jpg"
    assert result["width"] == 640
    assert result["height"] == 640
    assert result["type"] == "book"


def test_storytel_search_worker(monkeypatch):
    """Test StorytelSearchWorker QThread executes and emits signals."""
    mock_data = [{"title": "Thread Book", "image": "http://example.com/cover.jpg", "url": "http://example.com", "width": 300, "height": 450, "type": "book", "id": "999"}]
    
    class MockScraper:
        def search(self, query):
            return mock_data
            
    monkeypatch.setattr("storytel_scraper.StorytelScraper", MockScraper)
    
    worker = StorytelSearchWorker("query")
    results = []
    
    worker.results_found.connect(results.extend)
    worker.run()
    
    assert results == mock_data


def test_storytel_scraper_no_results_no_fallback(monkeypatch):
    """Test StorytelScraper returns empty list and does not fallback to DDG when direct API returns 0 results."""
    mock_response = {
        "items": []
    }
    
    def mock_fetch(self, url):
        return json.dumps(mock_response)
        
    monkeypatch.setattr(StorytelScraper, "_fetch", mock_fetch)
    
    # Mock DDGS to ensure it is not called
    class MockDDGS:
        def __init__(self, *args, **kwargs):
            raise AssertionError("DuckDuckGo search should not be called!")
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = StorytelScraper()
    results = scraper.search("nonexistent", limit=5)
    
    assert results == []


def test_storytel_scraper_ddg_fallback_filtering(monkeypatch):
    """Test StorytelScraper fallback to DuckDuckGo filters out non-Storytel and invalid results."""
    def mock_fetch(self, url):
        return None
        
    monkeypatch.setattr(StorytelScraper, "_fetch", mock_fetch)
    
    mock_ddg_results = [
        {
            # Valid Storytel URL and ID
            "title": "Valid Book | Storytel",
            "image": "https://covers.storytel.com/jpg-640/9781781102374.jpg",
            "url": "https://www.storytel.com/books/valid-book-117903",
            "width": 640,
            "height": 640
        },
        {
            # Invalid: Non-Storytel URL
            "title": "Wikipedia Book",
            "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Wikipedia-logo.png",
            "url": "https://en.wikipedia.org/wiki/Book",
            "width": 200,
            "height": 200
        },
        {
            # Invalid: Storytel URL but no book ID
            "title": "Storytel About Page",
            "image": "https://covers.storytel.com/about.jpg",
            "url": "https://www.storytel.com/about",
            "width": 300,
            "height": 300
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
            return mock_ddg_results
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = StorytelScraper()
    results = scraper.search("Query", limit=5)
    
    assert len(results) == 1
    assert results[0]["id"] == "117903"
    assert results[0]["title"] == "[Storytel] Valid Book"
