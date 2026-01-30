# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1]
- **Inverted Folder Logic**: Folders are now hidden by default (flat view). The "Show Folders" toggle button restores the hierarchy.
- **Persistence**: The state of the "Show Folders" toggle is saved and restored from `settings.ini`.
- **UI Improvements**:
    - "Show Folders" button is now icon-only with a tooltip.
    - Added tooltips to all library filter buttons ("All", "New", "Started", "Finished").
    - Filter buttons are now adaptive: text labels are hidden when the library panel is too narrow (< 450px).
    - Improved button sizing to dynamic widths to correctly fit translated text
