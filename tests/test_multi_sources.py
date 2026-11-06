import os
import shutil
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QTreeWidgetItem, QMessageBox
from PyQt6.QtCore import Qt

from settings_dialog import SettingsDialog
from database import DatabaseManager, init_database
from scanner import AudiobookScanner
from library import LibraryWidget, MultiLineDelegate
from player import PlaybackController
from main import AudiobookPlayerWindow


@pytest.fixture
def app_instance():
    return QApplication.instance() or QApplication([])


def test_settings_dialog_multi_sources_ui(app_instance, tmp_path):
    """Test SettingsDialog path addition, editing, disabling (strikeout), and removal"""
    p1 = str(tmp_path / "lib1")
    p2 = str(tmp_path / "lib2")
    os.makedirs(p1, exist_ok=True)
    os.makedirs(p2, exist_ok=True)

    db_mock = MagicMock()
    dialog = SettingsDialog(
        None,
        current_path=[p1, p2],
        ffprobe_path=Path("dummy_ffprobe"),
        db_manager=db_mock,
        excluded_paths=[p2],
    )

    assert dialog.pathslist.topLevelItemCount() == 2
    item1 = dialog.pathslist.topLevelItem(0)
    item2 = dialog.pathslist.topLevelItem(1)

    assert item1.text(0) == p1
    assert item1.checkState(0) == Qt.CheckState.Checked
    assert not item1.font(0).strikeOut()

    assert item2.text(0) == p2
    assert item2.checkState(0) == Qt.CheckState.Unchecked
    assert item2.font(0).strikeOut()

    # Toggle item1 to unchecked -> font should be strikeout
    item1.setCheckState(0, Qt.CheckState.Unchecked)
    assert item1.font(0).strikeOut()

    # Toggle back to checked -> font strikeout disabled
    item1.setCheckState(0, Qt.CheckState.Checked)
    assert not item1.font(0).strikeOut()

    # Test add_path via patch
    new_p = str(tmp_path / "lib3")
    os.makedirs(new_p, exist_ok=True)
    with patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=new_p):
        dialog.add_path()
    assert dialog.pathslist.topLevelItemCount() == 3
    assert dialog.pathslist.topLevelItem(2).text(0) == os.path.normpath(new_p)

    # Test edit_path on item1
    edited_p = str(tmp_path / "lib1_renamed")
    os.makedirs(edited_p, exist_ok=True)
    dialog.pathslist.setCurrentItem(item1)
    with patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=edited_p):
        dialog.edit_path()
    assert item1.text(0) == os.path.normpath(edited_p)
    assert os.path.normpath(p1) in dialog._deleted_paths

    # Test remove_path on item2
    dialog.pathslist.setCurrentItem(item2)
    with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        dialog.remove_path()
    assert dialog.pathslist.topLevelItemCount() == 2
    assert os.path.normpath(p2) in dialog._deleted_paths

    # Test on_save emits paths_saved and deletes removed paths from DB
    emitted_all = None
    emitted_excluded = None

    def on_paths_saved(all_p, exc_p):
        nonlocal emitted_all, emitted_excluded
        emitted_all = all_p
        emitted_excluded = exc_p

    dialog.paths_saved.connect(on_paths_saved)
    dialog.on_save()

    assert emitted_all is not None
    assert db_mock.delete_audiobooks_by_root.called


def test_settings_migration_and_persistence(tmp_path):
    """Test loading fallback default_path into paths and get_active_library_paths"""
    db_file = tmp_path / "test.db"
    init_database(db_file)
    db = DatabaseManager(str(db_file))

    window = MagicMock(spec=AudiobookPlayerWindow)
    window.db_manager = db
    window.config_file = tmp_path / "settings.ini"

    # Write settings with single default_path (legacy config)
    with open(window.config_file, "w", encoding="utf-8") as f:
        f.write("[Paths]\ndefault_path = C:/LegacyLibrary\n[Library]\n")

    # Call real methods
    window.get_active_library_paths = AudiobookPlayerWindow.get_active_library_paths.__get__(window, AudiobookPlayerWindow)
    window.load_settings = AudiobookPlayerWindow.load_settings.__get__(window, AudiobookPlayerWindow)
    window.save_settings = AudiobookPlayerWindow.save_settings.__get__(window, AudiobookPlayerWindow)
    window.geometry = MagicMock()
    window.geometry.return_value = MagicMock(x=lambda: 0, y=lambda: 0, width=lambda: 100, height=lambda: 100)
    window.saveGeometry = MagicMock(return_value=MagicMock(toHex=lambda: MagicMock(data=lambda: b"00")))
    window.normal_geometry = None
    window.normal_splitter_state = None
    window.current_theme = "dark"
    window.always_on_top = False
    window.show_statusbar = True
    window.default_cover_file = ""
    window.folder_cover_file = ""
    window.inherit_parent_cover = False
    window.show_id3 = True
    window.auto_rewind = False
    window.auto_check_updates = False
    window.show_visualizer = False
    window.show_subtitles = False
    window.subtitle_font_size = 15
    window.subtitle_translation_on_hover = False
    window.subtitle_autoscroll = False
    window.subtitle_target_lang = "en"
    window.subtitle_translation_provider = "freedict"
    window.player = MagicMock(vol_pos=100, speed_pos=10, volume_boost_enabled=False, volume_boost_level=4.0)
    window.deesser_enabled = False
    window.compressor_enabled = False
    window.noise_suppression_enabled = False
    window.vad_threshold = 50
    window.vad_grace_period = 0
    window.vad_retroactive_grace = 0
    window.deesser_preset = 1
    window.compressor_preset = 1
    window.pitch_enabled = False
    window.pitch_value = 0.0
    window.mono_enabled = False
    window.opus_workers = 0
    window.show_filter_labels = True
    window.show_nesting_lines = True
    window.nesting_lines_single_color = False
    window.nesting_lines_color = "#808080"
    window.show_detailed_info = True
    window.show_status_triangle = True
    window.show_info_progress = True
    window.show_info_file_count = True
    window.show_info_duration = True
    window.show_info_size = True
    window.show_info_technical = True
    window.show_info_year_written = True
    window.show_info_year_recorded = True
    window.show_info_language = True
    window.info_order = ""
    window.audiobook_icon_size = 100
    window.audiobook_row_height = 120
    window.statusBar = MagicMock(return_value=MagicMock())
    window.script_dir = tmp_path

    window.load_settings()

    assert window.library_paths == [os.path.normpath("C:/LegacyLibrary")]
    assert window.excluded_library_paths == []
    assert window.get_active_library_paths() == [os.path.normpath("C:/LegacyLibrary")]
    assert window.default_path == os.path.normpath("C:/LegacyLibrary")

    # Add second path and exclude first
    p2 = os.path.normpath("C:/SecondLibrary")
    window.library_paths.append(p2)
    window.excluded_library_paths.append(window.library_paths[0])
    assert window.get_active_library_paths() == [p2]

    # Save settings and verify settings.ini has paths and excluded_paths
    window.save_settings()
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read(window.config_file, encoding="utf-8")
    assert cfg.get("Paths", "paths") == f"{window.library_paths[0]};{p2}"
    assert cfg.get("Paths", "excluded_paths") == window.library_paths[0]
    assert cfg.get("Paths", "default_path") == p2


def test_scanner_multi_sources_rescan_availability(tmp_path):
    """Test scanning multiple library roots without losing availability or root_path metadata"""
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()

    # Create dummy books
    book1 = root1 / "Book1"
    book1.mkdir()
    (book1 / "chapter1.mp3").write_bytes(b"\x00" * 100)

    book2 = root2 / "Book2"
    book2.mkdir()
    (book2 / "chapter1.mp3").write_bytes(b"\x00" * 100)

    db_file = tmp_path / "library.db"
    init_database(db_file)

    config_ini = tmp_path / "settings.ini"
    with open(config_ini, "w", encoding="utf-8") as f:
        f.write(f"""[Paths]
default_path = {root1}
database = {db_file}
covers_dir = {tmp_path / 'covers'}
ffprobe_path = ffprobe
[Audio]
extensions = .mp3
opus_workers = 0
""")

    scanner = AudiobookScanner(str(config_ini))
    scanner.db_file = db_file
    scanner.covers_dir = tmp_path / "covers"
    scanner.covers_dir.mkdir(exist_ok=True)

    # Mock ffprobe metadata extract
    def mock_extract(audio_files, *args, **kwargs):
        return {
            "title": "Title",
            "author": "Author",
            "narrator": "Narrator",
            "files": [{"path": str(f), "duration": 60.0, "track": 1, "title": "Ch", "offset": 0.0, "is_url": False} for f in audio_files],
            "total_duration": 60.0 * len(audio_files),
            "common_codec": "mp3",
            "bitrate_min": 128,
            "bitrate_max": 128,
            "bitrate_mode": "cbr",
            "container": "mp3",
            "language": "en",
            "year_written": "2020",
            "year_recorded": "2020",
            "description": ""
        }
    scanner.extract_metadata = mock_extract

    # 1. Scan root1
    count1 = scanner.scan_directory(str(root1), force_rescan=True)
    assert count1 >= 1

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT path, is_available, root_path FROM audiobooks WHERE is_folder = 0")
    rows1 = c.fetchall()
    conn.close()

    assert len(rows1) == 1
    assert rows1[0][0] == "Book1"
    assert rows1[0][1] == 1
    assert os.path.normpath(rows1[0][2]) == os.path.normpath(str(root1))

    # 2. Scan root2 (clear_covers_cache=False)
    count2 = scanner.scan_directory(str(root2), force_rescan=False, clear_covers_cache=False)
    assert count2 >= 1

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT path, is_available, root_path FROM audiobooks WHERE is_folder = 0 ORDER BY path")
    rows2 = c.fetchall()
    conn.close()

    assert len(rows2) == 2
    # Both books MUST be available!
    assert rows2[0][0] == "Book1"
    assert rows2[0][1] == 1
    assert os.path.normpath(rows2[0][2]) == os.path.normpath(str(root1))

    assert rows2[1][0] == "Book2"
    assert rows2[1][1] == 1
    assert os.path.normpath(rows2[1][2]) == os.path.normpath(str(root2))


def test_library_widget_excluded_paths_and_sources_filter(app_instance, tmp_path):
    """Test excluding roots and filtering by sources in LibraryWidget"""
    root1 = os.path.normpath(str(tmp_path / "root1"))
    root2 = os.path.normpath(str(tmp_path / "root2"))

    db_mock = MagicMock()
    # Mock loaded audiobooks
    db_mock.load_audiobooks_from_db.return_value = {
        "": [
            {
                "path": "Book1", "name": "Book1", "title": "Book 1", "author": "Author A", "narrator": "Narrator A",
                "file_count": 1, "duration": 100, "listened_duration": 0, "progress_percent": 0,
                "codec": "mp3", "bitrate_min": 128, "bitrate_max": 128, "bitrate_mode": "cbr", "container": "mp3",
                "is_folder": False, "is_favorite": False, "is_started": False, "is_completed": False, "root_path": root1, "id": 1
            },
            {
                "path": "Book2", "name": "Book2", "title": "Book 2", "author": "Author B", "narrator": "Narrator B",
                "file_count": 1, "duration": 100, "listened_duration": 0, "progress_percent": 0,
                "codec": "mp3", "bitrate_min": 128, "bitrate_max": 128, "bitrate_mode": "cbr", "container": "mp3",
                "is_folder": False, "is_favorite": False, "is_started": False, "is_completed": False, "root_path": root2, "id": 2
            },
        ]
    }
    db_mock.get_all_audiobook_tags.return_value = {}
    db_mock.get_audiobook_count.return_value = 2
    db_mock.get_available_roots.return_value = [root1, root2]

    config = {
        "default_path": root1,
        "library_paths": [root1, root2],
        "excluded_library_paths": [root2],
        "sort_orders": {"all": "asc"},
        "sort_fields": {"all": "name"},
    }

    delegate = MultiLineDelegate()
    widget = LibraryWidget(db_mock, config, delegate, show_folders=False)

    # Verify Book2 (from root2) is excluded
    widget.load_audiobooks(use_cache=False)
    assert widget.tree.topLevelItemCount() == 1
    assert widget.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) == "Book1"

    # Now clear excluded_library_paths
    widget.config["excluded_library_paths"] = []
    widget.load_audiobooks(use_cache=False)
    assert widget.tree.topLevelItemCount() == 2

    # Now filter by source root2
    widget.selected_sources = {root2}
    widget.is_meta_filter_active = True
    widget.load_audiobooks(use_cache=True)
    assert widget.tree.topLevelItemCount() == 1
    assert widget.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) == "Book2"

    # Reset source filters
    widget._reset_all_meta_filters()
    assert len(widget.selected_sources) == 0
    assert widget.tree.topLevelItemCount() == 2


def test_path_resolution_multi_sources(app_instance, tmp_path):
    """Test path resolution in PlaybackController, LibraryWidget, and MainWindow"""
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()

    book1_dir = root1 / "Book1"
    book1_dir.mkdir()
    f1 = book1_dir / "track.mp3"
    f1.write_bytes(b"\x00" * 100)

    book2_dir = root2 / "Book2"
    book2_dir.mkdir()
    f2 = book2_dir / "track.mp3"
    f2.write_bytes(b"\x00" * 100)

    db_file = tmp_path / "test.db"
    init_database(db_file)
    db = DatabaseManager(str(db_file))

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("""
        INSERT INTO audiobooks (path, name, is_folder, root_path, is_available)
        VALUES ('Book1', 'Book1', 0, ?, 1)
    """, (str(root1),))
    id1 = c.lastrowid
    c.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration)
        VALUES (?, 'Book1/track.mp3', 'track.mp3', 1, 10.0)
    """, (id1,))

    c.execute("""
        INSERT INTO audiobooks (path, name, is_folder, root_path, is_available)
        VALUES ('Book2', 'Book2', 0, ?, 1)
    """, (str(root2),))
    id2 = c.lastrowid
    c.execute("""
        INSERT INTO audiobook_files (audiobook_id, file_path, file_name, track_number, duration)
        VALUES (?, 'Book2/track.mp3', 'track.mp3', 1, 10.0)
    """, (id2,))
    conn.commit()
    conn.close()

    # Test PlaybackController loads root2 book correctly
    player_mock = MagicMock()
    player_mock.load.return_value = True
    player_mock.get_duration.return_value = 10.0
    player_mock.speed_pos = 10
    player_mock.is_playing.return_value = False

    controller = PlaybackController(player_mock, db)
    controller.library_root = Path(root1)

    loaded = controller.load_audiobook("Book2")
    assert loaded is True
    assert controller.current_book_root == Path(root2)
    # player.load should have been called with file in root2
    expected_f2 = str(root2 / "Book2" / "track.mp3")
    player_mock.load.assert_called_with(expected_f2)

    # Test LibraryWidget._resolve_item_abs_path
    widget = LibraryWidget(db, {"default_path": str(root1), "library_paths": [str(root1), str(root2)]}, MultiLineDelegate())
    resolved = widget._resolve_item_abs_path("Book2/track.mp3")
    assert resolved == root2 / "Book2" / "track.mp3"

    # Test MainWindow on_delete_requested with root2 book
    window = MagicMock(spec=AudiobookPlayerWindow)
    window.default_path = str(root1)
    window.db_manager = db
    window.playback_controller = controller
    window.library_widget = MagicMock()
    window.player = MagicMock()
    window.delegate = MagicMock()
    window.statusBar = MagicMock(return_value=MagicMock())
    on_del_bound = AudiobookPlayerWindow.on_delete_requested.__get__(window, AudiobookPlayerWindow)

    with patch("shutil.rmtree") as mock_rm:
        on_del_bound(id2, "Book2", delete_from_disk=True)
        mock_rm.assert_called_once_with(root2 / "Book2")


def test_single_scan_window_for_multiple_sources(app_instance, tmp_path):
    """Verify only one scan window is created for multiple sources, and scans run sequentially"""
    root1 = str(tmp_path / "root1")
    root2 = str(tmp_path / "root2")
    
    window = MagicMock(spec=AudiobookPlayerWindow)
    window.library_paths = [root1, root2]
    window.excluded_library_paths = []
    window.default_path = root1
    window.ffprobe_path = Path("ffprobe")
    window.db_manager = MagicMock()
    window.library_widget = MagicMock()
    window.apply_blur = MagicMock()
    window.remove_blur = MagicMock()
    window.statusBar = MagicMock(return_value=MagicMock())
    window._scan_dialog = None
    window.get_active_library_paths = AudiobookPlayerWindow.get_active_library_paths.__get__(window, AudiobookPlayerWindow)

    rescan_bound = AudiobookPlayerWindow.rescan_directory.__get__(window, AudiobookPlayerWindow)

    with patch("main.ScanProgressDialog") as mock_dialog_cls:
        mock_dialog = MagicMock()
        mock_dialog.isVisible.return_value = True
        mock_dialog_cls.return_value = mock_dialog

        # 1. Trigger rescan
        rescan_bound()
        
        # Only 1 dialog must be created
        assert mock_dialog_cls.call_count == 1
        # It must receive all active paths in one call to scan one after another
        mock_dialog.start_scan.assert_called_once_with([root1, root2], Path("ffprobe"), subfolder_path=None, force_rescan=False)
        assert window._scan_dialog == mock_dialog

        # 2. Trigger rescan again while dialog is already open - must NOT open another window
        rescan_bound()
        assert mock_dialog_cls.call_count == 1
        mock_dialog.raise_.assert_called_once()
