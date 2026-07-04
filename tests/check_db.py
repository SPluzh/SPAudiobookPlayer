"""Quick diagnostic script to check database state for library display issues"""
import sqlite3
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')

db_path = r'c:\Users\user\Desktop\python\SPAudiobookPlayer\src\data\audiobooks.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Basic counts
c.execute('SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0')
total_books = c.fetchone()[0]
print(f"Total books: {total_books}")

c.execute('SELECT COUNT(*) FROM audiobooks WHERE is_folder = 1')
total_folders = c.fetchone()[0]
print(f"Total folders: {total_folders}")

c.execute('SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_available = 1')
available_books = c.fetchone()[0]
print(f"Available books: {available_books}")

c.execute('SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_available = 0')
unavailable_books = c.fetchone()[0]
print(f"Unavailable books: {unavailable_books}")

# Check parent_path distribution
c.execute("SELECT parent_path, COUNT(*) FROM audiobooks WHERE is_folder = 0 GROUP BY parent_path ORDER BY COUNT(*) DESC LIMIT 20")
print("\nTop 20 parent_paths for books:")
for row in c.fetchall():
    pp = repr(row[0])
    # Truncate long paths for readability
    if len(pp) > 80:
        pp = pp[:77] + '...'
    print(f"  {pp}: {row[1]} books")

# Check root-level items (parent_path = '' or NULL)
c.execute("SELECT COUNT(*) FROM audiobooks WHERE parent_path = ''")
root_empty = c.fetchone()[0]
print(f"\nItems with parent_path='': {root_empty}")

c.execute("SELECT COUNT(*) FROM audiobooks WHERE parent_path IS NULL")
root_null = c.fetchone()[0]
print(f"Items with parent_path=NULL: {root_null}")

# Check root folders specifically
c.execute("SELECT name, path FROM audiobooks WHERE is_folder = 1 AND (parent_path = '' OR parent_path IS NULL) LIMIT 10")
root_folders = c.fetchall()
print(f"\nRoot folders (first 10): {len(root_folders)}")
for name, path in root_folders:
    c.execute("SELECT COUNT(*) FROM audiobooks WHERE parent_path = ?", (path,))
    child_count = c.fetchone()[0]
    if len(path) > 60:
        path = path[:57] + '...'
    print(f"  '{name}' (path='{path}'): {child_count} children")

# Check filter counts
c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_started = 1 AND is_completed = 0 AND is_available = 1")
in_progress = c.fetchone()[0]
print(f"\nIn progress: {in_progress}")

c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_completed = 1 AND is_available = 1")
completed = c.fetchone()[0]
print(f"Completed: {completed}")

c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_started = 0 AND is_available = 1")
not_started = c.fetchone()[0]
print(f"Not started: {not_started}")

# Check if any books have very deep nesting
c.execute("SELECT parent_path, LENGTH(parent_path) as len FROM audiobooks WHERE is_folder = 0 ORDER BY len DESC LIMIT 5")
print("\nDeepest nested books:")
for row in c.fetchall():
    pp = row[0] or ''
    depth = pp.count('\\') + pp.count('/') if pp else 0
    if len(pp) > 80:
        pp = pp[:77] + '...'
    print(f"  depth={depth}, parent_path='{pp}' (len={row[1]})")

# Check total audiobooks count
c.execute("SELECT COUNT(*) FROM audiobooks")
total_all = c.fetchone()[0]
print(f"\nTotal records (folders + books): {total_all}")

# Check how many unique parent_paths exist
c.execute("SELECT COUNT(DISTINCT parent_path) FROM audiobooks")
unique_parents = c.fetchone()[0]
print(f"Unique parent_paths: {unique_parents}")

# Check max recursion depth needed
c.execute("""
    SELECT a.path, a.parent_path, a.name, a.is_folder 
    FROM audiobooks a 
    WHERE a.parent_path NOT IN (SELECT path FROM audiobooks WHERE is_folder = 1) 
    AND a.parent_path != '' 
    AND a.parent_path IS NOT NULL
    LIMIT 10
""")
orphans = c.fetchall()
if orphans:
    print(f"\nOrphaned items (parent_path doesn't match any folder):")
    for path, pp, name, is_f in orphans:
        if len(pp) > 60:
            pp = pp[:57] + '...'
        print(f"  name='{name}', is_folder={is_f}, parent_path='{pp}'")
else:
    print("\nNo orphaned items found.")

conn.close()
