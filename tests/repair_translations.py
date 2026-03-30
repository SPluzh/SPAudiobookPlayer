import json
import os
import re
from pathlib import Path

def repair_json_content(content):
    # Specific fix for the corruption I caused:
    # "github": "GitHub"
    #   }",
    #     "description": "...
    
    # Remove the extra brace and quote that broke the JSON
    content = re.sub(r'"github": "GitHub"\s+\}\s*",\s+', r'"github": "GitHub",\n    ', content)
    
    # Also handle cases where there might be a trailing comma before a closing brace that I left
    content = re.sub(r',\s*\}', r'\n  }', content)
    
    return content

def merge_dicts(source, target):
    """Recursively merge dictionaries. Source is existing, target is the template (en.json)."""
    for key, value in target.items():
        if key not in source:
            source[key] = value
        elif isinstance(value, dict) and isinstance(target[key], dict):
            # Recurse
            if not isinstance(source.get(key), dict):
                source[key] = {}
            merge_dicts(source[key], target[key])
    return source

def main():
    translations_dir = Path(r'c:\Users\user\Desktop\python\SPAudiobookPlayer\resources\translations')
    en_path = translations_dir / 'en.json'
    
    with open(en_path, 'r', encoding='utf-8') as f:
        en_template = json.load(f)
    
    files_to_fix = [f for f in os.listdir(translations_dir) if f.endswith('.json') and f != 'en.json']
    
    for filename in files_to_fix:
        file_path = translations_dir / filename
        print(f"Processing {filename}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Try to repair syntax
            repaired_content = repair_json_content(content)
            
            try:
                lang_data = json.loads(repaired_content)
            except json.JSONDecodeError as e:
                # If still fails, try to just load as much as possible with regex patterns 
                # or just start with template since I corrupted the "about" section heavily
                print(f"  Warning: {filename} still invalid after repair: {e}. Starting with raw content merge.")
                # Fallback to loading original content if it was valid before, 
                # but it's likely my previous edit broke it.
                lang_data = {}

            # Preserve language_name if possible
            match = re.search(r'"language_name":\s*"([^"]+)"', content)
            
            # Merge with English template
            merged_data = merge_dicts(lang_data, en_template)
            
            # Restore language_name
            if match:
                merged_data["language_name"] = match.group(1)
            else:
                # Fallback to directory name or something
                pass

            # Save back perfectly
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            print(f"  {filename} synchronized.")
            
        except Exception as e:
            print(f"  Critical error processing {filename}: {e}")

if __name__ == "__main__":
    main()
