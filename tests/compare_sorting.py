import sys
from pathlib import Path

# Reconfigure stdout to use utf-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# Ensure we can import modules from the project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database import DatabaseManager

db_path = project_root / "data" / "audiobooks.db"
db = DatabaseManager(db_path)

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

# Load items from DB
cached_library_data = db.load_audiobooks_from_db('all')

# 1. Gather all non-folder items (which are naturally ordered by parent folder first in the dict)
all_items_old = []
all_items_new = []
for parent_path, items in cached_library_data.items():
    for item_data in items:
        if item_data["is_folder"]:
            continue
        item_data_copy = item_data.copy()
        item_data_copy["parent_path"] = parent_path
        all_items_old.append(item_data_copy)
        all_items_new.append(item_data_copy.copy())

# Sort field and order to test: time_added, desc
sort_field = "time_added"
reverse_sort = True

# --- OLD LOGIC ---
# Single-pass sort
all_items_old.sort(
    key=make_sort_key(sort_field, reverse_sort),
    reverse=reverse_sort
)

# --- NEW LOGIC ---
# Two-pass stable sort: 1st by name (asc), 2nd by primary key (desc)
all_items_new.sort(key=lambda x: (x.get("name") or "").lower())
all_items_new.sort(
    key=make_sort_key(sort_field, reverse_sort),
    reverse=reverse_sort
)

print("=== OLD LOGIC (Single-Pass Sorting by time_added, desc) ===")
print("Notice how items with the same '2026-06-02 22:40:48/49' timestamp remain grouped by their parent folder:")
for i, book in enumerate(all_items_old):
    print(f"{i+1:02d}. Date: '{book['time_added']}' | Parent: '{book['parent_path']}' | Name: '{book['name']}'")

print("\n=== NEW LOGIC (Two-Pass Stable Sorting with Name Tie-Breaker) ===")
print("Notice how items are sorted alphabetically by name within identical timestamps, breaking folder groupings:")
for i, book in enumerate(all_items_new):
    print(f"{i+1:02d}. Date: '{book['time_added']}' | Parent: '{book['parent_path']}' | Name: '{book['name']}'")
