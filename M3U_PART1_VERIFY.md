# M3U Сканер — План верификации БД

**Scope:** Часть 1. Только сканер + БД. Без воспроизведения.  
**Связь:** `M3U_PART1_SCANNER.md`

---

## 🗄️ Шаг 0 — Прямой SQL-доступ к БД

Перед запуском тестов — убедиться что миграции применились.  
БД лежит в `data/audiobooks.db` (путь из `settings.ini`).

```bash
# PowerShell — открыть БД через sqlite3 CLI
sqlite3 data/audiobooks.db ".schema audiobooks"
sqlite3 data/audiobooks.db ".schema audiobook_files"
```

### Ожидаемые колонки в `audiobooks`:
| Колонка | Тип | Дефолт |
|---------|-----|--------|
| `is_playlist` | INTEGER | 0 |
| `playlist_path` | TEXT | NULL |

### Ожидаемые колонки в `audiobook_files`:
| Колонка | Тип | Дефолт |
|---------|-----|--------|
| `is_url` | INTEGER | 0 |

**Если колонок нет → миграция не применилась.** Проверить `init_database()`.

---

## 🧪 Шаг 1 — Инструмент быстрой проверки (скрипт)

Создать скрипт `tests/verify_m3u_scan.py` для ручного запуска после сканирования:

```python
"""
Быстрая проверка данных M3U-книг в БД после сканирования.
Запуск: python tests/verify_m3u_scan.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import configparser

cfg = configparser.ConfigParser()
cfg.read("resources/settings.ini", encoding="utf-8")
db_path = cfg.get("Paths", "database", fallback="data/audiobooks.db")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 60)
print("📚 M3U-книги в audiobooks:")
print("=" * 60)
c.execute("""
    SELECT id, path, name, author, file_count, duration,
           is_playlist, playlist_path, is_available
    FROM audiobooks
    WHERE is_playlist = 1
    ORDER BY time_added DESC
""")
books = c.fetchall()
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
              f"{dur:7.1f}s  {f['tag_title'][:30]}{url_mark}")

conn.close()
print("\n✅ Готово.")
```

---

## 📋 Шаг 2 — Тест-матрица сценариев

### Сценарий A: Папка с одним .m3u (локальные файлы)

**Структура:**
```
Library/
└── Автор - Название [Чтец]/
    ├── playlist.m3u
    ├── 01.mp3
    └── 02.mp3
```

**Ожидаемые данные в `audiobooks`:**
| Поле | Значение |
|------|----------|
| `path` | `Автор - Название [Чтец]` (папка, не файл!) |
| `is_playlist` | `1` |
| `playlist_path` | `Автор - Название [Чтец]/playlist.m3u` |
| `file_count` | `2` |
| `duration` | Реальная из mutagen/ffprobe (≠ из #EXTINF) |
| `is_available` | `1` |
| `author` | `Автор` |
| `title` | `Название` |
| `narrator` | `Чтец` |

**Ожидаемые данные в `audiobook_files`:**
| Поле | Значение |
|------|----------|
| `is_url` | `0` для всех треков |
| `duration` | > 0 (из `_analyze_files_parallel`) |
| `track_number` | 1, 2 (порядок из .m3u) |
| `file_path` | Абсолютный путь к .mp3 |

**SQL-запрос для проверки:**
```sql
SELECT a.path, a.is_playlist, a.playlist_path, a.file_count, a.duration,
       f.track_number, f.file_name, f.duration, f.is_url
FROM audiobooks a
JOIN audiobook_files f ON f.audiobook_id = a.id
WHERE a.is_playlist = 1
ORDER BY a.path, f.track_number;
```

---

### Сценарий B: Папка с несколькими .m3u

**Структура:**
```
Library/
└── Автор - Сборник [Чтец]/
    ├── Книга1.m3u
    ├── Книга2.m3u
    ├── 01.mp3
    └── 02.mp3
```

**Ожидаемые данные в `audiobooks`:**
| Поле | Книга1 | Книга2 |
|------|--------|--------|
| `path` | `Автор - Сборник [Чтец]/Книга1.m3u` | `Автор - Сборник [Чтец]/Книга2.m3u` |
| `parent_path` | `Автор - Сборник [Чтец]` | `Автор - Сборник [Чтец]` |
| `is_playlist` | `1` | `1` |
| `name` | `Книга1` | `Книга2` |

**Отдельная проверка:** Папка-контейнер должна быть в таблице папок (или как `is_folder=1`).

**SQL:**
```sql
SELECT path, parent_path, name, is_playlist
FROM audiobooks
WHERE path LIKE '%Сборник%'
ORDER BY path;
```

---

### Сценарий C: Standalone .m3u в корне (URL-стриминг)

**Структура:**
```
Library/
└── Neoplatonism.m3u   ← содержит http:// ссылки
```

**Содержимое .m3u:**
```
#EXTM3U
#EXTINF:3600,Платон. Государство
https://example.com/platon.mp3
#EXTINF:-1,Аристотель. Метафизика
https://example.com/aristotle.mp3
```

**Ожидаемые данные в `audiobooks`:**
| Поле | Значение |
|------|----------|
| `path` | `Neoplatonism.m3u` |
| `parent_path` | `''` (пустой) |
| `is_playlist` | `1` |
| `playlist_path` | `Neoplatonism.m3u` |

**Ожидаемые данные в `audiobook_files`:**
| Поле | Трек 1 | Трек 2 |
|------|--------|--------|
| `is_url` | `1` | `1` |
| `duration` | `3600.0` (из #EXTINF) | ≥ 0 (из HTTP HEAD или 0) |
| `file_path` | `https://example.com/platon.mp3` | `https://...` |

**SQL:**
```sql
SELECT a.path, a.is_playlist, f.file_path, f.is_url, f.duration
FROM audiobooks a
JOIN audiobook_files f ON f.audiobook_id = a.id
WHERE a.path LIKE '%.m3u'
  AND a.parent_path = '';
```

---

### Сценарий D: Папка без .m3u (старое поведение)

Убедиться что обычные книги **не затронуты**:

```sql
SELECT COUNT(*) FROM audiobooks WHERE is_playlist = 0;
-- Должно быть > 0 и совпадать с кол-вом до добавления M3U

SELECT COUNT(*) FROM audiobooks WHERE is_playlist = 1;
-- Только новые M3U-книги
```

---

### Сценарий E: Кириллика и CP1251

**Тестовый .m3u с CP1251-кодировкой:**
- Создать .m3u файл, сохранённый в кодировке CP1251
- Убедиться что `name`, `title`, `author` в БД — корректный UTF-8

**Проверка:**
```sql
SELECT name, author, title FROM audiobooks WHERE is_playlist = 1;
-- Нет кракозябр типа "ÐÐ²ÑÐ¾Ñ"
```

---

### Сценарий F: Повторное сканирование (state_hash)

1. Сканировать библиотеку → запомнить `state_hash`
2. Сканировать ещё раз без изменений
3. Проверить что `state_hash` не изменился и книга не пересоздана

```sql
-- До и после повторного сканирования:
SELECT id, path, state_hash, time_added FROM audiobooks WHERE is_playlist = 1;
-- id и time_added должны остаться прежними
```

---

### Сценарий G: Длительность локальных файлов (не из #EXTINF)

**Цель:** Убедиться что `_analyze_files_parallel` перезаписывает черновые значения из `#EXTINF`.

**Способ проверки:**  
Создать .m3u с намеренно неверной длительностью в `#EXTINF`:
```
#EXTINF:99,Трек 1
01.mp3
```
(реальная длина 01.mp3 — например 180 секунд)

После сканирования:
```sql
SELECT f.duration FROM audiobook_files f
JOIN audiobooks a ON a.id = f.audiobook_id
WHERE a.is_playlist = 1 AND f.track_number = 1;
-- Должно быть ~180, а НЕ 99
```

---

## 🔬 Шаг 3 — Pytest-тесты (автоматические)

Добавить в `tests/test_m3u_scanner.py`:

### Тест A: `_parse_m3u_file` — локальные файлы

```python
def test_parse_m3u_local_files(mock_scanner, temp_dir):
    """parse_m3u_file корректно извлекает локальные треки"""
    # Создать реальный mp3-заглушку
    mp3 = temp_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 100)  # Минимальный MP3-заголовок
    
    m3u = temp_dir / "playlist.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        f"#EXTINF:99,Трек 1\n"
        f"01.mp3\n",
        encoding="utf-8"
    )
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 1
    assert entries[0]['is_url'] == False
    assert entries[0]['title'] == "Трек 1"
    assert entries[0]['duration'] == 99  # Черновое из #EXTINF
    assert Path(entries[0]['path']).exists()
```

### Тест B: `_parse_m3u_file` — URL-треки

```python
def test_parse_m3u_url_entries(mock_scanner, temp_dir):
    """parse_m3u_file корректно парсит URL-треки"""
    m3u = temp_dir / "stream.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        "#EXTINF:3600,Radio Stream\n"
        "https://example.com/stream.mp3\n"
        "#EXTINF:-1,Live\n"
        "http://example.com/live\n",
        encoding="utf-8"
    )
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 2
    assert all(e['is_url'] for e in entries)
    assert entries[0]['duration'] == 3600
    assert entries[1]['duration'] == 0  # -1 → 0
```

### Тест C: `_parse_m3u_file` — CP1251 кодировка

```python
def test_parse_m3u_cp1251_encoding(mock_scanner, temp_dir):
    """parse_m3u_file читает файлы в CP1251"""
    mp3 = temp_dir / "трек.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 100)
    
    content = "#EXTM3U\n#EXTINF:100,Кириллика\nтрек.mp3\n"
    m3u = temp_dir / "playlist.m3u"
    m3u.write_bytes(content.encode("cp1251"))
    
    entries = mock_scanner._parse_m3u_file(m3u)
    
    assert len(entries) == 1
    assert entries[0]['title'] == "Кириллика"
```

### Тест D: `_save_playlist_as_book` — запись в БД (1 m3u → папка)

```python
def test_save_playlist_as_book_single(mock_scanner, temp_dir):
    """Папка с одним .m3u создаёт запись is_playlist=1 с path=папка"""
    import sqlite3
    
    # Создать структуру
    book_dir = temp_dir / "Автор - Книга [Чтец]"
    book_dir.mkdir()
    mp3 = book_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    m3u = book_dir / "playlist.m3u"
    m3u.write_text(f"#EXTM3U\n#EXTINF:10,Трек\n01.mp3\n", encoding="utf-8")
    
    # In-memory БД с нужной схемой
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_test_schema(conn)  # см. хелпер ниже
    
    mock_scanner._save_playlist_as_book(
        m3u_path=m3u,
        book_path="Автор - Книга [Чтец]",
        parent_path="",
        name="Автор - Книга [Чтец]",
        root=temp_dir,
        conn=conn
    )
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT * FROM audiobooks WHERE is_playlist = 1")
    row = c.fetchone()
    
    assert row is not None
    assert row['path'] == "Автор - Книга [Чтец]"
    assert row['is_playlist'] == 1
    assert row['playlist_path'] == "Автор - Книга [Чтец]/playlist.m3u"
    assert row['file_count'] == 1
    assert row['author'] == "Автор"
    assert row['narrator'] == "Чтец"
    
    c.execute("SELECT * FROM audiobook_files WHERE audiobook_id = ?", (row['id'],))
    files = c.fetchall()
    assert len(files) == 1
    assert files[0]['is_url'] == 0
    assert files[0]['track_number'] == 1
    conn.close()
```

### Тест E: Повторное сканирование не дублирует запись

```python
def test_save_playlist_idempotent(mock_scanner, temp_dir):
    """Повторный вызов _save_playlist_as_book не дублирует запись"""
    import sqlite3
    
    book_dir = temp_dir / "Книга"
    book_dir.mkdir()
    mp3 = book_dir / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    m3u = book_dir / "book.m3u"
    m3u.write_text("#EXTM3U\n01.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    
    kwargs = dict(m3u_path=m3u, book_path="Книга", parent_path="",
                  name="Книга", root=temp_dir, conn=conn)
    
    mock_scanner._save_playlist_as_book(**kwargs)
    conn.commit()
    mock_scanner._save_playlist_as_book(**kwargs)
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_playlist = 1")
    assert c.fetchone()[0] == 1  # Только одна запись
    conn.close()
```

### Тест F: Несколько .m3u → отдельные книги

```python
def test_process_playlist_multiple_m3u(mock_scanner, temp_dir):
    """N .m3u в папке → N отдельных книг в БД"""
    import sqlite3
    
    folder = temp_dir / "Сборник"
    folder.mkdir()
    mp3 = folder / "01.mp3"
    mp3.write_bytes(b"\xFF\xFB" + b"\x00" * 2000)
    
    for name in ["Книга1", "Книга2"]:
        m3u = folder / f"{name}.m3u"
        m3u.write_text("#EXTM3U\n01.mp3\n", encoding="utf-8")
    
    conn = sqlite3.connect(":memory:")
    _create_test_schema(conn)
    
    m3u_files = sorted(folder.glob("*.m3u"))
    mock_scanner._process_playlist_in_folder(
        folder=folder, root=temp_dir,
        m3u_files=m3u_files, conn=conn
    )
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT path, parent_path FROM audiobooks WHERE is_playlist = 1 ORDER BY path")
    rows = c.fetchall()
    
    assert len(rows) == 2
    for row in rows:
        assert row[0].endswith(".m3u")         # path = файл
        assert "Сборник" in row[1]             # parent = папка
    conn.close()
```

### Хелпер `_create_test_schema`

```python
def _create_test_schema(conn):
    """Создать минимальную схему БД для тестов M3U"""
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE audiobooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            parent_path TEXT DEFAULT '',
            name TEXT, author TEXT, title TEXT, narrator TEXT,
            file_count INTEGER DEFAULT 0,
            duration REAL DEFAULT 0,
            is_folder INTEGER DEFAULT 0,
            is_playlist INTEGER DEFAULT 0,
            playlist_path TEXT,
            cover_path TEXT, cached_cover_path TEXT,
            state_hash TEXT,
            listened_duration REAL DEFAULT 0,
            progress_percent REAL DEFAULT 0,
            current_file_index INTEGER DEFAULT 0,
            current_position REAL DEFAULT 0,
            playback_speed REAL DEFAULT 1.0,
            is_started INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            time_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE audiobook_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audiobook_id INTEGER,
            file_path TEXT,
            file_name TEXT,
            track_number INTEGER,
            duration REAL DEFAULT 0,
            start_offset REAL DEFAULT 0,
            tag_title TEXT, tag_artist TEXT, tag_album TEXT,
            tag_genre TEXT, tag_comment TEXT,
            is_url INTEGER DEFAULT 0
        );
        CREATE TABLE audiobook_covers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audiobook_id INTEGER,
            original_path TEXT,
            cached_path TEXT,
            is_selected INTEGER DEFAULT 0,
            source_type TEXT
        );
    """)
    conn.commit()
```

---

## 🖥️ Шаг 4 — Проверка в UI (без воспроизведения)

После сканирования запустить приложение и проверить:

| Проверка | Ожидаемо |
|----------|----------|
| M3U-книга видна в дереве библиотеки | ✅ |
| Отображается правильное число треков | ✅ |
| Отображается длительность (не 0:00) | ✅ |
| Автор и чтец распознаны из имени папки | ✅ |
| Нет дефолтной обложки-баги (либо дефолт, либо найденная) | ✅ |
| Книга не вызывает краш при открытии | ✅ |
| Книга из CP1251-файла отображает корректный текст | ✅ |

> ⚠️ Нажатие «Играть» на M3U-книге — ожидаемая ошибка. Это Часть 2.

---

## 🔴 Шаг 5 — Антипаттерны (что должно НЕ происходить)

```sql
-- ❌ Дубли одной и той же M3U-книги
SELECT path, COUNT(*) cnt FROM audiobooks WHERE is_playlist=1
GROUP BY path HAVING cnt > 1;
-- → Должно быть пусто

-- ❌ M3U-книга с 0 треков
SELECT a.path FROM audiobooks a
LEFT JOIN audiobook_files f ON f.audiobook_id = a.id
WHERE a.is_playlist=1
GROUP BY a.id HAVING COUNT(f.id) = 0;
-- → Должно быть пусто

-- ❌ URL-треки с is_url=0
SELECT f.file_path FROM audiobook_files f
WHERE f.file_path LIKE 'http%' AND f.is_url = 0;
-- → Должно быть пусто

-- ❌ Локальные треки с is_url=1
SELECT f.file_path FROM audiobook_files f
WHERE f.file_path NOT LIKE 'http%' AND f.is_url = 1;
-- → Должно быть пусто

-- ❌ Обычные книги стали is_playlist=1
SELECT COUNT(*) FROM audiobooks WHERE is_playlist=1;
-- → Только нужные M3U-книги, не все подряд

-- ❌ Треки без duration (если есть доступ к файлу)
SELECT f.file_name, f.duration FROM audiobook_files f
JOIN audiobooks a ON a.id = f.audiobook_id
WHERE a.is_playlist=1 AND f.is_url=0 AND f.duration <= 0;
-- → Должно быть пусто (если файлы доступны)
```

---

## 📊 Сводка чеклиста верификации

### Миграции БД
- [ ] Колонка `audiobooks.is_playlist` присутствует
- [ ] Колонка `audiobooks.playlist_path` присутствует
- [ ] Колонка `audiobook_files.is_url` присутствует

### Сканирование — запись в БД
- [ ] **Сценарий A:** Папка с 1 m3u → `path=папка`, `is_playlist=1`
- [ ] **Сценарий B:** Папка с N m3u → N записей с `path=.m3u файл`
- [ ] **Сценарий C:** Standalone .m3u с URL → `is_url=1` у треков
- [ ] **Сценарий D:** Обычные книги не затронуты
- [ ] **Сценарий E:** Кириллика в CP1251 — без кракозябр
- [ ] **Сценарий F:** Повторное сканирование — без дублей
- [ ] **Сценарий G:** Длительность локальных — из mutagen, не из #EXTINF

### Антипаттерны
- [ ] Нет дублей записей
- [ ] Нет M3U-книг с 0 треков
- [ ] `is_url` корректно проставлен для http-путей
- [ ] Обычные книги не получили `is_playlist=1`

### Автотесты (`pytest tests/test_m3u_scanner.py`)
- [ ] Тест A: `_parse_m3u_file` локальные файлы
- [ ] Тест B: `_parse_m3u_file` URL-треки
- [ ] Тест C: `_parse_m3u_file` CP1251
- [ ] Тест D: `_save_playlist_as_book` — запись в БД
- [ ] Тест E: Идемпотентность повторного сканирования
- [ ] Тест F: N .m3u → N книг

### UI (визуальная проверка)
- [ ] Книга видна в библиотеке
- [ ] Число треков и длительность корректны
- [ ] Метаданные (автор, чтец) распознаны
- [ ] Нет краша при открытии
- [ ] Кириллика отображается корректно

---

**Следующий шаг после верификации:** `M3U_PART2_PLAYBACK.md`
