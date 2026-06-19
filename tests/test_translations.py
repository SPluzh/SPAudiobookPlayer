from pathlib import Path
from tests.check_translations import check_all_translations

def test_translations_integrity():
    """Verify that all translation files contain all keys used in code and match the English reference."""
    project_root = Path(__file__).resolve().parent.parent
    total_missing = check_all_translations(project_root)
    assert total_missing == 0, f"Found {total_missing} missing translations. Run 'python tests/check_translations.py' for details."
