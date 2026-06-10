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

# Gather all non-folder items
all_books = []
for parent_path, items in cached_library_data.items():
    for item_data in items:
        if item_data["is_folder"]:
            continue
        item_copy = item_data.copy()
        item_copy["parent_path"] = parent_path
        all_books.append(item_copy)

# Sort by name, ASC
all_books_asc = sorted(
    all_books,
    key=make_sort_key("name", False),
    reverse=False
)

# Sort by name, DESC
all_books_desc = sorted(
    all_books,
    key=make_sort_key("name", True),
    reverse=True
)

print("=== FLAT SORT BY NAME (ASCENDING) ===")
for i, book in enumerate(all_books_asc):
    print(f"{i+1:02d}. Name: '{book['name']}' | Parent: '{book['parent_path']}'")

print("\n=== FLAT SORT BY NAME (DESCENDING) ===")
for i, book in enumerate(all_books_desc):
    print(f"{i+1:02d}. Name: '{book['name']}' | Parent: '{book['parent_path']}'")
