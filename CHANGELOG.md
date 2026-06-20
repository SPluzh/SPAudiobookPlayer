# Changelog

All notable changes to this project will be documented in this file.

## [1.7.11]
- **Metadata**: Fixed online cover search for Audible and Storytel to prevent displaying unrelated images or incorrect book covers when no matching books are found.

## [1.7.10]
- **UI**: Centered the book details text vertically next to the cover image in the library list for a cleaner layout.

## [1.7.9]
- **UI**: Added the ability to customize interface icon colors and line thickness in the Appearance settings with instant live preview.
- **UI**: Added support for reordering, sorting, and toggling fields in the library's audiobook details line.
- **Library**: Added interactive book tags with hover effects and quick filtering by clicking them.
- **Settings**: Database clearing now fully deletes listening history, statistics, bookmarks, and tags.

## [1.7.8]
- **Metadata**: Fixed manual cover scanning for playlist-based audiobooks in the edit dialog.
- **Metadata**: Added support for parent folder cover inheritance when manually scanning for covers.
- **Library**: Re-scanning an audiobook or manually refreshing its covers now updates and overwrites the cached cover images to reflect changes on disk.
- **Library**: Existing values for title, author, narrator, writing/recording years, and language are no longer overwritten during library updates if they are already populated.
- **Settings**: Added a "Force rescan" option to the library update section, allowing users to perform a clean library refresh and clear cached cover art.
- **Library**: Fixed an issue where updated or overwritten cover art images for audiobooks in the library did not refresh in the list after a scan unless the application was restarted.

## [1.7.7]
- **Playback**: Automatically stops the playing audiobook when starting conversion to Opus to prevent file errors.
- **Opus Converter**: Added a quick reference explaining the benefits of Opus, recommended bitrates, and stereo-to-mono settings.
- **Scanner**: Subfolders without their own cover image will now automatically inherit the cover image from their parent folder.

## [1.7.6]
- **Metadata**: Added platform source labels (Litres, Storytel, Goodreads, Audible, Web) to cover search results.
- **Metadata**: Integrated Audible, Litres, Storytel, and Goodreads as native cover search scrapers.
- **Metadata**: Added online cover search with hover previews to the metadata editor.

## [1.7.5]
- **Library**: Fixed a bug where right-clicking an item in the library to open the context menu would cause the list to unexpectedly jump to the top.
- **Library**: Added display of writing year, recording year, and language in the audiobook details line with polished icon spacing.
- **Scanner**: Optimized folder merge updates by scanning only the merged subfolder instead of the entire library.
- **Scanner**: Optimized library rescanning speed by avoiding slow recursive searches for cover files in unchanged audiobook folders.

## [1.7.4]
- **Library**: Added checkbox selection support for folder items in mass selection mode, enabling recursive selection and deselection of all nested contents.
- **Metadata**: Added support for bulk/mass editing of metadata for multiple selected audiobooks, complete with field-activation checkboxes and default preset states.
- **Scanner**: Added support for extracting language, writing year, and recording year
- **Scanner**: Added real-time scanning progress tracking with percentage and audiobook count in the progress bar and status label.
- **Library**: Added sorting options for book writing date, audiobook recording date, and language.
- **Library**: Refined folder view sorting to always sort folders alphabetically (ascending or descending) while audiobooks inside them follow the chosen sort field.

## [1.7.3]
- **Library**: Reorganized the audiobook context menu to display the "Play" action first, followed by a grouped section of all batch-compatible actions (Favorites, Tags, Mark as Read/Unread, Convert to Opus), and placed the single-book "Delete" action at the very bottom.
- **Library**: Added a "Convert to Opus" option to the audiobook context menu, allowing users to convert individual books or multiple selected books at once, followed by an automatic directory rescan to update book entries.
- **UI**: Fixed an issue in minimal interface mode where the bookmark buttons (Mark and +) were compressed vertically and overlapped by the volume slider.

## [1.7.2]
- **Library**: Added a mass selection button to the toolbar and checkboxes to audiobook rows.
- **Library**: Added a dropdown menu next to the mass selection button with options to select all visible books or clear the current selection.
- **Library**: Added support for batch assigning/managing tags, clearing tags, and toggling favorite status for all selected books from the context menu.
- **Library**: Added support for batch marking selected audiobooks as read or unread from the context menu.
- **UI**: Moved the folder visibility button to the left of the sort controls in the library toolbar.

## [1.7.1]
- **Library Deletion**: Added a checkbox to the audiobook delete dialog allowing users to delete book files directly from the disk.
- **Library Sorting**: Added an option to sort the library by reading progress percentage.

## [1.7.0]
- **UI**: Added a View menu option to remember whether folders are displayed or hidden separately for each tab (All, New, Started, Finished).
- **Library Sorting**: Added a sorting field dropdown (Title, Author, Date, etc.) and alphabetical A-Z/Z-A buttons, with preferences saved separately for each tab.

## [1.6.26]
- **Localization**: Added full support for Armenian language (Հայերեն), including comprehensive interface translations.

## [1.6.25]
- **Library UI**: Added colored status triangles (red for new, yellow for started, green for completed) to the top-left corner of audiobook covers in the library.
- **Library UI**: Added a View menu option to show/hide status triangles on book covers.

## [1.6.24]
- **Library UI**: Replaced text-based emoji prefixes (files, duration, size, bitrate) in the audiobook information line with custom graphical icons.
- **UI (About Dialog)**: Added global media hotkeys documentation, M3U/M3U8 playlists, and a feedback link.
- **UI (About Dialog)**: Refined layout (version moved to title, added cover formats list, and reordered formats).
- **UI (About Dialog)**: Documented description text files support (info.txt, description.txt, or about.txt).
- **Playback**: Added a quick access "+" button next to the Bookmarks button to directly add a bookmark at the current playback position.
- **Statistics**: Reordered list items and heatmap tooltips to show the title first, and added graphical icons for author, narrator, and duration.

## [1.6.23]
- **M3U Support**: Added full support for M3U/M3U8 playlists as audiobooks — both local files and network streams. Playlists are scanned, registered in the library, and played back with correct metadata, duration, cover art, and saved position restoration.
- **M3U Structure**: Recommended folder layout for network playlists:
    - **One playlist per folder** — place a single `.m3u`/`.m3u8` file in a dedicated folder named `Author - Title [Narrator]`; an optional `cover.jpg` in the same folder will be used as the book cover.
    - **Multiple playlists per folder** — place several `.m3u`/`.m3u8` files in one folder; each playlist is registered as a separate audiobook.

## [1.6.22]
- **Library**: Replaced the text-based narrator emoji with a custom graphical icon.
- **Library**: Added a custom writer icon before the author's name in the audiobook list.
- **Library**: Swapped the order of information to display the audiobook title above the author's name.
- **Library**: Added interactive author and narrator fields that bold and change the mouse cursor on hover.
- **Library**: Clicking on an author or narrator in the list view automatically populates the search bar to filter by that person.

## [1.6.21]
- **Library**: Added total file size tracking for audiobooks, displaying the formatted total book size (e.g. `💾 120.4 MB`) within the tree view (requires a library rescan to populate sizes for existing audiobooks).
- **UI**: Added a checkable option in the View menu to show or hide the detailed metadata row (progress, file count, duration, and size) for audiobooks in the library.

## [1.6.20]
- **Playback**: Added a floating real-time time tooltip that appears above the progress slider handle during manual seeking/scrubbing to show the target position.
- **Playback**: Fixed an issue where dragging the seek slider all the way to the right edge would cause it to bounce back to the beginning or switch chapters.
- **Taskbar**: Fixed taskbar progress bar turning green after computer wake from sleep while playback was paused.

## [1.6.19]
- **Metadata**: Added support for choosing a book cover in the metadata edit dialog when multiple covers are available.
- **Metadata**: Unified all action buttons (Open Folder, Refresh, and From Tags) into a compact vertical panel.
- **Metadata**: Added support for `.webp` audiobook cover images.
- **Metadata**: Fixed an issue where custom selected covers could be reset or overwritten during library rescans.
- **Metadata**: Fixed a bug where scanning or refreshing the folder of an audiobook could result in duplicate covers, prevent newly added covers (e.g., `cover.jpg`) from appearing, or fail to clear the cover image in the library after all cover images are deleted from the folder.
- **UI**: Redesigned the "About" dialog into a wider two-column layout.

## [1.6.18]
- **Statistics**: Guarded listening session recording against system sleep, hibernation, and OS freezes by ignoring sudden elapsed time jumps greater than 30 seconds.
- **Build**: Significantly reduced the installer and application size by cleaning up unused internal files, while keeping all built-in features fully intact.

## [1.6.17]
- **Audio Controls**: Added **Volume Boost** button (**VB**) — amplifies volume up to 400%, adjustable via right-click slider (200/300/400%).
- **UI**: Added **Show Status Bar** toggle to the **View** menu — status bar visibility is now remembered across restarts.

## [1.6.16]
- **Library**: Added display of total audiobook count and cumulative duration recursively to folder items in the library tree.
- **Library**: Fixed visual overlapping of horizontal folder separator lines with vertical hierarchy lines.
- **Statistics**: Increased the size of book covers in the history list from 55px to 75px for better visibility.
- **Statistics**: Enhanced book cover image rendering using high-resolution scaling to ensure crisp, blur-free, and perfectly scaled images on all displays.
- **UI**: Added a languages icon to the language menu item.
- **UI**: Added expand and collapse icons to the view menu items.
- **UI**: Added a locate icon to the reveal current audiobook menu item.
- **UI**: Added an update icon to the check for updates menu item.

## [1.6.15]
- **Playback**: Fixed a bug where the very end of a track (around 200ms) was cut off during automatic transitions.
- **Statistics**: Replaced default daily listening heatmap tooltips with a high-performance, lag-free custom popup.
- **Statistics**: Improved tooltip layout to display the author and title on separate lines with automatic text wrapping.
- **Statistics**: Excluded the current month of the last year from the far-left heatmap column to avoid redundant month labels.
- **Statistics**: Unified dialog labels, timestamps, card values, and heatmap cells to match the application's active text and accent colors.
- **Statistics**: Redesigned book rows (author, title, and narrator on separate lines with unified fonts) and added progress and total duration (⏱) to the timeline.
- **Statistics**: Replaced default multi-row mouse wheel scrolling with a smooth, coordinate-based snapping behavior that aligns perfectly to book rows and month headers.
- **Statistics**: Styled month headers in all themes to match the dialogue's standard label colors.
- **Statistics**: Added the total monthly listening duration (hours, minutes, and seconds) directly into the month header lines, matching the abbreviation style of the main stats cards.
- **UI**: Added a listening statistics icon to the menu item.

## [1.6.14]
- **Playback**: Fixed track switching to be instant and reliable when a track finishes, even if the file stops playing a few seconds early.

## [1.6.13]
- **Tags**: Added a "Remove All Tags" action to the audiobook context menu (under the Tags submenu) to quickly clear all assigned tags from the selected book.
- **Tags**: Custom checked tag indicator dot color is now dynamically matched to the theme's active accent color.

## [1.6.12]
- **Library**: Editing an audiobook's author, title, or narrator no longer bumps it to the top of "Recently Listened".
- **Statistics**: Fixed heatmap tooltip showing "No Data" for colored cells with zero listening time — now correctly shows "0 min".
- **Statistics**: Added seconds precision to heatmap day tooltips (e.g., "1h 30m 15s").
- **Statistics**: Added the audiobook start and completion dates/timestamps to the chronological listening history.
- **Statistics**: Added a mini progress bar directly below the cover art inside statistics book rows.
- **Library**: The progress bar is now drawn beautifully directly below the audiobook cover (instead of on top of it) for any started book, even if the progress is 0%.
- **Playback**: Fully completed audiobooks are no longer restored at startup or automatically rewound on exit.
- **Tags**: Checked/assigned tags in the context menu now draw a centered theme-accented dot inside a beautifully rounded tag color icon.

## [1.6.11]
- **Playback**: Improved automatic track switching by optimizing end-of-track detection buffers and fixing audiobook completion logic.

## [1.6.10]
- **Audio Controls**: Added a **Mono** toggle button:
    - Mixes stereo channels (Left + Right) into both speakers.
    - Useful for audiobooks where the narrator is recorded on one side or for listening with a single earbud.

## [1.6.9]
- **Library UI**: Fixed a bug where the hit and hover areas for "i" (info), Play, and Favorite icons were misaligned when books were nested in folders.
- **Scanner**: Fixed text encoding issues when reading book descriptions and CUE files:
    - Implemented robust priority-based encoding detection with heuristics to prevent incorrect UTF-16 interpretation of CP1251 text.

## [1.6.8]
- **Statistics**: Implemented comprehensive listening statistics dialog:
    - Added GitHub-style heatmap visualization for daily listening activity.
    - Added summary cards for total, yearly, monthly, and weekly listening time.
    - Added scrollable chronological history of books listened to by month.
    - **Note**: A full library rescan is required to populate historical data for the new statistics features.

## [1.6.7]
- **Scanner**: Cover images (cover.jpg) and descriptions (description.txt) added or updated after initial scan are applied on next library rescan.

## [1.6.6]
- **Library**: Improved mouse wheel scrolling to move by single row instead of multiple rows.
- **Library**: Added horizontal T-branches to all tree items for clearer nesting visualization.

## [1.6.5]
- **UI**: Added **Expand All Folders** (`E`) and **Collapse All Folders** (`W`) actions to the **View** menu.

## [1.6.4]
- **UI**: Added colored nesting lines to the library tree view with a toggle option in **View → Show Nesting Lines**.

## [1.6.3]
- **Localization**: Added comprehensive support for 3 new languages:
    - **Vietnamese** (Tiếng Việt)
    - **Thai** (ไทย)
    - **Indonesian** (Indonesian)

## [1.6.2]
- **Navigation**: Added **Reveal Current Audiobook** feature:
    - New menu item: **View → Reveal Current Audiobook (L)**.
    - Hotkey **L** instantly scrolls to and highlights the currently playing book in the library.
- **Hotkeys**: Added keyboard shortcuts for View menu items:
    - **P** — Toggle Minimal Interface mode.
    - **T** — Toggle Always on Top mode.

## [1.6.1]
- **Feature**: Added **Always on Top** mode to the **View** menu.

## [1.6.0]
- **UI**: Implemented **Minimal Interface** mode:
    - Added a "View" menu with a toggle to hide/show the library and playlist sections.

## [1.5.7]
- **UI**: Implemented **Active Folder Indicator** in the library:
    - Folders containing the currently playing audiobook now display an accent pill-colored bar on the left.

## [1.5.6]
- **Bookmarks**: Added display of bookmark markers on the progress bar.

## [1.5.5]
- **Library**: Added **Smart Search** functionality.
    - Implemented fuzzy matching for misspelled search terms (e.g. omitted characters).
    - Added automatic keyword transliteration to handle incorrect keyboard layouts (RU <-> EN).
    - Unified the search to query across author, title, narrator, codecs, and tags simultaneously.

## [1.5.4]
- **Settings**: Added "Check for updates at startup" toggle to Settings dialog.

## [1.5.3]
- **Auto-Update**: Added automatic update feature.

## [1.5.2]
- **Library**: Added ability to **Convert Library to Opus** format to save space while maintaining high quality:
    - **Performance**: Parallel multi-threaded processing using all available CPU cores.
    - **Smart Conversion**: Adjustable bitrate (24k-64k) with intelligent stereo-to-mono downmixing.
    - **Seamless Integration**: Preserves all metadata, covers, and playback progress; updates database in real-time.
    - **UX**: Detailed progress dialog with cancellation support.

## [1.5.1]
- **Drag & Drop**: Implemented comprehensive file and folder drop support

## [1.5.0]
- **Bookmarks**: Implemented a complete bookmarking system:
    - Added "Mark" button to player controls.
    - Dialogs for adding, editing, and managing bookmarks.
    - Bookmarks are sorted by position in the book.
    - Supports custom titles and descriptions.

## [1.4.3]
- **Visualizer**: Implemented real-time waveform visualization.
Visualization is integrated directly into the Play/Pause button for a seamless look.

## [1.4.2]
- **UI**: Added **Empty Library Placeholder** with instructional text and a clickable folder icon.

## [1.4.1]
- **Themes**: Added full support for dynamic theme switching:
    - Included **Dark Mint** and **Dark Pink** themes.
    - Implemented instant style reloading without application restart.

## [1.4.0]
- **Localization**: Extensive expansion of language support:
    - Added 10 new languages: **Arabic**, **Chinese**, **French**, **German**, **Hindi**, **Japanese**, **Korean**, **Portuguese**, **Spanish**, and **Turkish**.
    - **Dynamic Loading**: Application now automatically scans the `resources/translations` directory and adds new languages back to the settings menu.

## [1.3.8]
- **Library**: Added **Tag Filter** button enabling tag selection from a dropdown list.
- **Library**: Added **Open Library Folder** option to the main menu.

## [1.3.7]
- **Scanner**: Implemented support for **Single-File Audiobooks**.
    - Detects and processes standalone audio files (e.g., `.m4b`, `.mp3`) located in the library root.
    - Extracts metadata and cover art directly from individual files.

## [1.3.6]
- **Library**: Added **Audiobook Description** feature:
    - **Scanner**: Automatically detects `description.txt`, `info.txt`, `about.txt`, or `{folder_name}.txt` inside audiobook folders.
    - **UI**: Displays an "Info" (i) icon on the book cover if a description is found.
    - **Dialog**: Clicking the icon opens a dedicated window with the book description.

## [1.3.5]
- **Performance**: Implemented comprehensive **Cover Caching** system:
    - Covers are extracted, resized (to 300x300), and cached during scanning to `data/extracted_covers`.
    - Significantly reduces memory usage and improves library scrolling performance.
    - Added `lru_cache` to style calculations for smoother UI rendering.

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
