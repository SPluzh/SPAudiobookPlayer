# M3U Playlist Support — Часть 2: Воспроизведение

**Date:** 2026-05-31 (rev. 4)
**Project:** SP Audiobook Player
**Scope:** Только воспроизведение M3U. Сканирование — в `M3U_PART1_SCANNER.md`.

> **Предусловие:** Часть 1 полностью реализована и протестирована.
> БД содержит книги с `is_playlist=1`, треки с `is_url=0/1`.
> `get_audiobook_files()` возвращает поле `is_url`.

---

## 📋 Что делает эта часть

- Открытие URL-треков через `BASS_StreamCreateURL` (вместо `BASS_StreamCreateFile`)
- Настройка буферизации сети в BASS
- Обработка `is_url` в `player.py` при загрузке трека
- Lazy-update длительности URL-трека при первом воспроизведении (через BASS)
- Метод `update_file_duration()` в `DatabaseManager`
- Переводы для строк плеера

---

## 🔧 1. BASS Player (`bass_player.py`)

### Новые константы и конфигурация сети

```python
# Константы для сетевого стриминга
BASS_CONFIG_NET_BUFFER  = 15
BASS_CONFIG_NET_PREBUF  = 21
BASS_CONFIG_NET_TIMEOUT = 11

# В __init__(), после инициализации BASS:
if bass:
    bass.BASS_SetConfig(BASS_CONFIG_NET_BUFFER,  20000)   # 20 сек буфер
    bass.BASS_SetConfig(BASS_CONFIG_NET_PREBUF,  75)      # 75% предзагрузка
    bass.BASS_SetConfig(BASS_CONFIG_NET_TIMEOUT, 10000)   # 10 сек таймаут

    bass.BASS_StreamCreateURL.argtypes = [c_void_p, c_int, c_int, c_void_p, c_void_p]
    bass.BASS_StreamCreateURL.restype  = c_int
```

### Обновить `load(filepath)` — URL vs локальный файл

```python
def load(self, filepath: str) -> bool:
    is_url = filepath.startswith(('http://', 'https://'))
    if is_url:
        url_bytes = filepath.encode('utf-8') + b'\x00'
        flags = BASS_STREAM_DECODE | BASS_SAMPLE_FLOAT
        self.chan0 = bass.BASS_StreamCreateURL(url_bytes, 0, flags, None, None)
        self.is_streaming = True
    else:
        # текущий код для локальных файлов (без изменений)
        ...
```

**Оценка изменений:** +60 строк

---

## 🔧 2. Player Module (`player.py`)

### Обновить `load_file_by_index()`

```python
def load_file_by_index(self, index: int) -> bool:
    file_info = self.files_list[index]
    file_path = file_info['path']
    is_url = file_info.get('is_url', False)

    if is_url:
        full_path = file_path          # URL — использовать как есть
    else:
        # Локальный файл (текущая логика без изменений)
        if not Path(file_path).is_absolute() and self.library_root:
            full_path = str(self.library_root / file_path)
        else:
            full_path = file_path

    if not self.player.load(full_path):
        return False

    # Lazy-update длительности URL-трека (резервный путь)
    # Срабатывает только если HTTP HEAD при сканировании не дал результата
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

**Оценка изменений:** +20 строк

---

## 🔧 3. Database Manager — `update_file_duration()`

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

**Оценка изменений:** +25 строк

---

## 💬 4. Переводы (плеер)

```json
{
  "player.buffering":      "Буферизация...",
  "player.network_error":  "Ошибка сети"
}
```

**Оценка изменений:** +24 строки (12 языков × 2 ключа)

---

## 📊 Summary — Часть 2

| Файл | Изменения | Строк |
|------|-----------|-------|
| `bass_player.py` | `BASS_StreamCreateURL`, сетевая конфигурация, URL-ветка в `load()` | +60 |
| `player.py` | `is_url` в `load_file_by_index()`, lazy-update длительности | +20 |
| `database.py` | `update_file_duration()` | +25 |
| `resources/translations/*.json` | 2 ключа × 12 языков | +24 |

**Итого Части 2: ~129 строк**

---

## ✅ Checklist — Часть 2

### BASS Player
- [x] Добавить константы `BASS_CONFIG_NET_BUFFER`, `BASS_CONFIG_NET_PREBUF`, `BASS_CONFIG_NET_TIMEOUT`
- [x] Настроить буферизацию в `__init__()`
- [x] Объявить `BASS_StreamCreateURL` (argtypes, restype)
- [x] Добавить URL-ветку в `load()` — `BASS_StreamCreateURL` вместо `BASS_StreamCreateFile`
- [x] Добавить флаг `self.is_streaming` для отслеживания состояния

### Player
- [x] Обновить `load_file_by_index()` — обработка `is_url`
- [x] Добавить lazy-update длительности при первом воспроизведении URL-трека

### Database
- [x] Реализовать `update_file_duration()` в `DatabaseManager`

### Переводы
- [x] Добавить 2 ключа плеера во все 12 языков

---

## 🌐 Параметры сетевого стриминга

| Параметр | Значение | Описание |
|----------|----------|----------|
| `BASS_CONFIG_NET_BUFFER` | 20000 мс | Размер буфера (20 сек) |
| `BASS_CONFIG_NET_PREBUF` | 75% | Предзагрузка перед стартом |
| `BASS_CONFIG_NET_TIMEOUT` | 10000 мс | Таймаут подключения |

| Функция | Локальный | Сетевой |
|---------|-----------|---------|
| Воспроизведение | ✅ Мгновенно | ✅ После буферизации |
| Пауза/Продолжение | ✅ | ✅ |
| Перемотка | ✅ | ⚠️ Если сервер поддерживает Range |
| Скорость | ✅ | ✅ |
| Длительность | ✅ | ⚠️ Гибридный метод (HTTP HEAD + lazy-BASS) |
| Прогресс в БД | ✅ | ✅ |

---

## 🕐 Источники длительности (итого)

| Шаг | Когда | Метод | Тип |
|-----|-------|-------|-----|
| 1 | Сканирование | `#EXTINF > 0` | Локальный + URL |
| 2 | Сканирование | `_analyze_files_parallel()` | Только локальные |
| 3 | Сканирование | `_get_url_duration_fast()` (HTTP HEAD) | Только URL, если duration==0 |
| 4 | Первое воспроизведение | BASS lazy-update | Только URL, если duration==0 после сканирования |

---

## 🔒 Безопасность (URL)

- Разрешены только `http://` и `https://`
- `file://`, `ftp://` и прочие — блокировать в `load()`
- BASS обрабатывает таймауты и повторы внутренне

---

## 🧪 Тест Части 2

- [x] Локальный плейлист воспроизводится корректно (треки переключаются по порядку)
- [x] URL-плейлист открывается и буферизуется
- [x] Прогресс URL-трека сохраняется в БД
- [x] При недоступном URL — ошибка в статусбаре, переход к следующему треку
- [x] Перемотка URL-трека (если сервер поддерживает Range)
- [x] Смешанный плейлист (локальные + URL чередуются)
- [x] Lazy-update длительности срабатывает и обновляет БД
