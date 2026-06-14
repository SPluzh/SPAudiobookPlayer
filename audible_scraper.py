import urllib.request
import urllib.parse
import re
from PyQt6.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup

class AudibleScraper:
    BASE_URL = "https://www.audible.com"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.audible.com/'
    }
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        
    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.getcode() != 200:
                    print(f"[AudibleScraper] Fetch status {response.getcode()} for {url}")
                    return None
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"[AudibleScraper] Fetch error for {url}: {e}")
            return None

    def search(self, query: str, limit: int = 40) -> list:
        """
        Ищет книги на audible.com по поисковому запросу.
        Сначала пытается выполнить прямой парсинг HTML.
        Если запрос заблокирован WAF (Cloudflare/AWS WAF) или возвращает 503,
        переключается на поиск через DuckDuckGo Image Search.
        Возвращает список словарей, совместимый с CoverSearchResultWidget.
        """
        print(f"[AudibleScraper] Searching for '{query}'...")
        encoded_query = urllib.parse.quote(query)
        
        base_urls = ["https://www.audible.com", "https://www.audible.co.uk", "https://www.audible.de"]
            
        html = None
        used_base_url = ""
        for base_url in base_urls:
            url = f"{base_url}/search?keywords={encoded_query}"
            print(f"[AudibleScraper] Trying fetch from {url}...")
            html = self._fetch(url)
            if html and "productListItem" in html:
                used_base_url = base_url
                break
                
        results = []
        is_blocked = True
        
        if html and "productListItem" in html:
            is_blocked = False
            
        if not is_blocked:
            try:
                print("[AudibleScraper] Direct fetch succeeded. Parsing HTML...")
                soup = BeautifulSoup(html, 'html.parser')
                items = soup.select('li.productListItem')
                for item in items:
                    title_link = item.select_one('h3.bc-heading a')
                    if not title_link:
                        continue
                    
                    title = title_link.text.strip()
                    page_path = title_link.get('href', '')
                    if page_path.startswith('/'):
                        page_url = f"{used_base_url or self.BASE_URL}{page_path}"
                    else:
                        page_url = page_path
                        
                    # Извлекаем обложку
                    image_tag = item.select_one('img.bc-pub-block')
                    cover_url = ""
                    if image_tag:
                        srcset = image_tag.get('srcset')
                        if srcset:
                            parts = [p.strip().split(' ') for p in srcset.split(',')]
                            if parts:
                                cover_url = parts[-1][0]
                        if not cover_url:
                            cover_url = image_tag.get('src', '')
                            
                    if cover_url:
                        cover_url = cover_url.strip()
                        # Очищаем суффиксы размера обложки для получения оригинального разрешения
                        cover_url = re.sub(r'\._[^.]+_(?=\.[a-z]+)', '', cover_url, flags=re.IGNORECASE).strip()
                        
                    # Извлекаем ASIN (Book ID)
                    book_id = ""
                    item_id = item.get('id', '')
                    if item_id.startswith('product-list-item-'):
                        book_id = item_id[len('product-list-item-'):]
                    if not book_id:
                        match = re.search(r'/pd/(?:[^/]+/)?([A-Z0-9]{10})', page_url)
                        if match:
                            book_id = match.group(1)
                            
                    # Извлекаем авторов
                    author_label = item.select_one('.authorLabel')
                    authors_str = ""
                    if author_label:
                        a_tags = author_label.find_all('a')
                        if a_tags:
                            authors_str = ", ".join([a.text.strip() for a in a_tags if a.text.strip()])
                        else:
                            authors_str = author_label.text.replace("By:", "").strip()
                            
                    # Извлекаем дикторов
                    narrator_label = item.select_one('.narratorLabel')
                    narrators_str = ""
                    if narrator_label:
                        a_tags = narrator_label.find_all('a')
                        if a_tags:
                            narrators_str = ", ".join([a.text.strip() for a in a_tags if a.text.strip()])
                        else:
                            narrators_str = narrator_label.text.replace("Narrated by:", "").strip()
                            
                    display_title = f"[Audible] {title}"
                    if authors_str:
                        display_title += f" - {authors_str}"
                    if narrators_str:
                        display_title += f" (Чтец: {narrators_str})"
                        
                    results.append({
                        "image": cover_url,
                        "url": page_url,
                        "width": 500,
                        "height": 500,
                        "title": display_title.strip(),
                        "type": "book",
                        "id": book_id
                    })
                print(f"[AudibleScraper] Parsed {len(results)} books from direct search")
            except Exception as e:
                print(f"[AudibleScraper] Error parsing direct HTML: {e}")
                is_blocked = True
                
        if is_blocked or not results:
            print("[AudibleScraper] Direct search blocked or returned no results. Falling back to DuckDuckGo search...")
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                
                import time
                max_attempts = 3
                raw_results = []
                for attempt in range(max_attempts):
                    try:
                        with DDGS() as ddgs:
                            ddg_query = f"site:audible.com {query}"
                            print(f"[AudibleScraper] DDGS fallback attempt {attempt + 1}: querying '{ddg_query}'...")
                            raw_results = list(ddgs.images(ddg_query, safesearch='off', max_results=limit))
                        if len(raw_results) > 0:
                            break
                    except Exception as e:
                        print(f"[AudibleScraper] DDGS fallback attempt {attempt + 1} failed: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(1.0)
                    
                for res in raw_results:
                    title = res.get("title", "")
                    for suffix in [" | Audible.com", " - Audiobook - Audible.com", " - Audible.com", " (Audiobook) | Audible.com"]:
                        if title.endswith(suffix):
                            title = title[:-len(suffix)].strip()
                            
                    image_url = res.get("image", "")
                    if image_url:
                        image_url = re.sub(r'\._[^.]+_(?=\.[a-z]+)', '', image_url, flags=re.IGNORECASE)
                        
                    page_url = res.get("url", "")
                    book_id = ""
                    match = re.search(r'/pd/(?:[^/]+/)?([A-Z0-9]{10})', page_url)
                    if match:
                        book_id = match.group(1)
                        
                    results.append({
                        "image": image_url,
                        "url": page_url,
                        "width": res.get("width", 500),
                        "height": res.get("height", 500),
                        "title": f"[Audible] {title}".strip(),
                        "type": "book",
                        "id": book_id
                    })
                print(f"[AudibleScraper] Found {len(results)} items via DuckDuckGo fallback")
            except Exception as e:
                print(f"[AudibleScraper] DuckDuckGo fallback search failed: {e}")
                
        return results[:limit]

class AudibleSearchWorker(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query
        
    def run(self):
        try:
            scraper = AudibleScraper()
            results = scraper.search(self.query)
            self.results_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
