import os
import re
import json
from pathlib import Path

def get_translation_keys_from_code(project_root):
    """Scan .py files for tr('key') or tr("key") patterns."""
    keys = {} # key -> list of (file_path, line_number)
    # Matches tr('key'), tr('key', ...), tr("key"), etc.
    pattern = re.compile(r"tr\(['\"]([^'\"]+)['\"]")
    
    for root, _, files in os.walk(project_root):
        if "_build_" in root or ".venv" in root or "__pycache__" in root or ".git" in root or "tests" in root:
            continue
            
        for file in files:
            if file.endswith(".py") and file != "check_translations.py":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            found = pattern.findall(line)
                            for key in found:
                                if key not in keys:
                                    keys[key] = []
                                keys[key].append((file_path, line_num))
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

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}

def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def main():
    script_path = Path(__file__).resolve()
    # Adjust depending on where the script is located relative to project root
    # Expected: SPAudiobookPlayer/tests/check_translations.py -> project_root = SPAudiobookPlayer
    project_root = script_path.parent.parent 
    translations_dir = project_root / 'resources' / 'translations'
    
    print(f"Project root: {project_root}")
    print(f"Translations dir: {translations_dir}")
    print("-" * 50)
    
    # 1. Get keys from code
    print("Scanning code for 'tr(\"key\")' usage...")
    code_keys_map = get_translation_keys_from_code(project_root)
    code_keys = set(code_keys_map.keys())
    print(f"Found {len(code_keys)} unique translation keys in code.")

    # 2. Get translation files
    translation_files = list(translations_dir.glob("*.json"))
    if not translation_files:
        print("No translation files found!")
        return

    # Load English as reference if available
    en_file = translations_dir / "en.json"
    en_keys = set()
    if en_file.exists():
        en_data = load_json(en_file)
        en_keys = set(flatten_dict(en_data).keys())
        # Remove metadata keys
        if "language_name" in en_keys: en_keys.remove("language_name")
        print(f"Loaded English reference: {len(en_keys)} keys.")
    
    # 3. Check each file
    total_missing = 0
    
    for trans_file in translation_files:
        if trans_file.name == "missing_keys.json":
            continue
            
        lang_code = trans_file.stem
        print(f"\n[{lang_code.upper()}] Checking {trans_file.name}...")
        
        data = load_json(trans_file)
        file_keys_flat = flatten_dict(data)
        file_keys = set(file_keys_flat.keys())
        
        # A. Check against Code
        missing_in_file_from_code = []
        for k in sorted(code_keys):
            if k not in file_keys:
                missing_in_file_from_code.append(k)
        
        # B. Check against English (if not English itself)
        missing_in_file_from_en = []
        if lang_code != "en" and en_keys:
            for k in sorted(en_keys):
                if k not in file_keys:
                    # Don't double count if already missing from code
                    if k not in missing_in_file_from_code:
                        missing_in_file_from_en.append(k)

        # Report
        if missing_in_file_from_code:
            print(f"  !! Missing {len(missing_in_file_from_code)} keys used in CODE:")
            for k in missing_in_file_from_code:
                print(f"     - {k}")
            total_missing += len(missing_in_file_from_code)
            
        if missing_in_file_from_en:
            print(f"  !! Missing {len(missing_in_file_from_en)} keys present in ENGLISH but not here:")
            for k in missing_in_file_from_en:
                print(f"     - {k}")
            total_missing += len(missing_in_file_from_en)

        if not missing_in_file_from_code and not missing_in_file_from_en:
             print("  OK.")

    if total_missing == 0:
        print("\n[SUCCESS] All languages are valid and complete!")
    else:
        print(f"\n[WARNING] Found {total_missing} missing translations in total.")

if __name__ == "__main__":
    main()
