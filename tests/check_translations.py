import os
import re
import json
from pathlib import Path

def get_translation_keys_from_code(project_root):
    """Scan .py files for tr('key') or tr("key") patterns."""
    keys = set()
    # Matches tr('key'), tr('key', ...), tr("key"), etc.
    pattern = re.compile(r"tr\(['\"]([^'\"]+)['\"]")
    
    for root, _, files in os.walk(project_root):
        if "_build_" in root or ".venv" in root or "__pycache__" in root or ".git" in root:
            continue
            
        for file in files:
            if file.endswith(".py") and file != "check_translations.py":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        found = pattern.findall(content)
                        for key in found:
                            keys.add(key)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
                    
    return keys

def check_key_in_translations(key, translations):
    """Check if a dot-separated key exists in the translations dict."""
    parts = key.split('.')
    current = translations
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False
    return True

def main():
    # Assuming the script is in SPAudiobookPlayer/tests/
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    translations_dir = project_root / 'resources' / 'translations'
    
    print(f"Project root: {project_root}")
    print(f"Translations dir: {translations_dir}")
    print("-" * 50)
    
    # 1. Get keys from code
    code_keys = get_translation_keys_from_code(project_root)
    print(f"Found {len(code_keys)} unique translation keys in code.")
    
    # 2. Get translation files
    translation_files = list(translations_dir.glob("*.json"))
    if not translation_files:
        print("No translation files found!")
        return
        
    # 3. Check each file
    total_missing = 0
    for trans_file in translation_files:
        lang_code = trans_file.stem
        print(f"\nChecking language: {lang_code.upper()} ({trans_file.name})")
        
        try:
            with open(trans_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except Exception as e:
            print(f"  Error loading {trans_file.name}: {e}")
            continue
            
        missing_keys = []
        for key in sorted(code_keys):
            if not check_key_in_translations(key, translations):
                missing_keys.append(key)
                
        if missing_keys:
            print(f"  [MISSING] Found {len(missing_keys)} missing keys:")
            for key in missing_keys:
                print(f"    - {key}")
            total_missing += len(missing_keys)
        else:
            print("  [OK] All keys found!")
            
    if total_missing == 0:
        print("\n[SUCCESS] Everything is translated!")
    else:
        print(f"\n[WARNING] Total missing keys across all languages: {total_missing}")

if __name__ == "__main__":
    main()
