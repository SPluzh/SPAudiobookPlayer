import pytest
from litres_scraper import LitresScraper, LitresSearchWorker

def test_litres_scraper_deduplication(monkeypatch):
    """Test that LitresScraper removes duplicate covers, prioritizing audiobooks."""
    mock_html = """
    <html>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "initialState": {
                "rtkqApi": {
                  "queries": {
                    "getSearchData(...)": {
                      "data": {
                        "data": [
                          {
                            "type": "text_book",
                            "instance": {
                              "id": 222,
                              "title": "Book Title (Text)",
                              "cover_url": "/pub/c/cover/123.jpg",
                              "url": "/book/book-222",
                              "cover_width": 300,
                              "cover_height": 400,
                              "persons": [{"full_name": "Author Name", "role": "author"}]
                            }
                          },
                          {
                            "type": "audiobook",
                            "instance": {
                              "id": 111,
                              "title": "Book Title (Audio)",
                              "cover_url": "/pub/c/cover/123.jpg",
                              "url": "/book/book-111",
                              "cover_width": 300,
                              "cover_height": 400,
                              "persons": [{"full_name": "Author Name", "role": "author"}]
                            }
                          },
                          {
                            "type": "text_book",
                            "instance": {
                              "id": 333,
                              "title": "Another Book",
                              "cover_url": "/pub/c/cover/456.jpg",
                              "url": "/book/book-333",
                              "cover_width": 300,
                              "cover_height": 400,
                              "persons": [{"full_name": "Author Name", "role": "author"}]
                            }
                          }
                        ]
                      }
                    }
                  }
                }
              }
            }
          },
          "assetPrefix": "https://cdn.litres.ru"
        }
        </script>
    </body>
    </html>
    """
    
    def mock_fetch(self, url):
        return mock_html
        
    monkeypatch.setattr(LitresScraper, "_fetch", mock_fetch)
    
    scraper = LitresScraper()
    results = scraper.search("Test Query", limit=5)
    
    # We expect 2 results:
    # 1. The audiobook (id 111, cover "/pub/c/cover/123.jpg")
    # 2. The other text book (id 333, cover "/pub/c/cover/456.jpg")
    # The text book (id 222, cover "/pub/c/cover/123.jpg") should be discarded as a duplicate cover.
    assert len(results) == 2
    
    # First should be audiobook because of sorting and deduplication keeping the first one (audiobook)
    assert results[0]["id"] == 111
    assert results[0]["type"] == "audiobook"
    assert results[0]["image"] == "https://cdn.litres.ru/pub/c/cover/123.jpg"
    
    # Second should be the different book
    assert results[1]["id"] == 333
    assert results[1]["type"] == "text_book"
    assert results[1]["image"] == "https://cdn.litres.ru/pub/c/cover/456.jpg"

def test_litres_search_worker(monkeypatch):
    """Test LitresSearchWorker QThread executes and emits signals."""
    mock_data = [{"title": "Thread Book", "image": "https://cdn.litres.ru/pub/c/cover/999.jpg", "url": "http://example.com", "width": 300, "height": 400, "type": "audiobook", "id": 999}]
    
    class MockScraper:
        def search(self, query):
            return mock_data
            
    monkeypatch.setattr("litres_scraper.LitresScraper", MockScraper)
    
    worker = LitresSearchWorker("query")
    results = []
    
    worker.results_found.connect(results.extend)
    worker.run()
    
    assert results == mock_data
