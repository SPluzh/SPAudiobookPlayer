import os
import sys
from pathlib import Path
import mutagen
from mutagen import File

# Ensure output encoding is UTF-8
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

share_path = r"\\vmware-host\Shared Folders\аудиокниги"
count = 0

print("Scanning network share for tag inspection...")
for root, dirs, files in os.walk(share_path):
    for f in files:
        ext = Path(f).suffix.lower()
        if ext in ('.mp3', '.m4b', '.m4a', '.flac'):
            path = os.path.join(root, f)
            try:
                a = File(path)
                if a and a.tags:
                    keys = list(a.tags.keys())
                    print(f"\nFile: {f}")
                    print(f"Format keys: {keys}")
                    for k in keys:
                        val = str(a.tags[k])
                        # Print all keys except very long binary/text values (like covers)
                        if len(val) < 150:
                            print(f"  {k}: {val}")
                    count += 1
                    print("-" * 50)
            except Exception as e:
                print(f"Error reading {f}: {e}")
            if count >= 5:
                break
    if count >= 5:
        break
