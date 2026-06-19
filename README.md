<img width="1522" height="1151" alt="image" src="https://github.com/user-attachments/assets/a86c41ee-424d-4743-9d34-a8974b59a593" />

# SP Audiobook Player

Offline audiobook player for Windows. It provides library scanning, playback progress tracking, bookmarks, resume playback, and support for multiple audio formats and interface languages.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.6.0+-green.svg)](https://pypi.org/project/PyQt6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![Latest Release](https://img.shields.io/github/v/release/SPluzh/SPAudiobookPlayer)](https://github.com/SPluzh/SPAudiobookPlayer/releases)
[![Latest Release Downloads](https://img.shields.io/github/downloads/SPluzh/SPAudiobookPlayer/latest/total)](https://github.com/SPluzh/SPAudiobookPlayer/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/SPluzh/SPAudiobookPlayer/total)](https://github.com/SPluzh/SPAudiobookPlayer/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**English** | [Русский](#sp-audiobook-player-ru)

---

![](attachments/SP_Audiobook_Player_lpfBcdlMAz.gif)


## Features

### Playback & Audio
- **Multi-format support**: Plays MP3, M4A, M4B, OGG, FLAC, WAV, OPUS, APE, and CUE playlists.
- **Audio Engine**: Powered by BASS library for high-quality audio and independent pitch control (±12 semitones).
- **Speed Control**: Adjust playback speed from 0.5× to 3.0×.
- **Navigation**: Quick track skip, rewind/forward (10s/60s), and Windows taskbar controls.
- **Visualizer**: Real-time spectrum visualization directly on the play button.

### Library Management
- **Smart Scanning**: Automatically indexes directories and groups files into books by folder.
- **Metadata & Tags**: Reads and edits tags (author, narrator, custom tags) and extracts cover art.
- **Search & Filters**: Quick search and filtering by status (Started, Finished, Recently Added, Favorites).
- **Batch Operations**: Edit tags, assign metadata, toggle favorite, or convert to Opus for multiple books at once.
- **Easy Importing**: Supports drag-and-drop file adding and merging multiple folders into a single book.

### Progress & Bookmarks
- **Auto-Save**: Saves playback position per book and restores the last active session on startup.
- **Visual Progress**: Progress bars on cover thumbnails and memory of expanded folders.
- **Bookmarks**: Custom bookmarks with visual indicators on the main progress bar.
- **Smart Auto-Rewind**: Rewinds slightly after a pause to help you regain context.

### Voice & Audio Enhancement
- **Voice Clean-Up**: Built-in De-Esser (reduces sibilance), Noise Suppression, and Dynamic Compressor.
- **Volume Boost**: Amplifies quiet recordings up to 400%.
- **Mono Downmix**: Merges stereo channels into mono for single-earbud listening.

### User Interface
- **Aesthetic Customization**: Fully customizable color palette (accent, background, text, borders) and adjustable icon thickness with real-time live preview.
- **Dual-Pane Layout**: Library browser on the left, player controls and settings on the right.
- **Multilingual**: Fully localized into 16 languages (Arabic, Armenian, Chinese, English, French, German, Hindi, Indonesian, Japanese, Korean, Portuguese, Russian, Spanish, Thai, Turkish, and Vietnamese).

### Keyboard Shortcuts
| Action | Key |
| :--- | :--- |
| **Play / Pause** | `Space` or `Media Play/Pause` |
| **Stop** | `Media Stop` |
| **Previous / Next File** | `[` / `]` |
| **Rewind / Forward 10s** | `Left` / `Right` or `Media Prev` / `Next` |
| **Rewind / Forward 60s** | `Shift` + `Left` / `Right` |
| **Volume +/- 5%** | `Shift` + `Up` / `Down` |
| **Speed +/- 0.1x** | `Up` / `Down` |
| **Scan Library** | `Ctrl` + `R` |
| **Settings** | `Ctrl` + `,` |
| **Listening Statistics** | `Ctrl` + `T` |
| **Reveal Current Audiobook** | `L` |
| **Expand All Folders** | `E` |
| **Collapse All Folders** | `W` |
| **Toggle Minimal Interface** | `P` |
| **Toggle Always on Top** | `T` |

> [!NOTE]
> Multimedia keys (`Play`, `Pause`, `Stop`, `Next`, `Prev`) are **global** and work even when the application is minimized or not in focus.


## Installation

### Option 1: Download Executable (Recommended)
You can download the latest version from the [Releases](../../releases) page in one of the following formats:
- **Installer (Recommended)**: Download and run `SP_Audiobook_Player_Setup_vX.X.X.exe` to install the player.
- **Portable Version**: Download the `.zip` archive (`SP_Audiobook_Player_vX.X.X.zip`), extract it to any desired folder, and run `SP Audiobook Player.exe`.

### Manual Update
If auto-update doesn't work or you prefer to update manually:

1. Download the latest `.zip` from the [Releases](../../releases) page
2. **Close** SP Audiobook Player if it's running
3. Extract the archive **into the existing application folder** with file replacement

> [!IMPORTANT]
> Do **not** delete or overwrite the `data` folder and `settings.ini` file — they contain your library, progress, and settings. Simply extracting the archive on top of the existing installation will safely update all application files while keeping your data intact.


<details>
<summary>Run from Source & Building</summary>

### Prerequisites
- Python 3.8+
- Git

### 1. Clone & Setup
```bash
git clone https://github.com/yourusername/SPAudiobookPlayer.git
cd SPAudiobookPlayer
pip install -r requirements.txt
```

### 2. Run Application
```bash
python main.py
```

### 3. Build Executable (Optional)
To create a standalone EXE using PyInstaller:
```bash
cd _build_
__build.bat
```
The executable will be created in `_build_/dist/`.

> If the automatic download fails, you can download `ffmpeg-release-essentials.zip` from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract `ffmpeg.exe` and `ffprobe.exe`, and place them as follows:
> - **Running from source**: `resources/bin/`
> - **Using the built version**:
>   ```text
>   SP Audiobook Player/
>   ├── SP Audiobook Player.exe
>   └── _internal/resources/bin/
>       ├── ffmpeg.exe
>       └── ffprobe.exe
>   ```
</details>

## Usage

### First Launch
1. On first launch, open **Settings** (Menu → Settings)
2. Specify the path to your audiobook library
3. Click **"Scan library"** to index your audiobooks (missing ffmpeg will be downloaded automatically)
4. (Optional) Install ffprobe via **"Check/Update ffprobe"** for better metadata support

> If the automatic download fails, you can download `ffmpeg-release-essentials.zip` from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract `ffmpeg.exe` and `ffprobe.exe`, and place them as follows:
> ```text
> SP Audiobook Player/
> ├── SP Audiobook Player.exe
> └── _internal/resources/bin/
>     ├── ffmpeg.exe
>     └── ffprobe.exe
> ```

### Playing Audiobooks
- **Double-click** on an audiobook to start playing
- **Right-click** for context menu options (Play, Mark as Read, Open Folder)
- Use the **player controls** on the right panel to control playback
- Your progress is **automatically saved** when you switch books or close the app

### Library Organization
Your audiobooks should be organized in folders, with each audiobook in its own directory. The player **supports any folder hierarchy** - you can organize books by authors, series, or any nested structure:

**Simple structure:**
```
Audiobooks/
├── Author - Book Title [Narrator]/
│   ├── 01 - Chapter 1.mp3
│   ├── 02 - Chapter 2.mp3
│   └── cover.jpg
└── Another Author - Another Book [Narrator]/
    ├── Part 01.m4b
    └── Part 02.m4b
```

**Hierarchical structure (Authors → Series → Books):**
```
Audiobooks/
├── Author Name/
│   ├── Series Name/
│   │   ├── Author - Book Title [Narrator]/
│   │   │   ├── 01 - Chapter 1.mp3
│   │   │   ├── 02 - Chapter 2.mp3
│   │   │   └── cover.jpg
│   │   └── Author - Book 2 Title [Narrator]/
│   │       └── audiobook.m4b
│   └── Standalone Book/
│       └── Part 01.mp3
└── Another Author/
    └── Book Title/
        └── file.mp3
```

The scanner will automatically find all audiobooks regardless of nesting depth.

### Settings
- **Library Path**: Change your audiobook library location.
- **Rescan Library**: Manually trigger a library scan.
- **Tools**:
  - **Opus Converter**: Built-in tool to optimize library size by converting files to Opus format.
  - **FFmpeg/FFprobe**: Check status and download updates.
  - **Reset Data**: Clear all library data and covers (useful for clean rescans).
- **Auto-updater**: Keeps your application up to date with the latest features and fixes.

## Acknowledgments

- **BASS Audio Library**: High-quality audio playback
- **PyQt6**: Modern GUI framework
- **Mutagen**: Audio metadata reading
- **FFmpeg/ffprobe**: Advanced metadata extraction
- **RNNoise**: Intelligent noise suppression
- **BASS_VST**: VST effects support for BASS
- **[Lucide Icons](https://lucide.dev/)**: Clean and consistent icon toolkit
- **[audiobook-opus-converter](https://github.com/kadykov/audiobook-opus-converter)**: Basis for the built-in Opus converter logic

---

<a name="sp-audiobook-player-ru"></a>

# SP Audiobook Player (RU)

[English](#sp-audiobook-player) | **Русский**

---

Оффлайн-плеер аудиокниг для Windows. Поддерживает автоматическое сканирование библиотеки, отслеживание прогресса воспроизведения для каждой книги, закладки, возобновление прослушивания, а также работу с различными аудиоформатами и языками интерфейса.

![](attachments/SP_Audiobook_Player_lpfBcdlMAz.gif)

## Возможности

### Воспроизведение и звук
- **Поддержка форматов**: Воспроизведение MP3, M4A, M4B, OGG, FLAC, WAV, OPUS, APE и плейлистов CUE.
- **Аудиодвижок**: Высокое качество звука на базе BASS и независимое изменение тона (±12 полутонов).
- **Регулировка скорости**: Изменение темпа воспроизведения от 0.5× до 3.0×.
- **Навигация**: Быстрый переход по трекам, шаг 10/60 секунд и управление из панели задач Windows.
- **Визуализатор**: Спектр звука в реальном времени прямо на кнопке воспроизведения.

### Управление библиотекой
- **Умное сканирование**: Автоматический поиск папок и группировка файлов в книги.
- **Метаданные и теги**: Чтение и редактирование тегов (автор, чтец, свои теги), извлечение обложек.
- **Поиск и фильтры**: Быстрый поиск и фильтрация (недавно добавленные, в процессе, прочитанные, избранные).
- **Пакетные операции**: Редактирование тегов, смена статуса или конвертация в Opus для нескольких книг за раз.
- **Простой импорт**: Поддержка Drag & Drop и объединения папок в одну аудиокнигу.

### Прогресс и закладки
- **Автосохранение**: Запоминание позиции для каждой книги и восстановление сессии при запуске.
- **Визуальный прогресс**: Индикаторы прослушивания на обложках и запоминание раскрытых папок.
- **Закладки**: Создание закладок с отметками на шкале воспроизведения.
- **Умная перемотка**: Автоматический откат назад после паузы для восстановления контекста.

### Улучшение голоса и аудио
- **Очистка речи**: Встроенный De-Esser (борьба со свистом), шумоподавление и компрессор динамического диапазона.
- **Усиление звука**: Увеличение громкости тихих записей до 400%.
- **Моно-сведение**: Сведение стереоканалов в моно для удобного прослушивания с одним наушником.

### Интерфейс пользователя
- **Кастомизация оформления**: Полная настройка цветовой палитры (акцент, фон, текст, границы) и толщины линий с мгновенным предпросмотром.
- **Двухпанельный вид**: Дерево библиотеки слева, управление воспроизведением справа.
- **Локализация**: Полная поддержка 16 языков интерфейса (английский, арабский, армянский, вьетнамский, испанский, индонезийский, китайский, корейский, немецкий, португальский, русский, тайский, турецкий, французский, хинди и японский).

### Горячие клавиши
| Действие | Клавиша |
| :--- | :--- |
| **Воспр. / Пауза** | `Пробел` или `Media Play/Pause` |
| **Стоп** | `Media Stop` |
| **Пред. / След. файл** | `[` / `]` |
| **Назад / Вперёд 10с** | `Влево` / `Вправо` или `Media Prev` / `Next` |
| **Назад / Вперёд 60с** | `Shift` + `Влево` / `Вправо` |
| **Громкость +/- 5%** | `Shift` + `Вверх` / `Вниз` |
| **Скорость +/- 0.1x** | `Вверх` / `Вниз` |
| **Сканировать** | `Ctrl` + `R` |
| **Настройки** | `Ctrl` + `,` |
| **Статистика прослушивания** | `Ctrl` + `T` |
| **Показать текущую книгу** | `L` |
| **Раскрыть все папки** | `E` |
| **Свернуть все папки** | `W` |
| **Компактный вид** | `P` |
| **Поверх всех окон** | `T` |

> [!NOTE]
> Мультимедийные клавиши (`Play`, `Pause`, `Stop`, `Next`, `Prev`) являются **глобальными** и работают, даже когда приложение свёрнуто или находится не в фокусе.


## Установка

### Вариант 1: Скачать исполняемый файл (рекомендуется)
На странице [Releases](../../releases) доступны два варианта сборки:
- **Установщик (рекомендуется)**: Скачайте и запустите `SP_Audiobook_Player_Setup_vX.X.X.exe` для полноценной установки плеера в систему.
- **Портативная версия**: Скачайте `.zip` архив (`SP_Audiobook_Player_vX.X.X.zip`), распакуйте его в любую удобную папку и запустите `SP Audiobook Player.exe`.

### Ручное обновление
Если авто-обновление не работает или вы предпочитаете обновлять вручную:

1. Скачайте последний `.zip` со страницы [Releases](../../releases)
2. **Закройте** SP Audiobook Player, если он запущен
3. Распакуйте архив **в существующую папку приложения** с заменой файлов

> [!IMPORTANT]
> **Не** удаляйте и не перезаписывайте папку `data` и файл `settings.ini` — в них хранятся ваша библиотека, прогресс прослушивания и настройки. Простая распаковка архива поверх существующей установки безопасно обновит все файлы приложения, сохранив ваши данные.


<details>
<summary>Запуск из исходников и сборка</summary>

### Предварительные условия
- Python 3.8+
- Git

### 1. Клонирование и настройка
```bash
git clone https://github.com/yourusername/SPAudiobookPlayer.git
cd SPAudiobookPlayer
pip install -r requirements.txt
```

### 2. Запуск приложения
```bash
python main.py
```

### 3. Сборка EXE (опционально)
Для создания автономного исполняемого файла:
```bash
cd _build_
__build.bat
```
Исполняемый файл будет создан в `_build_/dist/`.

> Если автоматическая загрузка не удалась, вы можете скачать `ffmpeg-release-essentials.zip` с сайта [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), извлечь `ffmpeg.exe` и `ffprobe.exe` и разместить их следующим образом:
> - **Запуск из исходников**: `resources/bin/`
> - **Для собранной версии**:
> ```text
> SP Audiobook Player/
> ├── SP Audiobook Player.exe
> └── _internal/resources/bin/
>     ├── ffmpeg.exe
>     └── ffprobe.exe
> ```
</details>

## Использование

### Первый запуск
1. При первом запуске откройте **Настройки** (Меню → Настройки)
2. Укажите путь к вашей библиотеке аудиокниг
3. Нажмите **"Сканировать библиотеку"** для индексации аудиокниг (недостающий ffmpeg будет скачан автоматически)
4. (Опционально) Установите ffprobe через **"Проверить/Обновить ffprobe"** для лучшей поддержки метаданных

> Если автоматическая загрузка не удалась, вы можете скачать `ffmpeg-release-essentials.zip` с сайта [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), извлечь `ffmpeg.exe` и `ffprobe.exe` и разместить их следующим образом:
> ```text
> SP Audiobook Player/
> ├── SP Audiobook Player.exe
> └── _internal/resources/bin/
>     ├── ffmpeg.exe
>     └── ffprobe.exe
> ```

### Воспроизведение аудиокниг
- **Двойной клик** по аудиокниге для начала воспроизведения
- **Правый клик** для контекстного меню (Воспроизвести, Отметить прочитанным, Открыть папку)
- Используйте **элементы управления плеером** на правой панели для управления воспроизведением
- Ваш прогресс **автоматически сохраняется** при переключении книг или закрытии приложения

### Организация библиотеки
```
Audiobooks/
├── Автор - Название книги [Чтец]/
│   ├── 01 - Глава 1.mp3
│   ├── 02 - Глава 2.mp3
│   └── cover.jpg
└── Другой автор - Другая книга [Чтец]/
    ├── Часть 01.m4b
    └── Часть 02.m4b
```

**Иерархическая структура (Авторы → Циклы → Книги):**
```
Audiobooks/
├── Имя автора/
│   ├── Название цикла/
│   │   ├── Автор - Название [Чтец]/
│   │   │   ├── 01 - Глава 1.mp3
│   │   │   ├── 02 - Глава 2.mp3
│   │   │   └── cover.jpg
│   │   └── Автор - Название [Чтец]/
│   │       └── audiobook.m4b
│   └── Отдельная книга/
│       └── Часть 01.mp3
└── Другой автор/
    └── Название книги/
        └── file.mp3
```


Сканер автоматически найдёт все аудиокниги вне зависимости от глубины вложенности.

### Настройки
- **Путь к библиотеке**: Изменение расположения вашей библиотеки аудиокниг.
- **Сканировать библиотеку**: Ручной запуск сканирования.
- **Инструменты**:
  - **Конвертер в Opus**: Встроенный инструмент для оптимизации размера библиотеки путем конвертации файлов в формат Opus.
  - **FFmpeg/FFprobe**: Проверка статуса и обновление.
  - **Сброс данных**: Очистка всей базы данных и обложек (полезно для чистого пересканирования).
- **Авто-обновление**: Встроенный механизм проверки и установки обновлений приложения.

## Благодарности

- **BASS Audio Library**: Высококачественное воспроизведение аудио
- **PyQt6**: Современный фреймворк для GUI
- **Mutagen**: Чтение метаданных аудио
- **FFmpeg/ffprobe**: Расширенное извлечение метаданных
- **RNNoise**: Интеллектуальное шумоподавление
- **BASS_VST**: Поддержка VST-эффектов для BASS
- **[Lucide Icons](https://lucide.dev/)**: Современный набор векторных иконок
- **[audiobook-opus-converter](https://github.com/kadykov/audiobook-opus-converter)**: Основа для логики встроенного конвертера Opus

---

<div align="center">
Made for audiobook lovers
</div>
