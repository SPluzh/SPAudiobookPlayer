# Changelog

All notable changes to this project will be documented in this file.

## [1.3.4]
- **Metadata**: Implemented **Edit Metadata** context menu option.
    - Allows manual editing of Author, Title, and Narrator fields.

## [1.3.3]
- **Pitch Control**: Implemented independent pitch shifting functionality.
    - Added "Pitch" toggle button with context menu for fine-tuning (-12 to +12 semitones).

## [1.3.2]
- **Library**: Implemented **Virtual Merge** feature for folders:
    - Allows merging a folder and its subfolders into a single audiobook without changing physical files.

## [1.3.1]
- **UI**: Improved **Noise Suppression** settings popup:
    - Popup now appears correctly below the button.
    - Added dynamic translation support for popup labels (Sensitivity, Grace Period, Retroactive).
    - Labels update instantly when changing application language.

## [1.3.0]
- **Noise Suppression**: Added advanced noise reduction system (Right-click **NS** button to configure).
    - Features tunable **VAD** (Voice Activity Detection): Sensitivity, Grace Period, and Retroactive recording.
- **Audio Effects**: Updated **De-Esser** and **Compressor** with adjustable presets.
    - Added **Light**, **Medium**, and **Strong** modes (Right-click to select).
- **Localization**: Full translation of player buttons (ID3, AR, DS, C, NS).

## [1.2.0]
- **Favorites**: Mark audiobooks as "Favorites" (❤) via context menu.
    - Added dedicated "Favorites" filter to the main toolbar.
    - Visual heart indicator on book covers.
- **Tags**: Comprehensive tagging system for organizing the library.
    - **Tag Manager**: Create, edit, and delete custom colored tags.
    - **Assignment**: Assign multiple tags to books via context menu.
    - **Visualization**: Tags appear as colored chips under the book details.
    - **Search**: integrated tag search (e.g., searching for "Sci-Fi" finds books with that tag).

## [1.1.12]
- **Audio Engine**: Added support for **APE** (Monkey's Audio) format:
    - Integrated `bassape` plugin for high-quality lossless playback.
    - Implemented **CUE Sheet** support for reading metadata (Performer, Title, Year) and splitting single-file audiobooks into chapters.
    - Enhanced scanner to extract APEv2 tags and embedded cover art.
    - Improved recursive cover search to find artwork in subdirectories.

## [1.1.11]
- **Library**: Added comprehensive "Delete" functionality for both audiobooks and folders

## [1.1.10]
- **UI**: Implemented a sophisticated background blur effect for modal dialogs

## [1.1.9]
- **Library Sorting**: Implemented reliable chronological sorting for the 'Started' filter

## [1.1.8]
- **M4B Chapter Support**: Implemented comprehensive support for embedded chapters in M4B/MP4/M4A files

## [1.1.7]
- **Audio Engine**: Added support for **FLAC** audio format:
    - Integrated `bassflac` plugin for seamless FLAC playback.
    - Implemented comprehensive metadata extraction (Vorbis comments) for the library scanner.
    - Added support for embedded cover art extraction from FLAC files.

## [1.1.6]
- **Library Sorting**: Implemented persistent and meaningful sorting for library filters

## [1.1.5]
- **Scanner**: Added support for `.mp4` audio files.
    - Updated scanning logic to recognize `.mp4` extensions and extract metadata/covers.
    - Enhanced file analysis for duration and bitrate detection for MP4 containers.

## [1.1.4]
- **Technical Metadata**: Added extraction and library-wide display of audio technical info.
    - Implemented storage for `codec`, `bitrate`, `bitrate_mode`, and `container`.
    - Refined library UI with a compact tech info line: `💽 128 kbps CBR mp3`.
    - Improved bitrate display with automatic conversion from bps to kbps and localized units.
- **Scanner**: Enhanced codec detection by prioritizing real stream analysis via `ffprobe` over file extensions.
    - Accurate identification of Opus/AAC in M4B containers and Opus/Vorbis in OGG.
- **Search**: Extended library filtering to support searching by codec name and bitrate.
- **Fix**: Resolved critical application crash on launch caused by a translation typo and missing database columns.

## [1.1.3]
- **Audio**: Added support for M4B/MP4 files with **Opus** codec by implementing 

## [1.1.2]
- **UI**: Improved audiobook cover rendering:
    - Non-square covers now have their background extended using a blurred, edge-stretched version of the image to fill the square area seamlessly.

## [1.1.1]
- **Audio**: Added support for **M4B** and **AAC** files via `bass_aac` plugin.

## [1.1.0]
- **Audio Engine**: Added support for OPUS audio format via `bassopus` plugin integration.

## [1.0.6]
- **Audio**: Added **Compressor** effect (Toggle "C") with "Hard" preset for consistent volume in audiobooks.
- **Audio**: Added **De-Esser** effect (Toggle "DS") with "Soft" (-6dB) preset for more natural sound.
- **UI**: Redesigned player controls layout:
    - Effects buttons (ID3, AR, DS, C) moved to a dedicated top row.
    - Volume and Speed sliders combined into a single compact row.
    - Reduced margins and spacing for a streamlined interface.

## [1.0.5]
- **UI**: Added icons to the Settings dialog buttons for better visual clarity (Save, Scan, Reset, Update, Browse).

## [1.0.4]
- **Performance**: instant switching between library filters (`All`, `In Progress`, `Completed`) by implementing client-side filtering. No more database reloads on filter change.
- **Performance**: instant toggling of "Show Folders" view by caching library data structure.
- **Performance**: implemented LRU cache for cover icons to eliminate disk I/O and image scaling during library rendering.
- **UI**: Added high-quality antialiasing (`SmoothPixmapTransform`) for all cover and icon rendering.

## [1.0.3]
- **Hotkeys**: Added comprehensive keyboard support:
    - `Space` — Play/Pause.
    - `Up` / `Down` — Playback speed.
    - `Shift + Up` / `Down` — Volume control.
    - `Left` / `Right` — 10s seeking.
    - `Shift + Left` / `Right` — 60s seeking.
    - `[` / `]` — Previous/Next track.
- **Multimedia Keys**: Implemented truly global support for system media keys (Play, Pause, Next, Prev) that works even when the application is in the background.

## [1.0.2]
- **Auto-Rewind**: Added "AR" button to toggle automatic 10-30s rewind after pauses and 30s rewind on application close. State is persisted in settings.

## [1.0.1]
- **Folders**: Flat view by default; state persisted. Toggle converted to icon-only.
- **UI**: Adaptive filter buttons (icon-only < 450px) with tooltips. Optimized button widths for translations.
