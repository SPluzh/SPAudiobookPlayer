# 🎧 SP Audiobook Player

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.6.0+-green.svg)](https://pypi.org/project/PyQt6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![Latest Release](https://img.shields.io/github/v/release/USERNAME/REPOSITORY)](https://github.com/USERNAME/REPOSITORY/releases)
[![Downloads](https://img.shields.io/github/downloads/USERNAME/REPOSITORY/total)](https://github.com/USERNAME/REPOSITORY/releases)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English** | [Русский](#-sp-audiobook-player-ru)

---

## 📖 About

**SP Audiobook Player** is a modern and elegant audiobook player for Windows designed for a seamless listening experience. Built with PyQt6 and BASS audio library, it offers automatic library scanning, smart progress tracking per book, and a refined user interface that handles various audio formats and tag encodings effortlessly.

Perfect for audiobook enthusiasts who want a dedicated, feature-rich player with an intuitive interface and robust functionality.


https://github.com/user-attachments/assets/80126acc-8bc2-4c49-b95e-ae3a068343b0


## ✨ Features

### 🎵 Playback
- **Multi-format support**: MP3, M4A, M4B, OGG, FLAC, WAV, WMA, AAC, OPUS
- **High-quality audio**: Powered by BASS audio library
- **Playback speed control**: Adjust from 0.5× to 3.0×
- **Quick navigation**: Skip tracks, rewind/forward 10 or 60 seconds
- **Windows taskbar integration**: Playback controls directly from the taskbar

### 📚 Library Management
- **Automatic scanning**: Recursively scans directories for audiobooks
- **Smart organization**: Automatically groups files into audiobooks by folder
- **Tag support**: Reads author, title, narrator from ID3 tags (MP3) and other metadata
- **Encoding fix**: Handles various tag encodings, including Cyrillic
- **Cover art extraction**: Automatically extracts and displays embedded album art
- **Search functionality**: Find audiobooks by title, author, or narrator
- **Library filters**: Quick access to recently added, started, and finished books
- **Themes**: Choose between "Dark Mint" and "Dark Pink" styles

### 📊 Progress Tracking
- **Per-book progress**: Automatically saves playback position for each audiobook
- **Visual indicators**: Progress bars on cover thumbnails
- **Status filtering**: Filter by status (Not Started, In Progress, Completed)
- **Session restoration**: Resumes the last played audiobook on startup
- **Folder expansion state**: Remembers which folders were expanded in the library

### 🎨 User Interface
- **Modern dark theme**: Elegant and eye-friendly interface
- **Dual-pane layout**: Library browser on the left, player controls on the right
- **Context menus**: Right-click for quick actions (Play, Mark as Read, Open Folder)
- **Bilingual support**: Full interface localization (English/Russian)
- **Themes**: Choose between "Dark Mint" and "Dark Pink" styles


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
| **Play / Pause** | `Space` or `Media Play` |
| **Previous / Next File** | `[` / `]` |
| **Rewind / Forward 10s** | `Left` / `Right` |
| **Rewind / Forward 60s** | `Shift` + `Left` / `Right` |
| **Volume +/- 5%** | `Shift` + `Up` / `Down` |
| **Speed +/- 0.1x** | `Up` / `Down` |
| **Scan Library** | `Ctrl` + `R` |
| **Settings** | `Ctrl` + `,` |


## 🚀 Installation

### Requirements
- Windows 10/11 (64-bit)
- Python 3.8+ (for source installation)

### Option 1: Download Executable (Recommended)
1. Download the latest release from the [Releases](../../releases) page
2. Extract the archive to your desired location
3. Run `SP Audiobook Player.exe`

### Option 2: Run from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/SPAudiobookPlayer.git
   cd SPAudiobookPlayer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## 📘 Usage

### First Launch
1. On first launch, open **Settings** (Menu → Settings)
2. Specify the path to your audiobook library
3. Click **"Scan library"** to index your audiobooks (missing ffmpeg will be downloaded automatically)
4. (Optional) Install ffprobe via **"Check/Update ffprobe"** for better metadata support

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
  - **FFmpeg/FFprobe**: Check status and download updates.
  - **Reset Data**: Clear all library data and covers (useful for clean rescans).


## 📦 Building from Source

To create a standalone executable:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the build script:
   ```bash
   cd _build_
   __build.bat
   ```

3. The executable will be created in `_build_/dist/`



## 🙏 Acknowledgments

- **BASS Audio Library**: High-quality audio playback
- **PyQt6**: Modern GUI framework
- **Mutagen**: Audio metadata reading
- **FFmpeg/ffprobe**: Advanced metadata extraction

---

<a name="-sp-audiobook-player-ru"></a>

# 🎧 SP Audiobook Player (RU)

[English](#-sp-audiobook-player) | **Русский**

---

## 📖 О программе

**SP Audiobook Player** — это современный и элегантный плеер аудиокниг для Windows, созданный для комфортного прослушивания. Построенный на базе PyQt6 и аудиобиблиотеки BASS, он предлагает автоматическое сканирование библиотеки, умное сохранение прогресса для каждой книги и продуманный интерфейс, который корректно работает с различными аудиоформатами и кодировками тегов.

Идеальное решение для любителей аудиокниг, которым нужен функциональный плеер с интуитивным интерфейсом и широкими возможностями.

https://github.com/user-attachments/assets/0217de3d-64f2-4932-9604-54cc257d59d7

## ✨ Возможности

### 🎵 Воспроизведение
- **Поддержка форматов**: MP3, M4A, M4B, OGG, FLAC, WAV, WMA, AAC, OPUS
- **Высокое качество звука**: На базе аудиобиблиотеки BASS
- **Управление скоростью**: Регулировка от 0,5× до 3,0×
- **Быстрая навигация**: Переключение треков, перемотка на 10 или 60 секунд
- **Интеграция с Windows**: Кнопки управления прямо на панели задач

### 📚 Управление библиотекой
- **Автоматическое сканирование**: Рекурсивный поиск аудиокниг в папках
- **Умная организация**: Автоматическая группировка файлов в аудиокниги по папкам
- **Поддержка тегов**: Чтение автора, названия, чтеца из ID3-тегов и других метаданных
- **Исправление кодировки**: Работа с различными кодировками тегов, включая кириллицу
- **Извлечение обложек**: Автоматическое извлечение и отображение встроенных обложек
- **Функция поиска**: Поиск аудиокниг по названию, автору или чтецу
- **Фильтры библиотеки**: Быстрый доступ к недавно добавленным, начатым и завершённым книгам
- **Темы оформления**: Выбор между темами "Dark Mint" и "Dark Pink"

### 📊 Отслеживание прогресса
- **Прогресс для каждой книги**: Автоматическое сохранение позиции воспроизведения
- **Визуальные индикаторы**: Полосы прогресса на миниатюрах обложек
- **Фильтрация по статусу**: Фильтр по статусу (Не начато, В процессе, Завершено)
- **Восстановление сессии**: Возобновление последней прослушанной книги при запуске
- **Состояние раскрытия папок**: Запоминает, какие папки были раскрыты в библиотеке

### 🎨 Интерфейс
- **Современная тёмная тема**: Элегантный и приятный для глаз интерфейс
- **Двухпанельная компоновка**: Браузер библиотеки слева, управление плеером справа
- **Контекстные меню**: Правый клик для быстрых действий (Воспроизвести, Отметить прочитанным, Открыть папку)
- **Двуязычная поддержка**: Полная локализация интерфейса (английский/русский)
- **Темы оформления**: Выбор между темами "Dark Mint" и "Dark Pink (Hatsune Miku)"



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
| **Воспр. / Пауза** | `Пробел` или `Media Play` |
| **Пред. / След. файл** | `[` / `]` |
| **Назад / Вперёд 10с** | `Влево` / `Вправо` |
| **Назад / Вперёд 60с** | `Shift` + `Влево` / `Вправо` |
| **Громкость +/- 5%** | `Shift` + `Вверх` / `Вниз` |
| **Скорость +/- 0.1x** | `Вверх` / `Вниз` |
| **Сканировать** | `Ctrl` + `R` |
| **Настройки** | `Ctrl` + `,` |


## 🚀 Установка

### Требования
- Windows 10/11 (64-bit)
- Python 3.8+ (для запуска из исходников)

### Вариант 1: Скачать исполняемый файл (рекомендуется)
1. Скачайте последний релиз со страницы [Releases](../../releases)
2. Распакуйте архив в нужное место
3. Запустите `SP Audiobook Player.exe`

### Вариант 2: Запуск из исходников
1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/yourusername/SPAudiobookPlayer.git
   cd SPAudiobookPlayer
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Запустите приложение:
   ```bash
   python main.py
   ```

## 📘 Использование

### Первый запуск
1. При первом запуске откройте **Настройки** (Меню → Настройки)
2. Укажите путь к вашей библиотеке аудиокниг
3. Нажмите **"Сканировать библиотеку"** для индексации аудиокниг (недостающий ffmpeg будет скачан автоматически)
4. (Опционально) Установите ffprobe через **"Проверить/Обновить ffprobe"** для лучшей поддержки метаданных

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
  - **FFmpeg/FFprobe**: Проверка статуса и обновление.
  - **Сброс данных**: Очистка всей базы данных и обложек (полезно для чистого пересканирования).


## 📦 Сборка из исходников

Для создания автономного исполняемого файла:

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Запустите скрипт сборки:
   ```bash
   cd _build_
   __build.bat
   ```

3. Исполняемый файл будет создан в `_build_/dist/`


## 🙏 Благодарности

- **BASS Audio Library**: Высококачественное воспроизведение аудио
- **PyQt6**: Современный фреймворк для GUI
- **Mutagen**: Чтение метаданных аудио
- **FFmpeg/ffprobe**: Расширенное извлечение метаданных

---

<div align="center">
Made with ❤️ for audiobook lovers
</div>
