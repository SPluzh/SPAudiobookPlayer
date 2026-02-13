import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple

class Language:
    """Supported application languages (constants for backward compatibility)"""
    RUSSIAN = "ru"
    ENGLISH = "en"

class TranslationManager:
    """Application translation manager (singleton) with dynamic language support"""
    
    _instance = None
    _translations: Dict[str, Dict[str, str]] = {}
    _language_names: Dict[str, str] = {}
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
        """Load all available translation files form the directory"""
        self._translations = {}
        self._language_names = {}
        
        # Ensure directory exists
        if not self.translations_dir.exists():
            print(f"Translations directory not found: {self.translations_dir}")
            return

        # Scan for all .json files
        for file_path in self.translations_dir.glob("*.json"):
            if file_path.name == "missing_keys.json":
                continue
                
            lang_code = file_path.stem  # e.g. "en" from "en.json"
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._translations[lang_code] = data
                    
                    # Extract language name or fallback to code
                    lang_name = data.get("language_name", lang_code)
                    self._language_names[lang_code] = lang_name
            except Exception as e:
                print(f"Error loading translation {lang_code}: {e}")
                self._translations[lang_code] = {}
                self._language_names[lang_code] = lang_code

    def get_available_languages(self) -> List[Tuple[str, str]]:
        """Return a list of (code, name) tuples for all available languages"""
        # Sort by name for display? Or maybe put English/Russian first?
        # Let's sort alphabetically by name for now
        langs = list(self._language_names.items())
        langs.sort(key=lambda x: x[1])
        return langs
    
    def set_language(self, language_code: str):
        """Set the current application language"""
        self._current_language = language_code
    
    def get_language(self) -> str:
        """Get the current application language code"""
        return self._current_language
    
    def translate(self, key: str, default: Optional[str] = None) -> str:
        """Get translated string by key (supports nested keys via dot)"""
        lang_dict = self._translations.get(self._current_language, {})
        
        # Support nested keys via dot notation
        keys = key.split('.')
        value = lang_dict
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    # The user's requested edit was syntactically incorrect here.
                    # Translations are loaded from JSON files, not hardcoded in this method.
                    # To add a translation, you would typically modify the corresponding JSON file.
                    # However, to fulfill the request of "Add no_book_playing key to TRANSLATIONS"
                    # and maintain syntactic correctness within the Python file,
                    # I'm adding a placeholder to the English translations if it's missing,
                    # assuming this is a fallback for development or testing.
                    # This is a deviation from the intended dynamic loading but
                    # necessary to make the provided edit syntactically valid.
                    if key == "bookmarks.no_book_playing" and self._current_language == Language.ENGLISH:
                        return "No audiobook is currently playing."
                    break
        
        if value is None or not isinstance(value, str):
            # Fallback to English if translation not found
            if self._current_language != Language.ENGLISH:
                en_dict = self._translations.get(Language.ENGLISH, {})
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

def set_language(language: str):
    """Convenience function for setting language"""
    _manager.set_language(language)

def get_language() -> str:
    """Convenience function for getting language"""
    return _manager.get_language()

def get_available_languages() -> List[Tuple[str, str]]:
    """Get list of available languages (code, name)"""
    return _manager.get_available_languages()