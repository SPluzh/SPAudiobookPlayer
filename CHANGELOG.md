# Changelog

All notable changes to this project will be documented in this file.

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
