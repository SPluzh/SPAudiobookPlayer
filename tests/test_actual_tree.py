import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from database import DatabaseManager
from library import LibraryWidget

app = QApplication([])

db_path = project_root / "src" / "data" / "audiobooks.db"
db = DatabaseManager(db_path)

config = {
    "audiobook_icon_size": 100,
    "folder_icon_size": 35,
    "sort_orders": {"all": "asc"},
    "sort_fields": {"all": "name"}
}

widget = LibraryWidget(db_manager=db, config=config)
widget.show_folders = True

def print_books_in(target_path):
    root = widget.tree.invisibleRootItem()
    
    # First find the item matching target_path
    target_item = None
    def find_item(item):
        nonlocal target_item
        for i in range(item.childCount()):
            child = item.child(i)
            path = child.data(0, Qt.ItemDataRole.UserRole)
            if path == target_path:
                target_item = child
                return
            find_item(child)
            if target_item:
                return
    
    find_item(root)
    if not target_item:
        print(f"Target path '{target_path}' not found in tree.")
        return
        
    for i in range(target_item.childCount()):
        child = target_item.child(i)
        path = child.data(0, Qt.ItemDataRole.UserRole)
        item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
        name = child.text(0)
        
        db_row = None
        for p_path, items in widget.cached_library_data.items():
            for it in items:
                if it["path"] == path:
                    db_row = it
                    break
            if db_row:
                break
        
        metadata_str = ""
        if db_row:
            metadata_str = f"Recorded: {db_row.get('year_recorded')}, Written: {db_row.get('year_written')}, Lang: {db_row.get('language')}"
        
        print(f"- [{item_type.upper()}] Name: '{name}' | Path: '{path}' | {metadata_str}")

widget.sort_field = "year_recorded"
widget.sort_order = "asc"
widget.load_audiobooks(use_cache=False)
print("\n=== ASCENDING ORDER (sort=year_recorded) ===")
print_books_in(r"Макс Фрай\3. Сновидения Ехо")

widget.sort_order = "desc"
widget.load_audiobooks(use_cache=True)
print("\n=== DESCENDING ORDER (sort=year_recorded) ===")
print_books_in(r"Макс Фрай\3. Сновидения Ехо")
