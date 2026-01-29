import json
from pathlib import Path
from typing import Dict, Optional
from enum import Enum

class Language(Enum):
    RUSSIAN = "ru"
    ENGLISH = "en"

class TranslationManager:
    """Менеджер переводов приложения"""
    
    _instance = None
    _translations: Dict[str, Dict[str, str]] = {}
    _current_language = Language.RUSSIAN
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.translations_dir = Path(__file__).parent / "resources" / "translations"
        self.load_translations()
    
    def load_translations(self):
        """Загрузка всех доступных переводов"""
        self._translations = {}
        
        for lang in Language:
            file_path = self.translations_dir / f"{lang.value}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._translations[lang.value] = json.load(f)
                except Exception as e:
                    print(f"Ошибка загрузки перевода {lang.value}: {e}")
                    self._translations[lang.value] = {}
            else:
                # Если файл не найден, создаём пустой словарь
                self._translations[lang.value] = {}
    
    def set_language(self, language: Language):
        """Установка текущего языка"""
        self._current_language = language
    
    def get_language(self) -> Language:
        """Получение текущего языка"""
        return self._current_language
    
    def translate(self, key: str, default: Optional[str] = None) -> str:
        """
        Получение перевода по ключу
        
        Args:
            key: Ключ перевода
            default: Значение по умолчанию, если перевод не найден
            
        Returns:
            Переведённая строка
        """
        lang_dict = self._translations.get(self._current_language.value, {})
        
        # Поддержка вложенных ключей через точку
        keys = key.split('.')
        value = lang_dict
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    break
        
        if value is None or not isinstance(value, str):
            # Если перевод не найден, пробуем английский как fallback
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
            
            # Возвращаем default или сам ключ
            return default if default is not None else key
        
        return value
    
    def format(self, key: str, **kwargs) -> str:
        """
        Получение отформатированного перевода
        
        Args:
            key: Ключ перевода
            **kwargs: Параметры для форматирования
            
        Returns:
            Отформатированная строка
        """
        template = self.translate(key)
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    
    def save_missing_keys(self, keys: set):
        """Сохранение отсутствующих ключей для последующего перевода"""
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

# Глобальная функция для удобства
_manager = TranslationManager()

def tr(key: str, default: Optional[str] = None) -> str:
    """Быстрый доступ к переводу"""
    return _manager.translate(key, default)

def trf(key: str, **kwargs) -> str:
    """Быстрый доступ к форматированному переводу"""
    return _manager.format(key, **kwargs)

def set_language(language: Language):
    """Установка языка"""
    _manager.set_language(language)

def get_language() -> Language:
    """Получение текущего языка"""
    return _manager.get_language()