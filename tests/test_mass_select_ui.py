import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from main import AudiobookPlayerWindow

def test_mass_select_ui_behavior(tmp_path):
    app = QApplication.instance() or QApplication([])

    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(
            "[Library]\n"
            "remember_filter_folders=True\n"
            "show_folders=False\n"
        )

    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer'), \
         patch('main.get_base_path', return_value=tmp_path):
         
        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []
         
        window = AudiobookPlayerWindow()
        library = window.library_widget

        # Verify mass select button exists and is configured
        assert hasattr(library, 'btn_mass_select')
        assert library.btn_mass_select.isCheckable() is True
        assert library.btn_mass_select.isChecked() is False
        assert hasattr(library, 'btn_mass_select_arrow')

        # Toggle mass selection
        library.btn_mass_select.click()
        assert library.tree.mass_selection_mode is True
        assert library.btn_mass_select.isChecked() is True
        assert library.delegate.tree == library.tree

        # Check path selection persistence
        library.tree.selected_audiobook_paths.add("dummy_path")
        assert "dummy_path" in library.tree.selected_audiobook_paths
        
        # Untoggle mass selection clears paths
        library.btn_mass_select.click()
        assert library.tree.mass_selection_mode is False
        assert library.btn_mass_select.isChecked() is False
        assert len(library.tree.selected_audiobook_paths) == 0

        # Test select all / deselect all logic
        def make_mock_book(id_, path, name):
            return {
                "id": id_,
                "path": path,
                "name": name,
                "title": name,
                "author": "Author",
                "narrator": "Narrator X",
                "time_added": 100.0,
                "is_folder": False,
                "file_count": 1,
                "duration": 1000,
                "listened_duration": 0,
                "progress_percent": 0.0,
                "codec": "mp3",
                "bitrate_min": 128,
                "bitrate_max": 128,
                "bitrate_mode": "cbr",
                "container": "mp3",
                "description": "",
                "total_size": 1000000,
                "is_started": False,
                "is_completed": False,
                "is_favorite": False,
            }
        
        books = [
            make_mock_book(1, "path/A", "Book A"),
            make_mock_book(2, "path/B", "Book B"),
        ]
        
        mock_db.get_audiobook_count.return_value = 2
        mock_db.load_audiobooks_from_db.return_value = {"": books}
        
        library.load_audiobooks(use_cache=False)
        
        library.select_all_audiobooks()
        assert library.tree.mass_selection_mode is True
        assert library.btn_mass_select.isChecked() is True
        assert "path/A" in library.tree.selected_audiobook_paths
        assert "path/B" in library.tree.selected_audiobook_paths
        assert len(library.tree.selected_audiobook_paths) == 2
        
        library.deselect_all_audiobooks()
        assert len(library.tree.selected_audiobook_paths) == 0
