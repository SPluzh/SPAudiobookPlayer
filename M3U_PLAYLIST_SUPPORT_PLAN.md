# M3U Playlist Support Implementation Plan

**Date:** 2026-05-31 (rev. 2)
**Project:** SP Audiobook Player
**Feature:** M3U/M3U8 Playlist Support with Network Streaming

---

## 📋 Overview

Add support for M3U/M3U8 playlists to enable:
- **Local playlists** to define custom playback order
- **Network streaming** from HTTP/HTTPS URLs (e.g., Archive.org)
- **Mixed playlists** with both local and network files

---

## 🎯 Логика определения аудиокниг (обновлено)

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

## 🗄️ Database Schema Changes

### Новые колонки

```sql
-- audiobooks table
ALTER TABLE audiobooks ADD COLUMN is_playlist INTEGER DEFAULT 0;
ALTER TABLE audiobooks ADD COLUMN playlist_path TEXT;  -- путь к .m3u файлу

-- audiobook_files table  
ALTER TABLE audiobook_files ADD COLUMN is_url INTEGER DEFAULT 0;
```

### Модель данных

**Один плейлист в папке:**
```
audiobooks:
  path = 'Автор - Книга [Чтец]'   ← путь ПАПКИ
  is_folder = 0
  is_playlist = 1
  playlist_path = 'Автор - Книга [Чтец]/playlist.m3u'
```

**Несколько плейлистов в папке:**
```
audiobooks:
  path = 'Автор - Сборник/Книга1.m3u'  ← путь ФАЙЛА
  is_folder = 0
  is_playlist = 1
  playlist_path = 'Автор - Сборник/Книга1.m3u'
  parent_path = 'Автор - Сборник'
```

---

## 🔧 Implementation Details

### 1. Scanner Module (`scanner.py`)

#### `_find_playlist_files(folder: Path) -> List[Path]`
```python
def _find_playlist_files(self, folder: Path) -> List[Path]:
    """Find all .m3u/.m3u8 files in folder (not recursive)"""
    m3u_files = []
    for ext in ('*.m3u', '*.m3u8'):
        m3u_files.extend(folder.glob(ext))
    return sorted(m3u_files)
```

#### `_parse_m3u_file(m3u_path: Path) -> List[Dict]`
```python
def _parse_m3u_file(self, m3u_path: Path) -> List[Dict]:
    """
    Parse M3U/M3U8 playlist.
    Returns: [{'path': str, 'title': str, 'duration': float, 'is_url': bool}, ...]
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
                    'duration': current_duration if current_duration > 0 else 0,
                    'is_url': False
                })
        current_title = ''
        current_duration = -1

    return entries
```

#### Модифицированная логика сканирования

```python
# В scan_directory(), после основного цикла папок,
# добавить обработку плейлистов:

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

#### Интеграция в `scan_directory()`

В основном цикле по папкам, перед стандартной обработкой:

```python
for idx, folder in enumerate(folders, 1):
    # ... (получить rel, parent)
    
    # Найти .m3u файлы в этой папке (не рекурсивно)
    m3u_files = self._find_playlist_files(folder)
    
    if m3u_files:
        # Обработка плейлистов
        self._process_playlist_in_folder(folder, root, m3u_files, conn, verbose)
        # ВАЖНО: всё равно продолжаем, чтобы создать структуру папок
        # Но НЕ создаём стандартную аудиокнигу для этой папки
        continue
    
    # --- стандартная обработка папки (текущий код) ---
```

**Важная деталь:** папки, где ЕСТЬ аудиофайлы И m3u, не должны создавать «обычную» аудиокнигу — только playlist-based.

#### Обработка standalone .m3u в корне

В секции standalone files (после основного цикла):

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

#### `_save_playlist_as_book()`

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

    # State hash: содержимое .m3u + mtime
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

    total_duration = sum(e['duration'] for e in entries)
    file_count = len(entries)

    # Обложка (из папки .m3u файла)
    folder_of_m3u = m3u_path.parent
    cover, cover_cached = self._find_cover(folder_of_m3u, book_path)

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

**Оценка изменений:** +350 строк

---

### 2. Database Module (`database.py`)

```python
# Миграции в init_database():

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

---

### 3. BASS Player (`bass_player.py`)

```python
# Константы для сетевого стриминга
BASS_CONFIG_NET_BUFFER  = 15
BASS_CONFIG_NET_PREBUF  = 21
BASS_CONFIG_NET_TIMEOUT = 11

# В __init__():
if bass:
    bass.BASS_SetConfig(BASS_CONFIG_NET_BUFFER,  20000)
    bass.BASS_SetConfig(BASS_CONFIG_NET_PREBUF,  75)
    bass.BASS_SetConfig(BASS_CONFIG_NET_TIMEOUT, 10000)

    bass.BASS_StreamCreateURL.argtypes = [c_void_p, c_int, c_int, c_void_p, c_void_p]
    bass.BASS_StreamCreateURL.restype  = c_int

# В load():
def load(self, filepath: str) -> bool:
    is_url = filepath.startswith(('http://', 'https://'))
    if is_url:
        url_bytes = filepath.encode('utf-8') + b'\x00'
        flags = BASS_STREAM_DECODE | BASS_SAMPLE_FLOAT
        self.chan0 = bass.BASS_StreamCreateURL(url_bytes, 0, flags, None, None)
        self.is_streaming = True
    else:
        # текущий код для локальных файлов
        ...
```

**Оценка изменений:** +60 строк

---

### 4. Player Module (`player.py`)

```python
def load_file_by_index(self, index: int) -> bool:
    file_info = self.files_list[index]
    file_path = file_info['path']
    is_url = file_info.get('is_url', False)

    if is_url:
        full_path = file_path          # URL — использовать как есть
    else:
        # Локальный файл (текущая логика)
        if not Path(file_path).is_absolute() and self.library_root:
            full_path = str(self.library_root / file_path)
        else:
            full_path = file_path

    if not self.player.load(full_path):
        return False
    # ... остальной код без изменений
```

**Оценка изменений:** +15 строк

---

### 5. Library Module (`library.py`)

- Загрузить иконку плейлиста `playlist_icon`
- В `_create_item_from_data()`: если `data.get("is_playlist")` → использовать `playlist_icon` вместо дефолтной иконки

**Оценка изменений:** +30 строк

---

### 6. Database Manager (`database.py` — `get_audiobook_files`)

Добавить `is_url` в SELECT:

```python
cursor.execute('''
    SELECT file_path, file_name, duration, track_number, tag_title, start_offset,
           COALESCE(is_url, 0) as is_url
    FROM audiobook_files WHERE audiobook_id = ?
    ORDER BY track_number, start_offset, file_name
''', (audiobook_id,))
```

И обновить `load_audiobooks_from_db` — добавить `is_playlist` в возвращаемый dict.

**Оценка изменений:** +15 строк

---

### 7. Переводы (`resources/translations/*.json`)

```json
{
  "scanner.scanning_playlists":    "Сканирование M3U плейлистов...",
  "scanner.m3u_found":             "Найдено плейлистов: {count}",
  "scanner.m3u_parsing":           "Разбор: {name}",
  "scanner.m3u_files_loaded":      "Загружено треков: {count}",
  "library.playlist_indicator":    "Плейлист",
  "library.streaming_indicator":   "Стриминг",
  "player.buffering":              "Буферизация...",
  "player.network_error":          "Ошибка сети"
}
```

**Оценка изменений:** +96 строк (12 языков × 8 ключей)

---

## 📊 Summary of Changes

| Файл | Изменения | Строк |
|------|-----------|-------|
| `scanner.py` | `_find_playlist_files()`, `_parse_m3u_file()`, `_process_playlist_in_folder()`, `_save_playlist_as_book()` | +350 |
| `database.py` | 3 миграции + обновление SELECT | +35 |
| `bass_player.py` | `BASS_StreamCreateURL`, сетевая конфигурация | +60 |
| `player.py` | Обработка `is_url` | +15 |
| `library.py` | Иконка плейлиста | +30 |
| `resources/translations/*.json` | 8 ключей × 12 языков | +96 |

**Итого: ~586 строк**

---

## ✅ Implementation Checklist

### Phase 1: База данных
- [ ] Добавить миграции `is_playlist`, `playlist_path`, `is_url`
- [ ] Обновить `get_audiobook_files()` — вернуть `is_url`
- [ ] Обновить `load_audiobooks_from_db()` — вернуть `is_playlist`

### Phase 2: Сканер
- [ ] Реализовать `_find_playlist_files()`
- [ ] Реализовать `_parse_m3u_file()`
- [ ] Реализовать `_save_playlist_as_book()`
- [ ] Реализовать `_process_playlist_in_folder()` (1 плейлист → папка; N плейлистов → отдельные книги)
- [ ] Интегрировать в `scan_directory()` — до стандартной обработки папки
- [ ] Обработать standalone `.m3u` в корне библиотеки

### Phase 3: Воспроизведение
- [ ] Добавить `BASS_StreamCreateURL` в `bass_player.py`
- [ ] Настроить буферизацию сети
- [ ] Обновить `load()` — URL vs локальный файл
- [ ] Обновить `load_file_by_index()` в `player.py`

### Phase 4: UI
- [ ] Загрузить `playlist_icon` в `library.py`
- [ ] Применять иконку для `is_playlist=1` книг
- [ ] Добавить переводы во все 12 языков

### Phase 5: Тестирование
- [ ] Папка с 1 m3u → 1 аудиокнига (path = папка)
- [ ] Папка с N m3u → N аудиокниг (path = .m3u файл)
- [ ] Standalone .m3u с HTTP URL — стриминг
- [ ] Смешанный плейлист (локальные + URL)
- [ ] Кириллические пути и CP1251 кодировка
- [ ] Прогресс сохраняется и восстанавливается

---

## 🔍 Edge Cases & Nuances

### Папка с m3u И аудиофайлами без m3u
- Если в папке **1 m3u**: папка = аудиокнига, треки **из m3u** (порядок из плейлиста)
- Аудиофайлы вне плейлиста игнорируются при сканировании этой папки
- Это соответствует логике m4b: если есть m4b — используем главы из него

### Приоритет при обнаружении m3u
- `_find_playlist_files()` возвращает все `.m3u`/`.m3u8` в папке
- Приоритет имён при выборе "главного" не нужен — количество определяет поведение

### State hash для плейлистов
- Hash = `mtime + size` файла `.m3u`
- При изменении `.m3u` → книга пересканируется
- При добавлении нового `.m3u` → создаётся новая книга

### Прогресс при переходе от 1 к N плейлистам
- Если была 1 книга с `path=папка`, и добавили второй `.m3u`:
  - Старая запись `path=папка` удаляется (при следующем сканировании)
  - Создаются 2 новые записи `path=папка/файл1.m3u`, `path=папка/файл2.m3u`
  - Прогресс для первой книги будет потерян (неизбежно при смене структуры)

### URL-только плейлисты (нет локальных файлов)
- `_parse_m3u_file()` принимает URL-записи
- `_analyze_file()` не вызывается (нет локальных файлов для анализа)
- `duration` берётся из `#EXTINF`, если `-1` → остаётся `0`
- Длительность неизвестна до первого воспроизведения

---

## 🌐 Network Streaming

| Параметр | Значение |
|----------|----------|
| `BASS_CONFIG_NET_BUFFER` | 20000 мс (20 сек) |
| `BASS_CONFIG_NET_PREBUF` | 75% |
| `BASS_CONFIG_NET_TIMEOUT` | 10000 мс |

| Функция | Локальный | Сетевой |
|---------|-----------|---------|
| Воспроизведение | ✅ Мгновенно | ✅ После буферизации |
| Пауза/Продолжение | ✅ | ✅ |
| Перемотка | ✅ | ⚠️ Если сервер поддерживает Range |
| Скорость | ✅ | ✅ |
| Длительность | ✅ | ⚠️ Гибридный метод (см. ниже) |
| Прогресс в БД | ✅ | ✅ |

---

## 🔒 Security

- Разрешены только `http://` и `https://` протоколы
- `file://`, `ftp://` и прочие — блокировать
- Относительные пути: resolve() + проверка что внутри папки библиотеки
- BASS handles timeouts and retries internally

---

## 🕐 Гибридное получение длительности URL-треков

### Проблема

Для локальных файлов длительность получается через `mutagen` при сканировании. Для URL-треков `#EXTINF` может содержать `-1` (неизвестно) или вовсе отсутствовать.

### Стратегия (3 уровня)

```
При сканировании .m3u:
  1. #EXTINF > 0           → использовать, больше ничего не делать
  2. #EXTINF == -1 или 0   → попробовать HTTP HEAD (быстро, ~мс, без загрузки)
  3. HEAD не дал результат → сохранить duration=0

При первом воспроизведении URL-трека:
  → BASS открыл поток → BASS_ChannelGetLength → обновить duration в БД
```

### Реализация: `_get_url_duration_fast(url)` в `scanner.py`

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
            content_type = resp.headers.get('Content-Type', '')

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
                # Вычесть ~10 KB на ID3-теги
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

### Применение в `_parse_m3u_file()`

```python
def _parse_m3u_file(self, m3u_path: Path, fetch_url_durations: bool = False) -> List[Dict]:
    # ... (парсинг как раньше) ...
    
    for entry in entries:
        if entry['is_url'] and entry['duration'] == 0 and fetch_url_durations:
            entry['duration'] = self._get_url_duration_fast(entry['path'])
    
    return entries
```

> По умолчанию `fetch_url_durations=False` — сканирование не делает сетевых запросов.  
> Можно включить опционально (например, кнопка «Обновить длительности» в UI).

### Lazy-update при воспроизведении в `player.py`

```python
def load_file_by_index(self, index: int) -> bool:
    file_info = self.files_list[index]
    is_url = file_info.get('is_url', False)
    full_path = file_info['path'] if is_url else self._resolve_local_path(file_info['path'])

    if not self.player.load(full_path):
        return False

    # Если длительность URL-трека была неизвестна — обновить из BASS
    if is_url and file_info.get('duration', 0) == 0:
        actual_dur = self.player.get_duration()  # BASS_ChannelGetLength → Bytes2Seconds
        if actual_dur > 0:
            file_info['duration'] = actual_dur
            # Обновить в БД асинхронно (не блокировать воспроизведение)
            if self.db and self.current_book_id:
                self.db.update_file_duration(
                    audiobook_id=self.current_book_id,
                    file_path=file_info['path'],
                    duration=actual_dur
                )
    
    # ... остальной код без изменений
```

### Новый метод в `DatabaseManager`

```python
def update_file_duration(self, audiobook_id: int, file_path: str, duration: float):
    """Обновить длительность конкретного файла в audiobook_files"""
    conn = sqlite3.connect(self.db_file)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE audiobook_files
            SET duration = ?
            WHERE audiobook_id = ? AND file_path = ? AND duration = 0
        """, (duration, audiobook_id, file_path))
        
        # Пересчитать суммарную длительность книги
        cursor.execute("""
            UPDATE audiobooks
            SET duration = (
                SELECT COALESCE(SUM(duration), 0)
                FROM audiobook_files
                WHERE audiobook_id = ?
            )
            WHERE id = ?
        """, (audiobook_id, audiobook_id))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating file duration: {e}")
    finally:
        conn.close()
```

### Итоговая таблица источников длительности

| Источник | Когда | Скорость | Точность | Требует сеть |
|----------|-------|----------|----------|--------------|
| `#EXTINF` | Сканирование | Мгновенно | Зависит от автора | Нет |
| HTTP HEAD + 128 KB | Сканирование (опц.) | ~500 мс/трек | MP3: хорошая; M4A fast-start: хорошая | Да |
| BASS lazy-update | Первое воспроизведение | ~1-3 сек | Отличная (все форматы) | Да |

### Изменения в чеклисте

- [ ] Реализовать `_get_url_duration_fast()` в `scanner.py`
- [ ] Добавить параметр `fetch_url_durations` в `_parse_m3u_file()`
- [ ] Реализовать lazy-update длительности в `player.py`
- [ ] Добавить `update_file_duration()` в `DatabaseManager`

**Дополнительные строки:** +80

---

**End of Implementation Plan (rev. 3)**
