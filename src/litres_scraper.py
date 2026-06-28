import urllib.request
import urllib.parse
import json
import re
import sys
from PyQt6.QtCore import QThread, pyqtSignal

class LitresScraper:
    BASE_URL = "https://www.litres.ru"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.litres.ru/'
    }
    
    def __init__(self, timeout=15):
        self.timeout = timeout
        
    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"[LitresScraper] Fetch error for {url}: {e}")
            return None

    def search(self, query: str, limit: int = 40) -> list:
        """
        Ищет книги на litres.ru по поисковому запросу.
        Возвращает список словарей, совместимый с CoverSearchResultWidget.
        """
        print(f"[LitresScraper] Searching for '{query}'...")
        encoded_query = urllib.parse.quote(query)
        # Ищем по аудиокнигам и тексту для получения нужного типа обложек
        url = f"{self.BASE_URL}/search/?q={encoded_query}&art_types=audiobook&art_types=text_book"
        
        html = self._fetch(url)
        if not html:
            return []
            
        # Поиск __NEXT_DATA__
        pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            pattern_alt = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
            match = re.search(pattern_alt, html, re.DOTALL)
            
        if not match:
            print("[LitresScraper] Could not find __NEXT_DATA__ in HTML search results.")
            return []
            
        try:
            json_str = match.group(1).strip()
            data = json.loads(json_str)
            
            # Достаем initialState
            initial_state_raw = data.get("props", {}).get("pageProps", {}).get("initialState", "")
            if isinstance(initial_state_raw, str):
                initial_state = json.loads(initial_state_raw)
            else:
                initial_state = initial_state_raw
                
            queries = initial_state.get("rtkqApi", {}).get("queries", {})
            asset_prefix = data.get("assetPrefix", "https://cdn.litres.ru")
            if not asset_prefix.startswith("http"):
                asset_prefix = "https://cdn.litres.ru"
                
            search_items = []
            
            # Ищем ключ, содержащий поисковые данные
            for key, val in queries.items():
                if key.startswith("getSearchData"):
                    query_data = val.get("data", {})
                    items = query_data.get("data", [])
                    if items:
                        search_items = items
                        break
            
            results = []
            for item in search_items:
                instance = item.get("instance", {})
                if not instance:
                    continue
                    
                book_id = instance.get("id")
                title = instance.get("title", "")
                cover_path = instance.get("cover_url", "")
                
                if not cover_path or not book_id:
                    continue
                    
                # Получаем полный URL обложки
                # cover_path обычно "/pub/c/cover/12345.jpg"
                if cover_path.startswith("/"):
                    cover_url = f"{asset_prefix}{cover_path}"
                else:
                    cover_url = f"{asset_prefix}/{cover_path}"
                    
                page_path = instance.get("url", "")
                if page_path.startswith("/"):
                    page_url = f"{self.BASE_URL}{page_path}"
                else:
                    page_url = f"{self.BASE_URL}/{page_path}"
                    
                width = instance.get("cover_width", 300)
                height = instance.get("cover_height", 400)
                art_type = item.get("type", "text_book") # e.g. "audiobook", "text_book"
                
                # Получаем авторов и исполнителей
                persons = instance.get("persons", [])
                authors = [p.get("full_name", "") for p in persons if p.get("role") == "author"]
                readers = [p.get("full_name", "") for p in persons if p.get("role") == "reader"]
                
                # Формируем красивый заголовок для отображения (включая автора и формат)
                authors_str = ", ".join(authors) if authors else ""
                readers_str = f" (Чтец: {', '.join(readers)})" if readers else ""
                
                # Для совместимости с UI
                results.append({
                    "image": cover_url,
                    "url": page_url,
                    "width": width,
                    "height": height,
                    "title": f"[{art_type.replace('_', ' ').title()}] {title} - {authors_str}{readers_str}".strip(),
                    "type": art_type,
                    "id": book_id
                })
                
            # Сортируем результаты: сначала аудиокниги, затем все остальное
            results.sort(key=lambda x: 0 if x.get("type") == "audiobook" else 1)
            
            # Удаляем дубликаты обложек, сохраняя приоритет (аудиокниги будут первыми)
            seen_covers = set()
            deduplicated_results = []
            for item in results:
                cover_url = item.get("image")
                if cover_url:
                    if cover_url in seen_covers:
                        continue
                    seen_covers.add(cover_url)
                deduplicated_results.append(item)
            results = deduplicated_results
            
            print(f"[LitresScraper] Search completed. Found {len(results)} items.")
            return results[:limit]
            
        except Exception as e:
            print(f"[LitresScraper] Error parsing search results: {e}")
            import traceback
            traceback.print_exc()
            return []


class LitresSearchWorker(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query
        
    def run(self):
        try:
            scraper = LitresScraper()
            results = scraper.search(self.query)
            self.results_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
