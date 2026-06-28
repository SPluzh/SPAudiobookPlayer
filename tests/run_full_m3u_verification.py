"""
Полная автоматическая верификация сценариев M3U (Часть 1) согласно M3U_PART1_VERIFY.md.
"""
import sys
import os
import shutil
import sqlite3
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем корень проекта в пути
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner import AudiobookScanner
from database import init_database

def create_dummy_mp3(path: Path):
    # Минимальный заголовок MP3 фрейма для прохождения базовых проверок mutagen
    # 0xFF 0xFB означает MPEG-1 Layer 3, без защиты CRC
    path.write_bytes(b"\xFF\xFB" + b"\x00" * 3000)

def run_verification():
    print("=" * 60)
    print("🚀 НАЧАЛО АВТОМАТИЧЕСКОЙ ВЕРИФИКАЦИИ M3U")
    print("=" * 60)

    # 1. Создаем временную директорию для библиотеки и БД
    temp_dir = Path(tempfile.mkdtemp())
    db_file = temp_dir / "test_audiobooks.db"
    config_file = temp_dir / "settings.ini"

    # Создаем settings.ini
    config_file.write_text(f"""[Paths]
library={temp_dir}
database={db_file}
ffprobe=ffprobe
""", encoding="utf-8")

    # Инициализируем БД
    init_database(db_file, log_func=None)

    # --- Подготовка тестового окружения по сценариям ---

    # Сценарий A: Папка с одним .m3u (локальные файлы)
    dir_a = temp_dir / "Author A - Title A [Narrator A]"
    dir_a.mkdir()
    create_dummy_mp3(dir_a / "01.mp3")
    create_dummy_mp3(dir_a / "02.mp3")
    m3u_a = dir_a / "playlist.m3u"
    m3u_a.write_text("#EXTM3U\n#EXTINF:999,Track 1\n01.mp3\n#EXTINF:888,Track 2\n02.mp3\n", encoding="utf-8")

    # Сценарий B: Папка с несколькими .m3u
    dir_b = temp_dir / "Author B - Collection B [Narrator B]"
    dir_b.mkdir()
    create_dummy_mp3(dir_b / "01.mp3")
    create_dummy_mp3(dir_b / "02.mp3")
    m3u_b1 = dir_b / "Book1.m3u"
    m3u_b1.write_text("#EXTM3U\n#EXTINF:10,Chapter 1\n01.mp3\n", encoding="utf-8")
    m3u_b2 = dir_b / "Book2.m3u"
    m3u_b2.write_text("#EXTM3U\n#EXTINF:20,Chapter 2\n02.mp3\n", encoding="utf-8")

    # Сценарий C: Standalone .m3u в корне (URL-стриминг)
    m3u_c = temp_dir / "Neoplatonism.m3u"
    m3u_c.write_text("#EXTM3U\n#EXTINF:3600,Plato State\nhttps://example.com/platon.mp3\n#EXTINF:-1,Aristotle Metaphysics\nhttps://example.com/aristotle.mp3\n", encoding="utf-8")

    # Сценарий D: Папка без .m3u (старое поведение)
    dir_d = temp_dir / "Author D - Title D [Narrator D]"
    dir_d.mkdir()
    create_dummy_mp3(dir_d / "01.mp3")

    # Сценарий E: Кириллика и CP1251
    dir_e = temp_dir / "Author E - Title E [Narrator E]"
    dir_e.mkdir()
    create_dummy_mp3(dir_e / "01.mp3")
    m3u_e = dir_e / "playlist.m3u"
    m3u_e.write_bytes("#EXTM3U\n#EXTINF:100,Кириллица\n01.mp3\n".encode("cp1251"))

    # Сценарий G: Неверная длительность в #EXTINF (должна быть перезаписана mutagen)
    dir_g = temp_dir / "Author G - Title G [Narrator G]"
    dir_g.mkdir()
    # Создадим mp3 файл покрупнее (но с фейковыми фреймами mutagen определит минимальный размер)
    create_dummy_mp3(dir_g / "01.mp3")
    m3u_g = dir_g / "playlist.m3u"
    # Записываем в #EXTINF явно неверную длительность 99999 секунд
    m3u_g.write_text("#EXTM3U\n#EXTINF:99999,Wrong Duration\n01.mp3\n", encoding="utf-8")

    # Mock для сетевых запросов (HTTP HEAD и partial GET в Сценарии C)
    mock_response_head = MagicMock()
    mock_response_head.headers = {'Content-Length': '1000000'}
    mock_response_head.__enter__.return_value = mock_response_head

    mock_response_range = MagicMock()
    # Возвращаем пустой mp3 заголовок для парсинга
    mock_response_range.read.return_value = b"\xFF\xFB" + b"\x00" * 5000
    mock_response_range.__enter__.return_value = mock_response_range

    def mock_urlopen(req, *args, **kwargs):
        # Если метод HEAD
        if isinstance(req, str):
            url = req
            method = 'GET'
        else:
            url = req.full_url
            method = req.method
        
        if method == 'HEAD':
            return mock_response_head
        else:
            return mock_response_range

    # Мок _analyze_files_parallel для обхода фейковых MP3 файлов в тестовом окружении
    def mock_analyze(self, files, conn=None, max_workers=4, verbose=False):
        return [{'duration': 123.45, 'bitrate': 128000, 'codec': 'mp3', 'is_vbr': False} for _ in files]

    # Запуск сканирования с моками
    print("⏳ Выполняем сканирование библиотеки...")
    with patch("urllib.request.urlopen", side_effect=mock_urlopen), \
         patch.object(AudiobookScanner, "_analyze_files_parallel", mock_analyze):
        scanner = AudiobookScanner(str(config_file))
        scanner._load_translations = lambda: None
        scanner.translations = {}
        total = scanner.scan_directory(temp_dir)
        print(f"✅ Сканирование завершено. Обработано книг: {total}")

    # Подключение к БД для проверки результатов
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # --- ВЕРИФИКАЦИЯ ШАГОВ ---

    print("\n🔍 Шаг 0: Проверка схемы БД...")
    c.execute("PRAGMA table_info(audiobooks)")
    ab_cols = {row['name'] for row in c.fetchall()}
    assert "is_playlist" in ab_cols, "Missing columns in audiobooks table"
    assert "playlist_path" in ab_cols, "Missing columns in audiobooks table"

    c.execute("PRAGMA table_info(audiobook_files)")
    abf_cols = {row['name'] for row in c.fetchall()}
    assert "is_url" in abf_cols, "Missing columns in audiobook_files table"
    print("  [OK] Схема БД соответствует требованиям.")

    # --- Проверка Сценариев ---

    print("\n🔍 Сценарий A: Папка с одним .m3u (локальные файлы)...")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (str(dir_a.relative_to(temp_dir)),))
    row_a = c.fetchone()
    assert row_a is not None, "Scenario A audiobook not found"
    assert row_a['is_playlist'] == 1, "Should be marked as playlist"
    assert row_a['playlist_path'] == str(m3u_a.relative_to(temp_dir)), f"Incorrect playlist_path: {row_a['playlist_path']}"
    assert row_a['file_count'] == 2, f"Should have 2 files, got {row_a['file_count']}"
    assert row_a['author'] == "Author A", f"Author parsing failed: {row_a['author']}"
    assert row_a['title'] == "Title A", f"Title parsing failed: {row_a['title']}"
    assert row_a['narrator'] == "Narrator A", f"Narrator parsing failed: {row_a['narrator']}"
    print("  [OK] Сценарий A пройден.")

    print("\n🔍 Сценарий B: Папка с несколькими .m3u...")
    c.execute("SELECT * FROM audiobooks WHERE parent_path = ? ORDER BY path", (str(dir_b.relative_to(temp_dir)),))
    rows_b = c.fetchall()
    assert len(rows_b) == 2, f"Scenario B should produce 2 books, got {len(rows_b)}"
    assert rows_b[0]['path'] == str(m3u_b1.relative_to(temp_dir))
    assert rows_b[1]['path'] == str(m3u_b2.relative_to(temp_dir))
    assert rows_b[0]['is_playlist'] == 1
    assert rows_b[1]['is_playlist'] == 1
    print("  [OK] Сценарий B пройден.")

    print("\n🔍 Сценарий C: Standalone .m3u в корне (URL-стриминг)...")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (str(m3u_c.relative_to(temp_dir)),))
    row_c = c.fetchone()
    assert row_c is not None
    assert row_c['is_playlist'] == 1
    assert row_c['playlist_path'] == str(m3u_c.relative_to(temp_dir))
    
    # Проверка файлов URL
    c.execute("SELECT * FROM audiobook_files WHERE audiobook_id = ? ORDER BY track_number", (row_c['id'],))
    files_c = c.fetchall()
    assert len(files_c) == 2
    assert files_c[0]['is_url'] == 1
    assert files_c[1]['is_url'] == 1
    assert files_c[0]['file_path'] == "https://example.com/platon.mp3"
    assert files_c[0]['duration'] == 3600.0, f"Expected 3600.0 duration from #EXTINF, got {files_c[0]['duration']}"
    print("  [OK] Сценарий C пройден.")

    print("\n🔍 Сценарий D: Папка без .m3u (старое поведение)...")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (str(dir_d.relative_to(temp_dir)),))
    row_d = c.fetchone()
    assert row_d is not None
    assert row_d['is_playlist'] == 0, "Non-playlist folder should not have is_playlist=1"
    print("  [OK] Сценарий D пройден.")

    print("\n🔍 Сценарий E: Кириллика и CP1251...")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (str(dir_e.relative_to(temp_dir)),))
    row_e = c.fetchone()
    c.execute("SELECT * FROM audiobook_files WHERE audiobook_id = ?", (row_e['id'],))
    files_e = c.fetchall()
    assert files_e[0]['tag_title'] == "Кириллица", f"CP1251 decoding failed: {files_e[0]['tag_title']}"
    print("  [OK] Сценарий E пройден.")

    print("\n🔍 Сценарий G: Длительность локальных файлов (не из #EXTINF)...")
    c.execute("SELECT * FROM audiobooks WHERE path = ?", (str(dir_g.relative_to(temp_dir)),))
    row_g = c.fetchone()
    c.execute("SELECT * FROM audiobook_files WHERE audiobook_id = ?", (row_g['id'],))
    files_g = c.fetchall()
    # Длительность должна быть перезаписана mock_analyze на 123.45 секунд, а не 99999.0
    assert files_g[0]['duration'] == 123.45, f"Expected mocked duration 123.45, got {files_g[0]['duration']}"
    print("  [OK] Сценарий G пройден.")

    print("\n🔍 Сценарий F: Повторное сканирование (state_hash)...")
    c.execute("SELECT id, state_hash, time_added FROM audiobooks WHERE path = ?", (str(dir_a.relative_to(temp_dir)),))
    first_row = c.fetchone()
    first_id = first_row['id']
    first_hash = first_row['state_hash']
    first_added = first_row['time_added']

    # Повторный запуск сканирования
    with patch("urllib.request.urlopen", side_effect=mock_urlopen), \
         patch.object(AudiobookScanner, "_analyze_files_parallel", mock_analyze):
        scanner.scan_directory(temp_dir)

    c.execute("SELECT id, state_hash, time_added FROM audiobooks WHERE path = ?", (str(dir_a.relative_to(temp_dir)),))
    second_row = c.fetchone()
    assert second_row['id'] == first_id, "Audiobook record recreated with different ID"
    assert second_row['state_hash'] == first_hash, "State hash changed without file modification"
    assert second_row['time_added'] == first_added, "Time added updated during no-change scan"
    print("  [OK] Сценарий F пройден (сканирование идемпотентно).")

    # --- Проверка Антипаттернов (Шаг 5) ---

    print("\n🔍 Проверка антипаттернов...")
    
    # 1. Дубли одной и той же M3U-книги
    c.execute("""
        SELECT path, COUNT(*) cnt FROM audiobooks WHERE is_playlist=1
        GROUP BY path HAVING cnt > 1
    """)
    assert len(c.fetchall()) == 0, "Found duplicate playlist audiobooks!"

    # 2. M3U-книга с 0 треков
    c.execute("""
        SELECT a.path FROM audiobooks a
        LEFT JOIN audiobook_files f ON f.audiobook_id = a.id
        WHERE a.is_playlist=1
        GROUP BY a.id HAVING COUNT(f.id) = 0
    """)
    assert len(c.fetchall()) == 0, "Found M3U audiobook with 0 tracks!"

    # 3. URL-треки с is_url=0
    c.execute("""
        SELECT f.file_path FROM audiobook_files f
        WHERE f.file_path LIKE 'http%' AND f.is_url = 0
    """)
    assert len(c.fetchall()) == 0, "Found URL tracks with is_url=0!"

    # 4. Локальные треки с is_url=1
    c.execute("""
        SELECT f.file_path FROM audiobook_files f
        WHERE f.file_path NOT LIKE 'http%' AND f.is_url = 1
    """)
    assert len(c.fetchall()) == 0, "Found local tracks with is_url=1!"

    # 5. Обычные книги стали is_playlist=1
    c.execute("""
        SELECT COUNT(*) FROM audiobooks WHERE path = ? AND is_playlist = 1
    """, (str(dir_d.relative_to(temp_dir)),))
    assert c.fetchone()[0] == 0, "Non-playlist audiobook marked as is_playlist=1!"

    print("  [OK] Антипаттерны отсутствуют.")

    conn.close()
    
    # Очистка временных файлов
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("🎉 ВСЕ СЦЕНАРИИ ВЕРИФИКАЦИИ УСПЕШНО ПРОЙДЕНЫ!")
    print("=" * 60)

if __name__ == "__main__":
    run_verification()
