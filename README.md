# 🎧 SP Audiobook Player

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.6.0+-green.svg)](https://pypi.org/project/PyQt6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![Latest Release](https://img.shields.io/github/v/release/SPluzh/SPAudiobookPlayer)](https://github.com/SPluzh/SPAudiobookPlayer/releases)
[![Downloads](https://img.shields.io/github/downloads/SPluzh/SPAudiobookPlayer/total)](https://github.com/SPluzh/SPAudiobookPlayer/releases)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English** | [Русский](#-sp-audiobook-player-ru)

---

## 📖 About

**SP Audiobook Player** is a modern and elegant audiobook player for Windows designed for a seamless listening experience. Built with PyQt6 and BASS audio library, it offers automatic library scanning, smart progress tracking per book, and a refined user interface that handles various audio formats and tag encodings effortlessly.

Perfect for audiobook enthusiasts who want a dedicated, feature-rich player with an intuitive interface and robust functionality.

![](attachments/SP_Audiobook_Player_lpfBcdlMAz.gif)


## ✨ Features

### 🎵 Playback
- **Multi-format support**: MP3, M4A, M4B, OGG, FLAC, WAV, WMA, AAC, OPUS
- **High-quality audio**: Powered by BASS audio library
- **Playback speed control**: Adjust from 0.5× to 3.0×
- **Quick navigation**: Skip tracks, rewind/forward 10 or 60 seconds
- **Windows taskbar integration**: Playback controls directly from the taskbar
- **Visualizer**: Real-time audio spectrum visualization on the play button

### 📚 Library Management
- **Automatic scanning**: Recursively scans directories for audiobooks
- **Smart organization**: Automatically groups files into audiobooks by folder
- **Tag support**: Reads author, title, narrator from ID3 tags (MP3) and other metadata
- **Cover art extraction**: Automatically extracts and displays embedded album art
- **Search functionality**: Find audiobooks by title, author, or narrator
- **Library filters**: Quick access to recently added, started, and finished books
- **Favorites**: Mark books for quick access
- **Metadata Editor**: Edit book info directly in the app
- **Tag System**: Organize library with custom tags
- **Folder Merging**: Merge multiple folders into a single audiobook
- **Drag & Drop**: Easily add books by dragging them into the library

### 📊 Progress Tracking
- **Per-book progress**: Automatically saves playback position for each audiobook
- **Visual indicators**: Progress bars on cover thumbnails
- **Status filtering**: Filter by status (Not Started, In Progress, Completed)
- **Session restoration**: Resumes the last played audiobook on startup
- **Bookmarks**: Create and manage bookmarks with visual markers on the progress bar
- **Folder expansion state**: Remembers which folders were expanded in the library

### 🎨 User Interface
- **Modern dark theme**: Elegant and eye-friendly interface
- **Dual-pane layout**: Library browser on the left, player controls on the right
- **Context menus**: Right-click for quick actions (Play, Mark as Read, Open Folder)
- **Multilingual support**: Full interface localization (12 languages: AR, DE, EN, ES, FR, HI, JA, KO, PT, RU, TR, ZH)


### 🎛️ Smart Audio Processing
- **Smart Auto-Rewind**: Automatically rewinds after a pause to help you regain context (starts at 5s, adds 2s per minute of pause, up to 30s max).
- **Voice Enhancement**: 
  - **De-Esser**: Reduces harsh sibilance (s/sh sounds) with Light/Medium/Strong presets.
  - **Compressor**: Balances dynamic range for consistent volume levels.
  - **Noise Suppression**: Removes background noise for clearer speech.
- **Pitch Control**: Adjust playback pitch without changing speed (+/- 12 semitones).

### ⌨️ Keyboard Shortcuts
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

> [!NOTE]
> Multimedia keys (`Play`, `Pause`, `Stop`, `Next`, `Prev`) are **global** and work even when the application is minimized or not in focus.


## 🚀 Installation

### Requirements
- Windows 10/11 (64-bit)
- Python 3.8+ (for source installation)

### Option 1: Download Executable (Recommended)
1. Download the latest release from the [Releases](../../releases) page
2. Extract the archive to your desired location
3. Run `SP Audiobook Player.exe`


<details>
<summary>💻 Run from Source & Building</summary>

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

> [!TIP]
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

## 📘 Usage

### First Launch
1. On first launch, open **Settings** (Menu → Settings)
2. Specify the path to your audiobook library
3. Click **"Scan library"** to index your audiobooks (missing ffmpeg will be downloaded automatically)
4. (Optional) Install ffprobe via **"Check/Update ffprobe"** for better metadata support

[!NOTE]
If the automatic download fails, you can download `ffmpeg-release-essentials.zip` from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract `ffmpeg.exe` and `ffprobe.exe`, and place them as follows:
```text
SP Audiobook Player/
├── SP Audiobook Player.exe
└── _internal/resources/bin/
    ├── ffmpeg.exe
    └── ffprobe.exe
```

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

### ⚙️ Settings
- **Library Path**: Change your audiobook library location.
- **Rescan Library**: Manually trigger a library scan.
- **Tools**:
  - **Opus Converter**: Built-in tool to optimize library size by converting files to Opus format.
  - **FFmpeg/FFprobe**: Check status and download updates.
  - **Reset Data**: Clear all library data and covers (useful for clean rescans).
- **Auto-updater**: Keeps your application up to date with the latest features and fixes.





## 🙏 Acknowledgments

- **BASS Audio Library**: High-quality audio playback
- **PyQt6**: Modern GUI framework
- **Mutagen**: Audio metadata reading
- **FFmpeg/ffprobe**: Advanced metadata extraction
- **RNNoise**: Intelligent noise suppression
- **BASS_VST**: VST effects support for BASS

---

<a name="-sp-audiobook-player-ru"></a>

# 🎧 SP Audiobook Player (RU)

[English](#-sp-audiobook-player) | **Русский**

---

## 📖 О программе

**SP Audiobook Player** — это современный и элегантный плеер аудиокниг для Windows, созданный для комфортного прослушивания. Построенный на базе PyQt6 и аудиобиблиотеки BASS, он предлагает автоматическое сканирование библиотеки, умное сохранение прогресса для каждой книги и продуманный интерфейс, который корректно работает с различными аудиоформатами и кодировками тегов.

Идеальное решение для любителей аудиокниг, которым нужен функциональный плеер с интуитивным интерфейсом и широкими возможностями.

![](attachments/SP_Audiobook_Player_lpfBcdlMAz.gif)

## ✨ Возможности

### 🎵 Воспроизведение
- **Поддержка форматов**: MP3, M4A, M4B, OGG, FLAC, WAV, WMA, AAC, OPUS
- **Высокое качество звука**: На базе аудиобиблиотеки BASS
- **Управление скоростью**: Регулировка от 0,5× до 3,0×
- **Быстрая навигация**: Переключение треков, перемотка на 10 или 60 секунд
- **Интеграция с Windows**: Кнопки управления прямо на панели задач
- **Визуализатор**: Визуализация спектра аудио в реальном времени на кнопке воспроизведения

### 📚 Управление библиотекой
- **Автоматическое сканирование**: Рекурсивный поиск аудиокниг в папках
- **Умная организация**: Автоматическая группировка файлов в аудиокниги по папкам
- **Поддержка тегов**: Чтение автора, названия, чтеца из ID3-тегов и других метаданных
- **Исправление кодировки**: Работа с различными кодировками тегов, включая кириллицу
- **Извлечение обложек**: Автоматическое извлечение и отображение встроенных обложек
- **Функция поиска**: Поиск аудиокниг по названию, автору или чтецу
- **Фильтры библиотеки**: Быстрый доступ к недавно добавленным, начатым и завершённым книгам
- **Избранное**: Возможность отмечать книги для быстрого доступа
- **Редактор метаданных**: Редактирование информации о книгах прямо в приложении
- **Система тегов**: Организация библиотеки с помощью пользовательских тегов
- **Объединение папок**: Возможность объединять несколько папок в одну аудиокнигу
- **Drag & Drop**: Добавление книг простым перетаскиванием в окно плеера

### 📊 Отслеживание прогресса
- **Прогресс для каждой книги**: Автоматическое сохранение позиции воспроизведения
- **Визуальные индикаторы**: Полосы прогресса на миниатюрах обложек
- **Фильтрация по статусу**: Фильтр по статусу (Не начато, В процессе, Завершено)
- **Восстановление сессии**: Возобновление последней прослушанной книги при запуске
- **Закладки**: Создание и управление закладками с визуальными метками на шкале прогресса
- **Состояние раскрытия папок**: Запоминает, какие папки были раскрыты в библиотеке

### 🎨 Интерфейс
- **Современная тёмная тема**: Элегантный и приятный для глаз интерфейс
- **Двухпанельная компоновка**: Браузер библиотеки слева, управление плеером справа
- **Контекстные меню**: Правый клик для быстрых действий (Воспроизвести, Отметить прочитанным, Открыть папку)
- **Многоязычность**: Полная локализация интерфейса (12 языков: AR, DE, EN, ES, FR, HI, JA, KO, PT, RU, TR, ZH)


### 🎛️ Умная обработка звука
- **Smart Auto-Rewind**: Автоматическая перемотка назад после паузы для восстановления контекста (Базово 5с + 2с за минуту паузы, макс. 30с).
- **Улучшение голоса**:
  - **De-Esser**: Уменьшает резкие свистящие звуки (с/ш) с пресетами (Лёгкий/Средний/Сильный).
  - **Компрессор**: Выравнивает динамический диапазон для равномерной громкости.
  - **Шумоподавление**: Удаляет фоновый шум для чёткости речи.
- **Управление высотой тона**: Изменение тона без изменения скорости (+/- 12 полутонов).

### ⌨️ Горячие клавиши
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

> [!NOTE]
> Мультимедийные клавиши (`Play`, `Pause`, `Stop`, `Next`, `Prev`) являются **глобальными** и работают, даже когда приложение свёрнуто или находится не в фокусе.


## 🚀 Установка

### Требования
- Windows 10/11 (64-bit)
- Python 3.8+ (для запуска из исходников)

### Вариант 1: Скачать исполняемый файл (рекомендуется)
1. Скачайте последний релиз со страницы [Releases](../../releases)
2. Распакуйте архив в нужное место
3. Запустите `SP Audiobook Player.exe`


<details>
<summary>💻 Запуск из исходников и сборка</summary>

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

[!NOTE]
Если автоматическая загрузка не удалась, вы можете скачать `ffmpeg-release-essentials.zip` с сайта [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), извлечь `ffmpeg.exe` и `ffprobe.exe` и разместить их следующим образом:
- **Запуск из исходников**: `resources/bin/`
- **Для собранной версии**:
```text
SP Audiobook Player/
├── SP Audiobook Player.exe
└── _internal/resources/bin/
    ├── ffmpeg.exe
    └── ffprobe.exe
```
</details>

## 📘 Использование

### Первый запуск
1. При первом запуске откройте **Настройки** (Меню → Настройки)
2. Укажите путь к вашей библиотеке аудиокниг
3. Нажмите **"Сканировать библиотеку"** для индексации аудиокниг (недостающий ffmpeg будет скачан автоматически)
4. (Опционально) Установите ffprobe через **"Проверить/Обновить ffprobe"** для лучшей поддержки метаданных

   > [!NOTE]
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

### ⚙️ Настройки
- **Путь к библиотеке**: Изменение расположения вашей библиотеки аудиокниг.
- **Сканировать библиотеку**: Ручной запуск сканирования.
- **Инструменты**:
  - **Конвертер в Opus**: Встроенный инструмент для оптимизации размера библиотеки путем конвертации файлов в формат Opus.
  - **FFmpeg/FFprobe**: Проверка статуса и обновление.
  - **Сброс данных**: Очистка всей базы данных и обложек (полезно для чистого пересканирования).
- **Авто-обновление**: Встроенный механизм проверки и установки обновлений приложения.




## 🙏 Благодарности

- **BASS Audio Library**: Высококачественное воспроизведение аудио
- **PyQt6**: Современный фреймворк для GUI
- **Mutagen**: Чтение метаданных аудио
- **FFmpeg/ffprobe**: Расширенное извлечение метаданных
- **RNNoise**: Интеллектуальное шумоподавление
- **BASS_VST**: Поддержка VST-эффектов для BASS

---

<div align="center">
Made with ❤️ for audiobook lovers
</div>
