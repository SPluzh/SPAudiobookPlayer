import urllib.request
import urllib.parse
import re
import sys
from PyQt6.QtCore import QThread, pyqtSignal
from bs4 import BeautifulSoup

class GoodreadsScraper:
    BASE_URL = "https://www.goodreads.com"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.goodreads.com/'
    }
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        
    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.getcode() != 200:
                    print(f"[GoodreadsScraper] Fetch status {response.getcode()} for {url}")
                    return None
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"[GoodreadsScraper] Fetch error for {url}: {e}")
            return None

    def search(self, query: str, limit: int = 40) -> list:
        """
        Ищет книги на goodreads.com по поисковому запросу.
        Сначала пытается выполнить прямой парсинг HTML.
        Если запрос заблокирован WAF (Cloudflare/AWS WAF),
        переключается на поиск через DuckDuckGo Image Search.
        Возвращает список словарей, совместимый с CoverSearchResultWidget.
        """
        print(f"[GoodreadsScraper] Searching for '{query}'...")
        encoded_query = urllib.parse.quote(query)
        url = f"{self.BASE_URL}/search?q={encoded_query}"
        
        html = self._fetch(url)
        results = []
        
        is_blocked = True
        if html and "tableList" in html and "bookTitle" in html:
            is_blocked = False
            
        if not is_blocked:
            try:
                print("[GoodreadsScraper] Direct fetch succeeded. Parsing HTML...")
                soup = BeautifulSoup(html, 'html.parser')
                table = soup.find('table', class_='tableList')
                if table:
                    rows = table.find_all('tr', itemtype='http://schema.org/Book')
                    for row in rows:
                        title_link = row.find('a', class_='bookTitle')
                        if not title_link:
                            continue
                        
                        # Извлекаем заголовок
                        title = title_link.text.strip()
                        
                        # Извлекаем ссылку на страницу книги
                        page_path = title_link.get('href', '')
                        if page_path.startswith('/'):
                            page_url = f"{self.BASE_URL}{page_path}"
                        else:
                            page_url = page_path
                            
                        # Извлекаем авторов
                        author_links = row.find_all('a', class_='authorName')
                        authors = [a.text.strip() for a in author_links if a.text]
                        authors_str = ", ".join(authors) if authors else ""
                        
                        # Извлекаем обложку
                        img_tag = row.find('img', class_='bookCover')
                        cover_url = ""
                        if img_tag:
                            cover_url = img_tag.get('src', '')
                            # Преобразуем в ссылку на оригинальное/большое изображение
                            if cover_url:
                                cover_url = re.sub(r'\._S[XY]\d+_\.', '.', cover_url)
                                
                        # Извлекаем ID книги
                        book_id = ""
                        match = re.search(r'/book/show/(\d+)', page_path)
                        if match:
                            book_id = match.group(1)
                            
                        results.append({
                            "image": cover_url,
                            "url": page_url,
                            "width": 300,
                            "height": 450,
                            "title": f"[Goodreads] {title} - {authors_str}".strip(),
                            "type": "book",
                            "id": book_id
                        })
                print(f"[GoodreadsScraper] Parsed {len(results)} books from direct search")
            except Exception as e:
                print(f"[GoodreadsScraper] Error parsing direct HTML: {e}")
                is_blocked = True  # Переключение на DDG при ошибке парсинга
                
        if is_blocked or not results:
            print("[GoodreadsScraper] Direct search blocked or returned no results. Falling back to DuckDuckGo search...")
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                    
                with DDGS() as ddgs:
                    ddg_query = f"site:goodreads.com {query}"
                    raw_results = list(ddgs.images(ddg_query, safesearch='off', max_results=limit))
                    
                for res in raw_results:
                    title = res.get("title", "")
                    if title.endswith(" | Goodreads"):
                        title = title[:-12].strip()
                        
                    image_url = res.get("image", "")
                    if image_url:
                        # Убедимся, что изображение в максимальном разрешении
                        image_url = re.sub(r'\._S[XY]\d+_\.', '.', image_url)
                        
                    page_url = res.get("url", "")
                    book_id = ""
                    match = re.search(r'/book/show/(\d+)', page_url)
                    if match:
                        book_id = match.group(1)
                        
                    results.append({
                        "image": image_url,
                        "url": page_url,
                        "width": res.get("width", 300),
                        "height": res.get("height", 450),
                        "title": f"[Goodreads] {title}".strip(),
                        "type": "book",
                        "id": book_id
                    })
                print(f"[GoodreadsScraper] Found {len(results)} items via DuckDuckGo fallback")
            except Exception as e:
                print(f"[GoodreadsScraper] DuckDuckGo fallback search failed: {e}")
                
        return results[:limit]


class GoodreadsSearchWorker(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query
        
    def run(self):
        try:
            scraper = GoodreadsScraper()
            results = scraper.search(self.query)
            self.results_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
