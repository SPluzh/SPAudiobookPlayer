"""
Быстрая проверка данных M3U-книг в БД после сканирования.
Запуск: python tests/verify_m3u_scan.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import configparser

cfg = configparser.ConfigParser()
cfg.read("src/resources/settings.ini", encoding="utf-8")
db_path = cfg.get("Paths", "database", fallback="src/data/audiobooks.db")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 60)
print("📚 M3U-книги в audiobooks:")
print("=" * 60)
try:
    c.execute("""
        SELECT id, path, name, author, file_count, duration,
               is_playlist, playlist_path, is_available
        FROM audiobooks
        WHERE is_playlist = 1
        ORDER BY time_added DESC
    """)
    books = c.fetchall()
except sqlite3.OperationalError as e:
    print(f"  ❌ Ошибка SQL: {e}")
    books = []

if not books:
    print("  ⚠️  Нет M3U-книг в БД!")
else:
    for b in books:
        print(f"\n  ID: {b['id']}")
        print(f"  path:          {b['path']}")
        print(f"  name:          {b['name']}")
        print(f"  author:        {b['author']}")
        print(f"  file_count:    {b['file_count']}")
        print(f"  duration:      {b['duration']:.1f}s ({b['duration']/60:.1f} мин)")
        print(f"  is_playlist:   {b['is_playlist']}")
        print(f"  playlist_path: {b['playlist_path']}")
        print(f"  is_available:  {b['is_available']}")

    print("\n" + "=" * 60)
    print("🎵 Треки M3U-книг в audiobook_files:")
    print("=" * 60)
    for b in books:
        c.execute("""
            SELECT track_number, file_path, file_name, duration,
                   tag_title, is_url
            FROM audiobook_files
            WHERE audiobook_id = ?
            ORDER BY track_number
        """, (b['id'],))
        files = c.fetchall()
        print(f"\n  [{b['name']}] — {len(files)} треков:")
        for f in files:
            url_mark = " 🌐URL" if f['is_url'] else ""
            dur = f['duration']
            print(f"    #{f['track_number']:02d}  {f['file_name'][:50]:<50} "
                  f"{dur:7.1f}s  {str(f['tag_title'] or '')[:30]}{url_mark}")

conn.close()
print("\n✅ Готово.")
