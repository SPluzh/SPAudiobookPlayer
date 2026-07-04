import sys
import sqlite3
from pathlib import Path

# Reconfigure stdout to use utf-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# Mock or use actual DatabaseManager
sys.path.append(str(Path(__file__).parent.parent / "src"))
# pyrefly: ignore [missing-import]
from database import DatabaseManager

db_path = Path(__file__).resolve().parent.parent / "src" / "data" / "audiobooks.db"
db = DatabaseManager(db_path)

# Let's mock the sorting key and sort behavior from library.py
def make_sort_key(field, reverse):
    def key_fn(x):
        is_folder = x.get("is_folder", False)
        if is_folder:
            val = (x.get("name") or "").lower()
            return (1, val) if reverse else (0, val)
        
        val = x.get(field)
        is_empty = (val is None or val == "")
        
        if is_empty:
            return (0, "") if reverse else (1, "")
        
        if field in ("name", "author"):
            val = str(val).lower()
        else:
            if isinstance(val, (int, float)):
                pass
            else:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = str(val)
        
        return (1, val) if reverse else (0, val)
    return key_fn

def simulate_flat_load(sort_field, sort_order):
    cached_library_data = db.load_audiobooks_from_db('all')
    all_items = []
    for parent_path, items in cached_library_data.items():
        for item_data in items:
            if item_data["is_folder"]:
                continue
            # Store parent_path inside item_data for printing
            item_data["parent_path"] = parent_path
            all_items.append(item_data)
            
    reverse_sort = (sort_order == "desc")
    # Two-pass stable sort from library.py
    all_items.sort(key=lambda x: (x.get("name") or "").lower())
    all_items.sort(
        key=make_sort_key(sort_field, reverse_sort),
        reverse=reverse_sort
    )
    return all_items

print("=== SORTING BY name, asc ===")
sorted_books = simulate_flat_load("name", "asc")
for i, book in enumerate(sorted_books):
    print(f"{i+1:02d}. Name: '{book['name']}' | Parent: '{book['parent_path']}'")

print("\n=== SORTING BY time_added, desc ===")
sorted_books = simulate_flat_load("time_added", "desc")
for i, book in enumerate(sorted_books):
    print(f"{i+1:02d}. Name: '{book['name']}' | Date: '{book['time_added']}' | Parent: '{book['parent_path']}'")
