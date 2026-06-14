import urllib.request
import urllib.parse
import json
import re
from PyQt6.QtCore import QThread, pyqtSignal

class StorytelScraper:
    BASE_URL = "https://api.storytel.net/search/client/web"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.storytel.com/'
    }
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        
    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.getcode() != 200:
                    print(f"[StorytelScraper] Fetch status {response.getcode()} for {url}")
                    return None
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"[StorytelScraper] Fetch error for {url}: {e}")
            return None

    def search(self, query: str, limit: int = 40) -> list:
        """
        Ищет книги на storytel.com через их публичный API.
        Если запрос не удался, переключается на поиск через DuckDuckGo Image Search.
        Возвращает список словарей, совместимый с CoverSearchResultWidget.
        """
        print(f"[StorytelScraper] Searching for '{query}'...")
        encoded_query = urllib.parse.quote(query)
        # store=STHP-TV для глобального поиска по умолчанию
        url = f"{self.BASE_URL}?query={encoded_query}&store=STHP-TV&searchFor=books&includeFormats=abook,ebook"
        
        json_data = self._fetch(url)
        results = []
        is_failed = True
        
        if json_data:
            try:
                data = json.loads(json_data)
                items = data.get("items", [])
                is_failed = False
                
                for item in items:
                    title = item.get("title", "")
                    book_id = item.get("id", "")
                    share_url = item.get("shareUrl", "")
                    
                    authors = item.get("authors", [])
                    authors_str = ", ".join([a.get("name", "") for a in authors if a.get("name")])
                    
                    narrators = item.get("narrators", [])
                    narrators_str = ", ".join([n.get("name", "") for n in narrators if n.get("name")])
                    readers_suffix = f" (Чтец: {narrators_str})" if narrators_str else ""
                    
                    formats = item.get("formats", [])
                    for fmt in formats:
                        fmt_type = fmt.get("type", "")
                        cover = fmt.get("cover", {})
                        cover_url = cover.get("url", "")
                        width = cover.get("width", 300)
                        height = cover.get("height", 450)
                        
                        if not cover_url:
                            continue
                            
                        if fmt_type == "abook":
                            display_title = f"[Storytel] [Audiobook] {title} - {authors_str}{readers_suffix}".strip()
                        else:
                            display_title = f"[Storytel] [Ebook] {title} - {authors_str}".strip()
                            
                        results.append({
                            "image": cover_url,
                            "url": share_url or f"https://www.storytel.com/books/{book_id}",
                            "width": width,
                            "height": height,
                            "title": display_title,
                            "type": fmt_type,
                            "id": book_id
                        })
                print(f"[StorytelScraper] Parsed {len(results)} books from direct API search")
            except Exception as e:
                print(f"[StorytelScraper] Error parsing direct API response: {e}")
                is_failed = True
                
        if is_failed or not results:
            print("[StorytelScraper] Direct search failed or returned no results. Falling back to DuckDuckGo search...")
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                    
                with DDGS() as ddgs:
                    ddg_query = f"site:storytel.com {query}"
                    raw_results = list(ddgs.images(ddg_query, safesearch='off', max_results=limit))
                    
                for res in raw_results:
                    title = res.get("title", "")
                    if title.endswith(" | Storytel"):
                        title = title[:-11].strip()
                        
                    image_url = res.get("image", "")
                    page_url = res.get("url", "")
                    
                    book_id = ""
                    match = re.search(r'-(\d+)(?:\?|$)', page_url)
                    if match:
                        book_id = match.group(1)
                        
                    results.append({
                        "image": image_url,
                        "url": page_url,
                        "width": res.get("width", 300),
                        "height": res.get("height", 450),
                        "title": f"[Storytel] {title}".strip(),
                        "type": "book",
                        "id": book_id
                    })
                print(f"[StorytelScraper] Found {len(results)} items via DuckDuckGo fallback")
            except Exception as e:
                print(f"[StorytelScraper] DuckDuckGo fallback search failed: {e}")
                
        return results[:limit]

class StorytelSearchWorker(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query
        
    def run(self):
        try:
            scraper = StorytelScraper()
            results = scraper.search(self.query)
            self.results_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
