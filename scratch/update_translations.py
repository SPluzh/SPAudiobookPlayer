import os
import json
from pathlib import Path

def main():
    project_root = Path(r"c:\Users\user\Desktop\python\SPAudiobookPlayer")
    translations_dir = project_root / "resources" / "translations"
    
    for p in translations_dir.glob("*.json"):
        if p.name == "missing_keys.json":
            continue
        print(f"Updating {p.name}...")
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "delegate" in data:
                # Insert keys in the delegate dict
                delegate = data["delegate"]
                # We can place them after separator or just add them
                delegate["year_written_prefix"] = "✍️"
                delegate["year_recorded_prefix"] = "💿"
                delegate["language_prefix"] = "🌐"
            
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                # Add a trailing newline to match git style
                f.write("\n")
                
        except Exception as e:
            print(f"Error updating {p.name}: {e}")

if __name__ == "__main__":
    main()
