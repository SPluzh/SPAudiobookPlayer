import json
from pathlib import Path
from typing import Dict, Optional
from enum import Enum

class Language(Enum):
    """Supported application languages"""
    RUSSIAN = "ru"
    ENGLISH = "en"

class TranslationManager:
    """Application translation manager (singleton)"""
    
    _instance = None
    _translations: Dict[str, Dict[str, str]] = {}
    _current_language = Language.RUSSIAN
    
    def __new__(cls):
        """Create or return the singleton instance"""
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize and load translations"""
        if self._initialized:
            return
        self._initialized = True
        self.translations_dir = Path(__file__).parent / "resources" / "translations"
        self.load_translations()
    
    def load_translations(self):
        """Load all available translation files"""
        self._translations = {}
        
        for lang in Language:
            file_path = self.translations_dir / f"{lang.value}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._translations[lang.value] = json.load(f)
                except Exception as e:
                    print(f"Error loading translation {lang.value}: {e}")
                    self._translations[lang.value] = {}
            else:
                # If file not found, create empty dictionary
                self._translations[lang.value] = {}
    
    def set_language(self, language: Language):
        """Set the current application language"""
        self._current_language = language
    
    def get_language(self) -> Language:
        """Get the current application language"""
        return self._current_language
    
    def translate(self, key: str, default: Optional[str] = None) -> str:
        """Get translated string by key (supports nested keys via dot)"""
        lang_dict = self._translations.get(self._current_language.value, {})
        
        # Support nested keys via dot notation
        keys = key.split('.')
        value = lang_dict
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    break
        
        if value is None or not isinstance(value, str):
            # Fallback to English if translation not found
            if self._current_language != Language.ENGLISH:
                en_dict = self._translations.get(Language.ENGLISH.value, {})
                value = en_dict
                for k in keys:
                    if isinstance(value, dict):
                        value = value.get(k)
                        if value is None:
                            break
                
                if isinstance(value, str):
                    return value
            
            # Return default value or the key itself
            return default if default is not None else key
        
        return value
    
    def format(self, key: str, **kwargs) -> str:
        """Get formatted translation string"""
        template = self.translate(key)
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    
    def save_missing_keys(self, keys: set):
        """Save missing translation keys to missing_keys.json"""
        missing_file = self.translations_dir / "missing_keys.json"
        
        existing = set()
        if missing_file.exists():
            try:
                with open(missing_file, 'r', encoding='utf-8') as f:
                    existing = set(json.load(f))
            except:
                pass
        
        all_keys = existing | keys
        
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(all_keys)), f, indent=2, ensure_ascii=False)


_manager = TranslationManager()

def tr(key: str, default: Optional[str] = None) -> str:
    """Convenience function for translating strings"""
    return _manager.translate(key, default)

def trf(key: str, **kwargs) -> str:
    """Convenience function for formatted translations"""
    return _manager.format(key, **kwargs)

def set_language(language: Language):
    """Convenience function for setting language"""
    _manager.set_language(language)

def get_language() -> Language:
    """Convenience function for getting language"""
    return _manager.get_language()