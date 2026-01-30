# Changelog

All notable changes to this project will be documented in this file.

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
