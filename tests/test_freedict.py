import pytest
import urllib.error
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from settings_dialog import SettingsDialog
from subtitle_translator import TranslationWorker, TranslationPopup
from database import DatabaseManager, init_database

def test_settings_dialog_freedict_provider():
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(
        None,
        current_path="C:/DummyLibrary",
        ffprobe_path=Path("dummy_ffprobe"),
        subtitle_target_lang="en",
        subtitle_translation_provider="freedict"
    )

    assert hasattr(dialog, 'provider_combo')
    assert dialog.provider_combo.findData("freedict") != -1
    assert dialog.provider_combo.currentData() == "freedict"

def test_translation_worker_freedict_mock(monkeypatch):
    app = QApplication.instance() or QApplication([])

    fake_response_data = [
        {
            "word": "test",
            "phonetic": "/test/",
            "phonetics": [
                {"text": "/test/", "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/test-us.mp3"}
            ],
            "meanings": [
                {
                    "partOfSpeech": "noun",
                    "definitions": [
                        {"definition": "A procedure intended to establish the quality, performance, or reliability of something.", "example": "both groups took a test"}
                    ],
                    "synonyms": ["trial", "experiment"]
                }
            ]
        }
    ]

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def read(self):
            import json
            return json.dumps(fake_response_data).encode('utf-8')

    def fake_urlopen(req, timeout=5, context=None):
        return FakeResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    worker = TranslationWorker("test", target_lang="ru", provider="freedict")

    result_received = {}

    def on_finished(orig, result):
        result_received.update(result)

    worker.finished.connect(on_finished)
    worker.run()

    assert result_received.get("provider") == "freedict"
    assert result_received.get("phonetic") == "/test/"
    assert "noun" in result_received.get("parts_of_speech", {})
    assert "trial" in result_received.get("synonyms", {}).get("noun", [])

def test_translation_worker_502_error_handling(monkeypatch):
    app = QApplication.instance() or QApplication([])

    def fake_urlopen_502(req, timeout=5, context=None):
        raise urllib.error.HTTPError(req.full_url, 502, "Bad Gateway", {}, None)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_502)

    worker = TranslationWorker("testword", target_lang="ru", provider="freedict")

    error_received = []

    def on_error(err_msg):
        error_received.append(err_msg)

    worker.error.connect(on_error)
    worker.run()

    assert len(error_received) == 1
    assert "502" in error_received[0]

def test_per_provider_translation_cache(tmp_path):
    db_file = tmp_path / "test.db"
    init_database(db_file)
    db = DatabaseManager(db_file)

    # Save translation for google provider
    google_res = {"translation": "тест", "parts_of_speech": {"noun": ["тест"]}}
    db.save_cached_translation("test", "ru", google_res, provider="google")

    # Save translation for freedict provider
    freedict_res = {"translation": "A procedure intended to establish quality", "phonetic": "/test/", "provider": "freedict"}
    db.save_cached_translation("test", "ru", freedict_res, provider="freedict")

    # Fetch google result
    google_cached = db.get_cached_translation("test", "ru", provider="google")
    assert google_cached is not None
    assert google_cached["translation"] == "тест"
    assert google_cached.get("phonetic", "") == ""

    # Fetch freedict result
    freedict_cached = db.get_cached_translation("test", "ru", provider="freedict")
    assert freedict_cached is not None
    assert freedict_cached["translation"] == "A procedure intended to establish quality"
    assert freedict_cached.get("phonetic") == "/test/"
