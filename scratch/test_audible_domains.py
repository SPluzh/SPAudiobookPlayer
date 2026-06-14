import urllib.request

domains = [
    "https://www.audible.com",
    "https://www.audible.de",
    "https://www.audible.co.uk",
    "https://www.audible.ca"
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}

for domain in domains:
    url = f"{domain}/search?keywords=Margarita"
    print(f"Testing {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"Success for {domain}! Status: {response.getcode()}")
            html = response.read().decode('utf-8')
            print(f"Length of response: {len(html)}")
            if "productListItem" in html:
                print("Found product list items!")
            else:
                print("No product list items found.")
    except Exception as e:
        print(f"Failed for {domain}: {e}")
