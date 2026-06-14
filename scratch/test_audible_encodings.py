import urllib.request
import urllib.parse

queries = [
    "Master and Margarita",
    "Мастер и Маргарита",
    "Мастер",
    "Bulgakov"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Referer': 'https://www.audible.com/'
}

for query in queries:
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.audible.com/search?keywords={encoded_query}"
    print(f"Testing query '{query}' -> {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"Success! Status: {response.getcode()}")
            html = response.read().decode('utf-8')
            if "productListItem" in html:
                print("Found product list items!")
            else:
                print("No product list items found.")
    except Exception as e:
        print(f"Failed: {e}")
