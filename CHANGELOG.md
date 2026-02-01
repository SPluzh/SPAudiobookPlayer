# Changelog

All notable changes to this project will be documented in this file.

## [1.0.6]
- **Audio**: Added **Compressor** effect (Toggle "C") with "Hard" preset for consistent volume in audiobooks.
- **Audio**: Switched effects engine to **BASS_FX (BFX)** plugin (`COMPRESSOR2`, `PEAKEQ`), eliminating echo artifacts.
- **Audio**: Refined **De-Esser** ("DS") to be softer (-6dB) and more natural.
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
