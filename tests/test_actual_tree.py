import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Reconfigure stdout to use utf-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# Ensure we can import modules from the project root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database import DatabaseManager
from library import LibraryWidget

app = QApplication([])

db_path = project_root / "data" / "audiobooks.db"
db = DatabaseManager(db_path)

# Mock config
config = {
    "audiobook_icon_size": 100,
    "folder_icon_size": 35,
    "sort_orders": {
        "all": "asc",
        "not_started": "desc",
        "in_progress": "desc",
        "completed": "desc"
    },
    "sort_fields": {
        "all": "name",
        "not_started": "time_added",
        "in_progress": "last_updated",
        "completed": "time_finished"
    }
}

widget = LibraryWidget(db_manager=db, config=config)

# 1. Test with show_folders = False
widget.show_folders = False
widget.current_filter = "all"
widget.load_audiobooks(use_cache=False)

print("=== ACTUAL TREE ITEMS (show_folders=False, filter=all, sort=name, asc) ===")
root = widget.tree.invisibleRootItem()
print(f"Tree child count: {root.childCount()}")
for i in range(root.childCount()):
    child = root.child(i)
    path = child.data(0, Qt.ItemDataRole.UserRole)
    item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
    # Get the title/author from UserRole+2
    metadata = child.data(0, Qt.ItemDataRole.UserRole + 2)
    author = metadata[0] if metadata else ""
    title = metadata[1] if metadata else ""
    print(f"{i+1:02d}. Type: {item_type} | Path: '{path}' | Author: '{author}' | Title: '{title}'")

# 2. Test with show_folders = False, filter = all, sort = time_added, desc
widget.sort_fields["all"] = "time_added"
widget.sort_orders["all"] = "desc"
widget.load_audiobooks(use_cache=False)

print("\n=== ACTUAL TREE ITEMS (show_folders=False, filter=all, sort=time_added, desc) ===")
root = widget.tree.invisibleRootItem()
print(f"Tree child count: {root.childCount()}")
for i in range(root.childCount()):
    child = root.child(i)
    path = child.data(0, Qt.ItemDataRole.UserRole)
    item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
    metadata = child.data(0, Qt.ItemDataRole.UserRole + 2)
    author = metadata[0] if metadata else ""
    title = metadata[1] if metadata else ""
    print(f"{i+1:02d}. Type: {item_type} | Path: '{path}' | Author: '{author}' | Title: '{title}'")
