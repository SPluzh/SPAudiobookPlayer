import sys
import requests
import urllib.parse
import json

sys.stdout.reconfigure(encoding='utf-8')

def translate(text, target_lang):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            res = r.json()
            # The structure of the result is [[[translated_text, source_text, ...]]]
            translated = "".join([part[0] for part in res[0] if part[0]])
            return translated
    except Exception as e:
        print(f"Error translating to {target_lang}: {e}")
    return None

print("AR:", translate("Accent color for active elements, selections, and highlights", "ar"))
print("DE:", translate("Accent color for active elements, selections, and highlights", "de"))
