import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

db_path = Path("data/audiobooks.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT path, parent_path, name, year_recorded FROM audiobooks WHERE is_folder = 0")
books = c.fetchall()

parent_years = defaultdict(set)
for path, parent_path, name, year in books:
    if parent_path:
        parent_years[parent_path].add(year)

for p, years in parent_years.items():
    if len(years) > 1:
        non_empty = [y for y in years if y]
        if len(non_empty) > 1:
            print(f"Folder: '{p}' has years: {years}")
