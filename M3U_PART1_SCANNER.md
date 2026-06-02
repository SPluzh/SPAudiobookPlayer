# M3U Playlist Support — Часть 1: Сканирование

**Date:** 2026-05-31 (rev. 4)
**Project:** SP Audiobook Player
**Scope:** Только сканер и БД. Воспроизведение — в `M3U_PART2_PLAYBACK.md`.

> После завершения этой части книги с M3U-плейлистами должны корректно появляться
> в библиотеке с правильным числом треков и длительностью.
> Воспроизведение при этом ещё не работает — это нормально.

---

## 📋 Что делает эта часть

- Парсинг `.m3u` / `.m3u8` файлов
- Запись книг в БД (`is_playlist=1`, `playlist_path`, `is_url`)
- Определение длины локальных файлов через `_analyze_files_parallel()`
- Определение длины URL-треков через HTTP HEAD при сканировании
- Миграции схемы БД
- Обновление `get_audiobook_files()` и `load_audiobooks_from_db()`
- Переводы для строк сканера

---

## 🎯 Логика определения аудиокниг

### Правило: папка с плейлистами

| Ситуация | Результат |
|----------|-----------|
| Папка с **одним** `.m3u` и аудиофайлами | **1 аудиокнига** (папка = книга, треки из плейлиста) |
| Папка с **несколькими** `.m3u` и аудиофайлами | **N аудиокниг** (каждый `.m3u` = отдельная книга) |
| Папка без `.m3u`, только аудиофайлы | Текущее поведение (сортировка по алфавиту) |
| Папка без аудио, только `.m3u` с URL | Каждый `.m3u` = отдельная аудиокнига (стриминг) |
| Одиночный `.m3u` в корне библиотеки | 1 аудиокнига (стриминг или локальные пути) |

### Аналогия с m4b

- Один `.m4b` в папке → папка считается аудиокнигой, главы = треки
- **Один `.m3u` в папке → папка считается аудиокнигой**, записи = треки
- **Несколько `.m3u` → каждый файл = отдельная аудиокнига** (аналог нескольких m4b в папке)

---

## 🗃️ Сценарии

### 1. Папка с одним плейлистом (папка = аудиокнига)
```
Автор - Название книги [Чтец]/
├── playlist.m3u     ← единственный плейлист
├── 01.mp3
└── 02.mp3
```
**path в БД:** `Автор - Название книги [Чтец]` (папка!)
**is_playlist:** 1, файлы = записи из m3u

### 2. Папка с несколькими плейлистами (каждый = аудиокнига)
```
Автор - Сборник [Чтец]/
├── Книга1.m3u
├── Книга2.m3u
└── ... .mp3
```
**path в БД:** `Автор - Сборник [Чтец]/Книга1.m3u`, `Автор - Сборник [Чтец]/Книга2.m3u`
**Родитель:** `Автор - Сборник [Чтец]` — папка-контейнер

### 3. Папка без плейлиста (текущее поведение)
```
Автор - Название [Чтец]/
├── 01.mp3
└── 02.mp3
```
**Без изменений**, сортировка по алфавиту

### 4. Одиночный .m3u в корне (стриминг)
```
Audiobooks/
└── Neoplatonism.m3u    ← URL-стриминг
```
**path в БД:** `Neoplatonism.m3u`, is_playlist=1

---

## 🗄️ 1. Database Migrations (`database.py`)

### Новые колонки

```sql
-- audiobooks table
ALTER TABLE audiobooks ADD COLUMN is_playlist INTEGER DEFAULT 0;
ALTER TABLE audiobooks ADD COLUMN playlist_path TEXT;  -- путь к .m3u файлу

-- audiobook_files table
ALTER TABLE audiobook_files ADD COLUMN is_url INTEGER DEFAULT 0;
```

### Код миграций в `init_database()`

```python
try:
    c.execute("ALTER TABLE audiobooks ADD COLUMN is_playlist INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE audiobooks ADD COLUMN playlist_path TEXT")
except sqlite3.OperationalError:
    pass

try:
    c.execute("ALTER TABLE audiobook_files ADD COLUMN is_url INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass
```

**Оценка изменений:** +20 строк

### Обновить `get_audiobook_files()`

Добавить `is_url` в SELECT:

```python
cursor.execute('''
    SELECT file_path, file_name, duration, track_number, tag_title, start_offset,
           COALESCE(is_url, 0) as is_url
    FROM audiobook_files WHERE audiobook_id = ?
    ORDER BY track_number, start_offset, file_name
''', (audiobook_id,))
```

### Обновить `load_audiobooks_from_db()`

Добавить `is_playlist` в возвращаемый dict (нужно для плеера в Части 2).

**Оценка изменений:** +15 строк

---

## 🔧 2. Scanner Module (`scanner.py`)

### `_find_playlist_files(folder: Path) -> List[Path]`

```python
def _find_playlist_files(self, folder: Path) -> List[Path]:
    """Find all .m3u/.m3u8 files in folder (not recursive)"""
    m3u_files = []
    for ext in ('*.m3u', '*.m3u8'):
        m3u_files.extend(folder.glob(ext))
    return sorted(m3u_files)
```

### `_parse_m3u_file(m3u_path: Path) -> List[Dict]`

```python
def _parse_m3u_file(self, m3u_path: Path) -> List[Dict]:
    """
    Parse M3U/M3U8 playlist.
    Returns: [{'path': str, 'title': str, 'duration': float, 'is_url': bool}, ...]

    NOTE: duration для локальных файлов здесь берётся из #EXTINF как черновое значение.
    Фактическая длина будет определена в _save_playlist_as_book() через _analyze_files_parallel().
    Для URL: duration из #EXTINF, если 0 — HTTP HEAD в _save_playlist_as_book().
    """
    entries = []
    content = None
    for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
        try:
            content = m3u_path.read_text(encoding=encoding)
            break
        except:
            continue
    if not content:
        return []

    lines = content.splitlines()
    current_title = ''
    current_duration = -1

    for line in lines:
        line = line.strip()
        if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
            continue
        if line.startswith('#EXTINF'):
            match = re.match(r'#EXTINF:\s*(-?\d+)\s*,\s*(.*)', line)
            if match:
                current_duration = float(match.group(1))
                current_title = match.group(2).strip()
            continue

        file_path = line
        is_url = file_path.startswith(('http://', 'https://'))

        if is_url:
            entries.append({
                'path': file_path,
                'title': current_title or Path(file_path).name,
                'duration': current_duration if current_duration > 0 else 0,
                'is_url': True
            })
        else:
            if not Path(file_path).is_absolute():
                resolved = (m3u_path.parent / file_path).resolve()
            else:
                resolved = Path(file_path)
            if resolved.exists() and resolved.suffix.lower() in self.audio_extensions:
                entries.append({
                    'path': str(resolved),
                    'title': current_title or resolved.name,
                    # Черновое значение из #EXTINF; будет заменено реальным в _save_playlist_as_book()
                    'duration': current_duration if current_duration > 0 else 0,
                    'is_url': False
                })
        current_title = ''
        current_duration = -1

    return entries
```

### `_get_url_duration_fast(url)` — определение длины сетевых треков

```python
def _get_url_duration_fast(self, url: str) -> float:
    """
    Быстро оценить длительность URL-файла без полной загрузки.
    Использует HTTP HEAD для Content-Length, затем скачивает
    первые 128 KB для разбора заголовка через mutagen.
    Возвращает 0.0 если не удалось.
    """
    import urllib.request
    import io

    try:
        # Шаг 1: HEAD-запрос — получить Content-Length
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'SPAudiobookPlayer/1.0')
        with urllib.request.urlopen(req, timeout=5) as resp:
            content_length = int(resp.headers.get('Content-Length', 0))

        if content_length == 0:
            return 0.0  # Живой поток или сервер не отдаёт размер

        # Шаг 2: Скачать первые 128 KB (заголовок аудиофайла)
        req2 = urllib.request.Request(url)
        req2.add_header('Range', 'bytes=0-131071')
        req2.add_header('User-Agent', 'SPAudiobookPlayer/1.0')
        with urllib.request.urlopen(req2, timeout=10) as resp:
            chunk = resp.read()

        buf = io.BytesIO(chunk)

        # Шаг 3: Разобрать через mutagen
        try:
            from mutagen.mp3 import MP3, BitrateMode
            audio = MP3(buf)
            if audio.info.length > 0:
                # VBR с Xing/VBRI заголовком в первых 128 KB → точная длительность
                return audio.info.length
            elif audio.info.bitrate > 0 and content_length > 0:
                # CBR: оценка через Content-Length / (битрейт в байтах/сек)
                audio_bytes = max(0, content_length - 10240)
                return audio_bytes / (audio.info.bitrate / 8)
        except Exception:
            pass

        try:
            from mutagen.mp4 import MP4
            buf.seek(0)
            audio = MP4(buf)
            if audio.info.length > 0:
                # M4A с moov-атомом в начале файла (fast-start)
                return audio.info.length
        except Exception:
            pass

    except Exception:
        pass

    return 0.0
```

### `_save_playlist_as_book()`

```python
def _save_playlist_as_book(self, m3u_path, book_path, parent_path, name, root, conn):
    """Сохранить плейлист как аудиокнигу в БД"""
    c = conn.cursor()
    entries = self._parse_m3u_file(m3u_path)
    if not entries:
        return

    rel_m3u = str(m3u_path.relative_to(root))

    # Метаданные из имени
    f_author, f_title, f_narrator = self._parse_audiobook_name(name)

    # State hash: mtime + size файла .m3u
    try:
        stat = m3u_path.stat()
        state_str = f"{rel_m3u}|{stat.st_size}|{stat.st_mtime}"
        current_state_hash = hashlib.md5(state_str.encode()).hexdigest()
    except Exception:
        current_state_hash = ''

    # Проверить существующую запись
    c.execute("SELECT id, state_hash FROM audiobooks WHERE path = ?", (book_path,))
    existing = c.fetchone()
    if existing and existing[1] == current_state_hash:
        c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (existing[0],))
        return

    # ── ОПРЕДЕЛИТЬ ДЛИНУ ЛОКАЛЬНЫХ ФАЙЛОВ ──────────────────────────────────────
    # Для локальных файлов длину нельзя брать только из #EXTINF:
    # она может отсутствовать (-1) или быть неточной.
    # Используем _analyze_files_parallel() с кэшем — те же правила, что и для
    # обычных аудиокниг: mutagen (быстро) + ffprobe (резервно).
    local_entries = [(i, e) for i, e in enumerate(entries) if not e['is_url']]
    if local_entries:
        local_paths = [Path(e['path']) for _, e in local_entries]
        analyses = self._analyze_files_parallel(local_paths, conn=conn, max_workers=4)
        for (orig_idx, entry), info in zip(local_entries, analyses):
            if info and info.get('duration', 0) > 0:
                entry['duration'] = info['duration']  # реальная длина перезаписывает #EXTINF
    # ───────────────────────────────────────────────────────────────────────────

    # ── ОПРЕДЕЛИТЬ ДЛИНУ URL-ФАЙЛОВ (ОБЯЗАТЕЛЬНО) ────────────────────────────
    # #EXTINF может отсутствовать или содержать -1.
    # Для каждого URL-трека с duration == 0 вызываем HTTP HEAD.
    # Если #EXTINF уже содержал положительную длительность — HEAD не делается.
    for entry in entries:
        if entry['is_url'] and entry['duration'] == 0:
            entry['duration'] = self._get_url_duration_fast(entry['path'])
    # ─────────────────────────────────────────────────────────────────────────

    total_duration = sum(e['duration'] for e in entries)
    file_count = len(entries)

    # Обложка: ищем в папке .m3u файла (изображение или встроенная).
    # Если обложки нет — _find_cover() возвращает (None, None).
    # library.py уже обрабатывает None: item.setIcon(0, cover_icon or self.default_audiobook_icon)
    # Т.е. при отсутствии обложки книга автоматически получает дефолтную иконку — так же, как все другие книги.
    folder_of_m3u = m3u_path.parent
    cover, cover_cached = self._find_cover(folder_of_m3u, book_path)
    # cover = None, cover_cached = None → дефолтная обложка в библиотеке

    if existing:
        book_id = existing[0]
        c.execute("""
            UPDATE audiobooks
            SET parent_path=?, name=?, author=?, title=?, narrator=?,
                file_count=?, duration=?, is_folder=0,
                is_playlist=1, playlist_path=?,
                cover_path=?, cached_cover_path=?,
                state_hash=?, is_available=1
            WHERE path=?
        """, (parent_path, name, f_author, f_title, f_narrator,
              file_count, total_duration, rel_m3u,
              cover, cover_cached, current_state_hash, book_path))
    else:
        c.execute("""
            INSERT INTO audiobooks
            (path, parent_path, name, author, title, narrator,
             file_count, duration, is_folder, is_playlist, playlist_path,
             cover_path, cached_cover_path, state_hash,
             listened_duration, progress_percent, current_file_index,
             current_position, playback_speed, is_started, is_completed,
             is_available, time_added)
            VALUES (?,?,?,?,?,?,?,?,0,1,?,?,?,?,0,0,0,0,1.0,0,0,1,CURRENT_TIMESTAMP)
        """, (book_path, parent_path, name, f_author, f_title, f_narrator,
              file_count, total_duration, rel_m3u,
              cover, cover_cached, current_state_hash))
        c.execute("SELECT id FROM audiobooks WHERE path = ?", (book_path,))
        book_id = c.fetchone()[0]

    # Удалить старые файлы и вставить новые
    c.execute("DELETE FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
    files_batch = []
    for idx, entry in enumerate(entries, 1):
        files_batch.append((
            book_id,
            entry['path'],
            Path(entry['path']).name,
            idx,
            entry['duration'],
            0.0,
            entry['title'],
            '', '', '', '',
            1 if entry['is_url'] else 0
        ))

    c.executemany("""
        INSERT INTO audiobook_files
        (audiobook_id, file_path, file_name, track_number, duration,
         start_offset, tag_title, tag_artist, tag_album, tag_genre, tag_comment, is_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, files_batch)
```

**Оценка изменений:** +360 строк

### `_process_playlist_in_folder()`

```python
def _process_playlist_in_folder(self, folder, root, m3u_files, conn, verbose=False):
    """
    Обработка плейлистов в папке.

    Если m3u_files содержит 1 файл:
        → папка считается аудиокнигой (is_playlist=1)
        → path = rel путь к ПАПКЕ
        → playlist_path = rel путь к .m3u файлу

    Если m3u_files содержит > 1 файла:
        → каждый .m3u = отдельная аудиокнига
        → path = rel путь к .m3u ФАЙЛУ
        → parent создаётся для папки
    """
    rel_folder = folder.relative_to(root)

    if len(m3u_files) == 1:
        # Папка = одна аудиокнига
        m3u_file = m3u_files[0]
        self._save_playlist_as_book(
            m3u_path=m3u_file,
            book_path=str(rel_folder),       # path = папка
            parent_path=str(rel_folder.parent) if str(rel_folder.parent) != '.' else '',
            name=folder.name,
            root=root,
            conn=conn
        )
    else:
        # Каждый .m3u = отдельная аудиокнига
        for m3u_file in m3u_files:
            rel_m3u = m3u_file.relative_to(root)
            self._save_playlist_as_book(
                m3u_path=m3u_file,
                book_path=str(rel_m3u),       # path = .m3u файл
                parent_path=str(rel_folder),   # parent = папка
                name=m3u_file.stem,
                root=root,
                conn=conn
            )
        # Создать папку-контейнер
        save_folder(str(rel_folder))  # вызов существующей функции
```

### Интеграция в `scan_directory()`

В основном цикле по папкам, перед стандартной обработкой:

```python
for idx, folder in enumerate(folders, 1):
    # ... (получить rel, parent)

    # Найти .m3u файлы в этой папке (не рекурсивно)
    m3u_files = self._find_playlist_files(folder)

    if m3u_files:
        # Обработка плейлистов
        self._process_playlist_in_folder(folder, root, m3u_files, conn, verbose)
        # ВАЖНО: папка с .m3u не создаёт стандартную аудиокнигу
        continue

    # --- стандартная обработка папки (текущий код) ---
```

### Обработка standalone .m3u в корне

```python
# После обработки standalone audio files:
standalone_m3u = []
try:
    for f in root.iterdir():
        if f.is_file() and f.suffix.lower() in ('.m3u', '.m3u8'):
            standalone_m3u.append(f)
except PermissionError:
    pass

for m3u_file in standalone_m3u:
    rel_m3u = m3u_file.relative_to(root)
    self._save_playlist_as_book(
        m3u_path=m3u_file,
        book_path=str(rel_m3u),
        parent_path='',
        name=m3u_file.stem,
        root=root,
        conn=conn
    )
```

---

## 💬 3. Переводы (сканер)

```json
{
  "scanner.scanning_playlists": "Сканирование M3U плейлистов...",
  "scanner.m3u_found":          "Найдено плейлистов: {count}",
  "scanner.m3u_parsing":        "Разбор: {name}",
  "scanner.m3u_files_loaded":   "Загружено треков: {count}"
}
```

**Оценка изменений:** +48 строк (12 языков × 4 ключа)

---

## 📊 Summary — Часть 1

| Файл | Изменения | Строк |
|------|-----------|-------|
| `scanner.py` | `_find_playlist_files()`, `_parse_m3u_file()`, `_get_url_duration_fast()`, `_process_playlist_in_folder()`, `_save_playlist_as_book()` | +360 |
| `database.py` | 3 миграции + `get_audiobook_files()` + `load_audiobooks_from_db()` | +35 |
| `library.py` | Без изменений (M3U книги выглядят как обычные) | 0 |
| `resources/translations/*.json` | 4 ключа × 12 языков | +48 |

**Итого Части 1: ~443 строки**

---

## ✅ Checklist — Часть 1

### БД
- [ ] Добавить миграции `is_playlist`, `playlist_path`, `is_url`
- [ ] Обновить `get_audiobook_files()` — вернуть `is_url`
- [ ] Обновить `load_audiobooks_from_db()` — вернуть `is_playlist`

### Сканер
- [ ] Реализовать `_find_playlist_files()`
- [ ] Реализовать `_parse_m3u_file()` (черновые duration из #EXTINF)
- [ ] Реализовать `_get_url_duration_fast()` — HTTP HEAD при сканировании
- [ ] Реализовать `_save_playlist_as_book()`:
  - [ ] `_analyze_files_parallel()` для локальных файлов (перезаписывает #EXTINF)
  - [ ] `_get_url_duration_fast()` для URL-треков с `duration == 0`
- [ ] Реализовать `_process_playlist_in_folder()` (1 → папка; N → отдельные книги)
- [ ] Интегрировать в `scan_directory()` — до стандартной обработки
- [ ] Обработать standalone `.m3u` в корне библиотеки

### Переводы
- [ ] Добавить 4 ключа сканера во все 12 языков

---

## 🔍 Edge Cases (сканер)

### Папка с m3u И аудиофайлами без m3u
- Если **1 m3u**: папка = аудиокнига, треки **из m3u** (порядок из плейлиста)
- Аудиофайлы вне плейлиста игнорируются при сканировании этой папки
- Соответствует логике m4b: если есть m4b — используем главы из него

### State hash для плейлистов
- Hash = `mtime + size` файла `.m3u`
- При изменении `.m3u` → книга пересканируется
- При добавлении нового `.m3u` → создаётся новая книга

### Прогресс при переходе от 1 к N плейлистам
- Если была 1 книга с `path=папка`, и добавили второй `.m3u`:
  - Старая запись `path=папка` удаляется (при следующем сканировании)
  - Создаются 2 новые записи `path=папка/файл1.m3u`, `path=папка/файл2.m3u`
  - Прогресс будет потерян (неизбежно при смене структуры)

### Определение длины сетевых файлов при сканировании

| Источник | Условие | Скорость | Точность |
|----------|---------|----------|----------|
| `#EXTINF > 0` | Всегда | Мгновенно | Зависит от автора .m3u |
| `_analyze_files_parallel()` | Локальный файл (всегда) | Быстро (кэш) | Отличная |
| `_get_url_duration_fast()` | URL + `duration == 0` | ~500 мс/трек | MP3: хорошая |
| `duration = 0` (fallback) | HEAD не дал результата | — | — |

### Безопасность путей
- Разрешены только `http://` и `https://` протоколы для URL
- `file://`, `ftp://` и прочие — блокировать
- Относительные пути: `resolve()` + проверка что внутри папки библиотеки

---

## 🧪 Тест Части 1 (без воспроизведения)

После реализации Части 1 проверить:

- [ ] Папка с 1 m3u → 1 запись в БД (`is_playlist=1`, `path=папка`)
- [ ] Папка с N m3u → N записей (`path=.m3u файл`)
- [ ] Standalone .m3u с HTTP URL → 1 запись, треки с `is_url=1`
- [ ] Длительность локальных файлов — реальная (не из #EXTINF)
- [ ] Длительность URL-треков — из HTTP HEAD или 0
- [ ] Кириллические пути и CP1251 кодировка
- [ ] Книга появляется в библиотеке (открытие/закрытие без краша)

> ⚠️ Нажатие «Играть» на M3U-книге в этой части скорее всего вызовет ошибку — это ожидаемо. Воспроизведение реализуется в Части 2.

---

**Следующий шаг:** `M3U_PART2_PLAYBACK.md`
