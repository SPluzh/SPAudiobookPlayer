# Listening Statistics Feature

## Overview

Система отслеживания статистики прослушивания аудиокниг была добавлена для учета реального времени прослушивания по дням, месяцам и годам.

## Что отслеживается

- **Реальное время прослушивания** - фактическое время, проведенное за прослушиванием (не зависит от скорости воспроизведения)
- **Сессии прослушивания** - каждый период непрерывного прослушивания записывается как отдельная сессия
- **Дневная статистика** - агрегированные данные по дням для каждой книги
- **Месячная и годовая статистика** - автоматически вычисляется из дневных данных

## Структура базы данных

### Таблица `listening_sessions`

Хранит детальную информацию о каждой сессии прослушивания:

```sql
CREATE TABLE listening_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audiobook_id INTEGER NOT NULL,
    session_date DATE NOT NULL,              -- Дата сессии (YYYY-MM-DD)
    session_start TIMESTAMP NOT NULL,        -- Время начала
    session_end TIMESTAMP,                   -- Время окончания (NULL если активна)
    duration_seconds REAL DEFAULT 0,         -- Длительность в секундах
    playback_speed REAL DEFAULT 1.0,         -- Скорость воспроизведения
    is_active INTEGER DEFAULT 1,             -- 1 если сессия активна
    FOREIGN KEY(audiobook_id) REFERENCES audiobooks(id) ON DELETE CASCADE
)
```

### Таблица `daily_listening_stats`

Агрегированная статистика по дням:

```sql
CREATE TABLE daily_listening_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audiobook_id INTEGER NOT NULL,
    listen_date DATE NOT NULL,               -- Дата (YYYY-MM-DD)
    total_seconds REAL DEFAULT 0,            -- Всего секунд за день
    session_count INTEGER DEFAULT 0,         -- Количество сессий
    UNIQUE(audiobook_id, listen_date),
    FOREIGN KEY(audiobook_id) REFERENCES audiobooks(id) ON DELETE CASCADE
)
```

## Как это работает

### 1. Автоматическое отслеживание

Система автоматически отслеживает время прослушивания:

- При загрузке аудиокниги создается новая сессия
- Каждые 100ms таймер обновляет счетчик времени (если воспроизведение активно)
- Каждые 10 секунд накопленное время сохраняется в базу данных
- При паузе/остановке сессия приостанавливается
- При закрытии приложения или переключении книги сессия завершается

### 2. Агрегация данных

- При завершении сессии данные автоматически добавляются в `daily_listening_stats`
- Если в этот день уже были сессии для этой книги, время суммируется
- Месячная и годовая статистика вычисляется динамически из дневных данных

## API для работы со статистикой

### DatabaseManager методы

#### Получить дневную статистику

```python
# Вся статистика
stats = db.get_daily_stats()

# Для конкретной книги
stats = db.get_daily_stats(audiobook_id=5)

# За период
stats = db.get_daily_stats(start_date='2026-04-01', end_date='2026-04-30')

# Результат:
# [
#     {
#         'audiobook_id': 5,
#         'audiobook_name': 'Название книги',
#         'date': '2026-04-30',
#         'total_seconds': 3600.5,
#         'session_count': 3
#     },
#     ...
# ]
```

#### Получить месячную статистику

```python
# За конкретный месяц
stats = db.get_monthly_stats(year=2026, month=4)

# Для конкретной книги
stats = db.get_monthly_stats(audiobook_id=5, year=2026, month=4)

# Результат:
# [
#     {
#         'audiobook_id': 5,
#         'audiobook_name': 'Название книги',
#         'month': '2026-04',
#         'total_seconds': 86400.0,
#         'session_count': 45
#     },
#     ...
# ]
```

#### Получить годовую статистику

```python
# За конкретный год
stats = db.get_yearly_stats(year=2026)

# Для конкретной книги
stats = db.get_yearly_stats(audiobook_id=5, year=2026)

# Результат:
# [
#     {
#         'audiobook_id': 5,
#         'audiobook_name': 'Название книги',
#         'year': '2026',
#         'total_seconds': 1036800.0,
#         'session_count': 520
#     },
#     ...
# ]
```

## Примеры использования

### Пример 1: Получить статистику за сегодня

```python
from datetime import datetime
from database import DatabaseManager

db = DatabaseManager(Path("data/audiobooks.db"))

today = datetime.now().strftime('%Y-%m-%d')
stats = db.get_daily_stats(start_date=today, end_date=today)

for stat in stats:
    hours = stat['total_seconds'] / 3600
    print(f"{stat['audiobook_name']}: {hours:.2f} часов ({stat['session_count']} сессий)")
```

### Пример 2: Топ-5 книг за месяц

```python
from datetime import datetime

db = DatabaseManager(Path("data/audiobooks.db"))

year = datetime.now().year
month = datetime.now().month
stats = db.get_monthly_stats(year=year, month=month)

# Сортировка по времени прослушивания
sorted_stats = sorted(stats, key=lambda x: x['total_seconds'], reverse=True)[:5]

print(f"Топ-5 книг за {year}-{month:02d}:")
for i, stat in enumerate(sorted_stats, 1):
    hours = stat['total_seconds'] / 3600
    print(f"{i}. {stat['audiobook_name']}: {hours:.2f} часов")
```

### Пример 3: Общая статистика за год

```python
db = DatabaseManager(Path("data/audiobooks.db"))

stats = db.get_yearly_stats(year=2026)

total_seconds = sum(s['total_seconds'] for s in stats)
total_books = len(stats)
total_sessions = sum(s['session_count'] for s in stats)

print(f"Статистика за 2026 год:")
print(f"Всего прослушано: {total_seconds / 3600:.2f} часов")
print(f"Книг: {total_books}")
print(f"Сессий: {total_sessions}")
print(f"Среднее время на книгу: {total_seconds / total_books / 3600:.2f} часов")
```

## Важные замечания

1. **Реальное время vs. время контента**: Система отслеживает реальное время прослушивания (wall clock time), а не время контента. Если вы слушаете на скорости 2x, 1 час контента будет записан как 30 минут реального времени.

2. **Автоматическое сохранение**: Данные сохраняются каждые 10 секунд и при закрытии приложения. Если приложение аварийно завершится, может быть потеряно до 10 секунд данных.

3. **Миграция существующих данных**: Существующие данные в поле `listened_duration` не конвертируются в новую систему статистики. Новая система начинает отслеживание с момента обновления.

4. **Производительность**: Индексы созданы для оптимизации запросов по датам и книгам. Запросы должны выполняться быстро даже при большом количестве данных.

## Будущие улучшения

Возможные направления развития:

- [ ] UI для просмотра статистики (графики, таблицы)
- [ ] Экспорт статистики в CSV/JSON
- [ ] Цели прослушивания (например, "1 час в день")
- [ ] Сравнение статистики по периодам
- [ ] Отслеживание времени по жанрам/авторам
- [ ] Уведомления о достижениях

## Тестирование

Запустите тесты для проверки функциональности:

```bash
python tests/test_listening_stats.py
```

Все тесты должны пройти успешно.

## Техническая информация

- **Файл трекера**: `listening_tracker.py`
- **Методы БД**: `database.py` (строки 1398-1690)
- **Интеграция**: `main.py` (строки 98, 166-168, 1560-1563, 1925-1927)
- **Контроллер**: `player.py` (строки 27, 50-52, 110-116, 237-239)
- **Тесты**: `tests/test_listening_stats.py`

---

**Дата создания**: 2026-04-30  
**Версия**: 1.0
