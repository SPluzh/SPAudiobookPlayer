import pytest
from PyQt6.QtCore import QEventLoop
from audible_scraper import AudibleScraper, AudibleSearchWorker

def test_audible_scraper_direct_parsing(monkeypatch):
    """Test AudibleScraper direct HTML parsing when the search succeeds without a block."""
    mock_html = """
    <html>
    <body>
        <li class="productListItem" id="product-list-item-B002V02KPU">
            <h3 class="bc-heading">
                <a href="/pd/The-Master-and-Margarita-Audiobook/B002V02KPU">The Master and Margarita</a>
            </h3>
            <img class="bc-pub-block" src="https://m.media-amazon.com/images/I/51-kXV1XUNL._SL500_.jpg" srcset="https://m.media-amazon.com/images/I/51-kXV1XUNL._SL100_.jpg 1x, https://m.media-amazon.com/images/I/51-kXV1XUNL._SL500_.jpg 2x">
            <span class="authorLabel">
                By: <a href="/author/Mikhail-Bulgakov">Mikhail Bulgakov</a>
            </span>
            <span class="narratorLabel">
                Narrated by: <a href="/narrator/Julian-Rhind-Tutt">Julian Rhind-Tutt</a>
            </span>
        </li>
    </body>
    </html>
    """
    
    def mock_fetch(self, url):
        return mock_html
        
    monkeypatch.setattr(AudibleScraper, "_fetch", mock_fetch)
    
    scraper = AudibleScraper()
    results = scraper.search("Master and Margarita", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "B002V02KPU"
    assert "Mikhail Bulgakov" in result["title"]
    assert "Julian Rhind-Tutt" in result["title"]
    assert result["url"] == "https://www.audible.com/pd/The-Master-and-Margarita-Audiobook/B002V02KPU"
    # Suffix `_SL500_` should be stripped from the highest density srcset image
    assert result["image"] == "https://m.media-amazon.com/images/I/51-kXV1XUNL.jpg"
    assert result["width"] == 500
    assert result["height"] == 500
    assert result["type"] == "book"


def test_audible_scraper_ddg_fallback(monkeypatch):
    """Test AudibleScraper fallback to DuckDuckGo when direct fetch fails/is blocked."""
    # Direct fetch returns None (blocked by WAF)
    def mock_fetch(self, url):
        return None
        
    monkeypatch.setattr(AudibleScraper, "_fetch", mock_fetch)
    
    mock_ddg_results = [
        {
            "title": "The Master and Margarita Audiobook by Mikhail Bulgakov - Audiobook - Audible.com",
            "image": "https://m.media-amazon.com/images/I/51-kXV1XUNL._SL500_.jpg",
            "url": "https://www.audible.com/pd/The-Master-and-Margarita-Audiobook/B002V02KPU",
            "width": 500,
            "height": 500
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
            assert "site:audible.com" in query
            return mock_ddg_results
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = AudibleScraper()
    results = scraper.search("Master and Margarita", limit=5)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "B002V02KPU"
    # Suffix ` - Audiobook - Audible.com` should be stripped, and [Audible] prefix added
    assert result["title"] == "[Audible] The Master and Margarita Audiobook by Mikhail Bulgakov"
    assert result["url"] == "https://www.audible.com/pd/The-Master-and-Margarita-Audiobook/B002V02KPU"
    # Suffix `_SL500_` should be stripped
    assert result["image"] == "https://m.media-amazon.com/images/I/51-kXV1XUNL.jpg"


def test_audible_search_worker(monkeypatch):
    """Test AudibleSearchWorker QThread executes and emits signals."""
    mock_data = [{"title": "Thread Book", "image": "http://example.com/cover.jpg", "url": "http://example.com", "width": 500, "height": 500, "type": "book", "id": "B000000000"}]
    
    class MockScraper:
        def search(self, query):
            return mock_data
            
    monkeypatch.setattr("audible_scraper.AudibleScraper", MockScraper)
    
    worker = AudibleSearchWorker("query")
    results = []
    
    worker.results_found.connect(results.extend)
    worker.run()
    
    assert results == mock_data


def test_audible_scraper_no_results_no_fallback(monkeypatch):
    """Test AudibleScraper returns empty list and does not fallback to DDG when direct search returns a valid page with 0 results."""
    # A valid Audible page layout, but has no `productListItem` elements
    mock_html = """
    <html>
    <body class="audible-page">
        <div class="bc-container">
            <p>0 results found</p>
            <input type="text" name="keywords" value="nonexistent">
        </div>
    </body>
    </html>
    """
    
    def mock_fetch(self, url):
        return mock_html
        
    monkeypatch.setattr(AudibleScraper, "_fetch", mock_fetch)
    
    # We also mock DDGS to raise an exception if it is somehow called
    class MockDDGS:
        def __init__(self, *args, **kwargs):
            raise AssertionError("DuckDuckGo search should not be called!")
            
    try:
        import ddgs
        monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    except ImportError:
        pass
    monkeypatch.setattr("duckduckgo_search.DDGS", MockDDGS)
    
    scraper = AudibleScraper()
    results = scraper.search("nonexistent", limit=5)
    
    assert results == []


def test_audible_scraper_ddg_fallback_filtering(monkeypatch):
    """Test AudibleScraper fallback to DuckDuckGo filters out non-Audible and invalid results."""
    # Direct fetch returns None (blocked by WAF)
    def mock_fetch(self, url):
        return None
        
    monkeypatch.setattr(AudibleScraper, "_fetch", mock_fetch)
    
    mock_ddg_results = [
        {
            # Valid Audible URL and ID
            "title": "Valid Book | Audible.com",
            "image": "https://m.media-amazon.com/images/I/51-kXV1XUNL._SL500_.jpg",
            "url": "https://www.audible.com/pd/Valid-Book-Audiobook/B002V02KPU",
            "width": 500,
            "height": 500
        },
        {
            # Invalid: Non-Audible URL
            "title": "Wikipedia Book",
            "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Wikipedia-logo.png",
            "url": "https://en.wikipedia.org/wiki/Book",
            "width": 200,
            "height": 200
        },
        {
            # Invalid: Audible URL but not a product detail page (no ID)
            "title": "Audible Help Center",
            "image": "https://m.media-amazon.com/images/I/help.jpg",
            "url": "https://www.audible.com/about/help",
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
    
    scraper = AudibleScraper()
    results = scraper.search("Query", limit=5)
    
    assert len(results) == 1
    assert results[0]["id"] == "B002V02KPU"
    assert results[0]["title"] == "[Audible] Valid Book"
