import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from settings_dialog import SettingsDialog
from translations import tr

def test_settings_dialog_translation():
    # Ensure a QApplication instance exists
    app = QApplication.instance() or QApplication([])

    # Create dialog with a custom target lang and provider
    dialog = SettingsDialog(
        None,
        current_path="C:/DummyLibrary",
        ffprobe_path=Path("dummy_ffprobe"),
        subtitle_target_lang="es",
        subtitle_translation_provider="google"
    )
    
    # 1. Verify widgets exist and are configured correctly
    assert hasattr(dialog, 'lang_combo')
    assert hasattr(dialog, 'provider_combo')
    
    assert dialog.lang_combo.currentData() == "es"
    assert dialog.provider_combo.currentData() == "google"

    # 2. Verify signal emission when saving settings
    emitted_lang = None
    emitted_provider = None
    
    def on_lang_changed(lang):
        nonlocal emitted_lang
        emitted_lang = lang

    def on_provider_changed(provider):
        nonlocal emitted_provider
        emitted_provider = provider

    dialog.subtitle_target_lang_changed.connect(on_lang_changed)
    dialog.subtitle_translation_provider_changed.connect(on_provider_changed)
    
    # Select fr as target language
    idx_lang = dialog.lang_combo.findData("fr")
    assert idx_lang != -1
    dialog.lang_combo.setCurrentIndex(idx_lang)
    
    # Select google as provider
    idx_provider = dialog.provider_combo.findData("google")
    assert idx_provider != -1
    dialog.provider_combo.setCurrentIndex(idx_provider)
    
    # Trigger save action
    dialog.on_save()
    assert emitted_lang == "fr"
    assert emitted_provider == "google"
