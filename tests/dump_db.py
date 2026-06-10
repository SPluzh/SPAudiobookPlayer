import sqlite3
import sys
from pathlib import Path

# Reconfigure stdout to use utf-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

db_path = Path(r"c:\Users\user\Desktop\python\SPAudiobookPlayer\data\audiobooks.db")

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get column names
cursor.execute("PRAGMA table_info(audiobooks)")
columns = [row[1] for row in cursor.fetchall()]

# Get all records
cursor.execute("SELECT * FROM audiobooks")
rows = cursor.fetchall()
conn.close()

audiobooks = []
for row in rows:
    audiobooks.append(dict(zip(columns, row)))

# Filter for books (not folders) and available
books = [b for b in audiobooks if b.get("is_folder") == 0 and b.get("is_available") == 1]

print(f"Total books found: {len(books)}")
for i, book in enumerate(books):
    print(f"Book {i+1}: ID={book.get('id')}, Path={book.get('path')}, Parent={book.get('parent_path')}, Name={book.get('name')}, Author={book.get('author')}, Title={book.get('title')}, TimeAdded={book.get('time_added')}")
