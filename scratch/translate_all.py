import os
import json
import time
import sys
import urllib.parse
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def translate(text, target_lang):
    # Google Translate single API
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                res = r.json()
                translated = "".join([part[0] for part in res[0] if part[0]])
                return translated
            else:
                print(f"  Warning: Status code {r.status_code} for {target_lang}")
        except Exception as e:
            print(f"  Error translating to {target_lang}: {e}")
        time.sleep(1.0)
    return None

def main():
    project_root = Path(__file__).resolve().parent.parent
    translations_dir = project_root / 'resources' / 'translations'
    
    en_file = translations_dir / "en.json"
    with open(en_file, 'r', encoding='utf-8') as f:
        en_data = json.load(f)
        
    appearance_en = en_data.get("appearance", {})
    tooltip_keys = [k for k in appearance_en.keys() if k.endswith("_tooltip")]
    
    print(f"Found {len(tooltip_keys)} tooltip keys to translate:")
    for k in tooltip_keys:
        print(f"  - {k}: {appearance_en[k]}")
        
    translation_files = list(translations_dir.glob("*.json"))
    skip_langs = {"en", "ru", "zh"}
    
    for trans_file in translation_files:
        lang_code = trans_file.stem
        if lang_code in skip_langs or lang_code == "missing_keys":
            continue
            
        print(f"\nProcessing {trans_file.name} (language: {lang_code})...")
        
        with open(trans_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if "appearance" not in data:
            data["appearance"] = {}
            
        appearance = data["appearance"]
        changed = False
        
        for k in tooltip_keys:
            # We translate if key doesn't exist, OR if it's equal to the English key (placeholder)
            current_val = appearance.get(k)
            english_val = appearance_en[k]
            
            if not current_val or current_val == english_val:
                print(f"  Translating key '{k}' to '{lang_code}'...")
                translated_val = translate(english_val, lang_code)
                if translated_val:
                    appearance[k] = translated_val
                    changed = True
                    print(f"    -> {translated_val}")
                    time.sleep(0.3)  # Be nice to Google Translate
                else:
                    print(f"    FAILED to translate '{k}'")
                    
        if changed:
            # Write back maintaining indent of 2 (which is the standard format for the JSON files)
            with open(trans_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Saved updates to {trans_file.name}")
        else:
            print(f"  No updates needed for {trans_file.name}")

if __name__ == "__main__":
    main()
