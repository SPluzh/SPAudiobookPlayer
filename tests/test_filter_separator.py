import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QFrame
from pathlib import Path


def test_filter_separator_exists_and_positioned(tmp_path):
    app = QApplication.instance() or QApplication([])
    from main import AudiobookPlayerWindow

    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    settings_file = resources_dir / "settings.ini"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("[Library]\n")

    with patch('main.DatabaseManager') as mock_db_class, \
         patch('main.BassPlayer') as mock_player_class, \
         patch('main.get_base_path', return_value=tmp_path):

        mock_player = mock_player_class.return_value
        mock_player.vol_pos = 1.0
        mock_player.speed_pos = 1.0
        mock_player.volume_boost_enabled = False
        mock_player.volume_boost_level = 4.0
        mock_player.get_position.return_value = 0.0

        mock_db = mock_db_class.return_value
        mock_db.get_audiobook_count.return_value = 0
        mock_db.load_audiobooks_from_db.return_value = {}
        mock_db.get_all_audiobook_tags.return_value = {}
        mock_db.get_all_tags.return_value = []

        window = AudiobookPlayerWindow()
        library = window.library_widget

        # 1. Attributes exist and are QFrames with VLine shape
        assert hasattr(library, "filter_separator")
        assert isinstance(library.filter_separator, QFrame)
        assert library.filter_separator.objectName() == "filterSeparator"
        assert library.filter_separator.frameShape() == QFrame.Shape.VLine

        assert hasattr(library, "tile_view_separator")
        assert isinstance(library.tile_view_separator, QFrame)
        assert library.tile_view_separator.objectName() == "filterSeparator"
        assert library.tile_view_separator.frameShape() == QFrame.Shape.VLine

        # 2. Check position in layout
        main_layout = library.layout()
        filter_layout = None
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item.layout():
                lay = item.layout()
                for j in range(lay.count()):
                    sub = lay.itemAt(j)
                    if sub.widget() == library.filter_separator:
                        filter_layout = lay
                        break
                if filter_layout:
                    break

        assert filter_layout is not None, "filter_separator not found in any layout"

        # Verify order for tile view separator: btn_tile_view < tile_view_separator < mass_layout
        idx_tile_view = -1
        idx_tile_sep = -1
        idx_mass_layout = -1

        # Verify order for filter separator: tag_filter_layout < filter_separator < filter_buttons["all"]
        idx_separator = -1
        idx_tag_layout = -1
        idx_btn_all = -1

        for j in range(filter_layout.count()):
            item = filter_layout.itemAt(j)
            if item.widget() == library.btn_tile_view:
                idx_tile_view = j
            elif item.widget() == library.tile_view_separator:
                idx_tile_sep = j
            elif item.widget() == library.filter_separator:
                idx_separator = j
            elif item.widget() == library.filter_buttons.get("all"):
                idx_btn_all = j
            elif item.layout():
                sub_lay = item.layout()
                for k in range(sub_lay.count()):
                    w = sub_lay.itemAt(k).widget()
                    if w == library.btn_tags:
                        idx_tag_layout = j
                    elif w == library.btn_mass_select:
                        idx_mass_layout = j

        assert idx_tile_view != -1
        assert idx_tile_sep != -1
        assert idx_mass_layout != -1
        assert idx_tile_view < idx_tile_sep < idx_mass_layout

        assert idx_tag_layout != -1
        assert idx_separator != -1
        assert idx_btn_all != -1
        assert idx_tag_layout < idx_separator < idx_btn_all

        # 3. Check QSS has QFrame#filterSeparator defined
        style_path = Path(__file__).resolve().parent.parent / "src" / "resources" / "styles" / "style.qss"
        assert style_path.exists()
        content = style_path.read_text(encoding="utf-8")
        assert "QFrame#filterSeparator" in content
