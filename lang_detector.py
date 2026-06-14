# -*- coding: utf-8 -*-
"""
lang_detector.py — определение языка аудиокниги по имени папки.

Поддерживаемые языки
────────────────────
Нелатинские скрипты (однозначное определение):
  ar  Arabic      — U+0600–U+06FF
  hi  Hindi       — U+0900–U+097F  (Devanagari)
  hy  Armenian    — U+0530–U+058F
  ja  Japanese    — U+3040–U+30FF  (кана) + CJK
  ko  Korean      — U+AC00–U+D7AF  (Hangul)
  th  Thai        — U+0E00–U+0E7F
  zh  Chinese     — U+4E00–U+9FFF  (CJK без кана)

Кириллические скрипты:
  ru  Russian     — кириллица без специфичных букв
  uk  Ukrainian   — єїіґ
  be  Belarusian  — ў

Латинские скрипты (эвристика по символам и словам):
  de  German      — äöüß
  fr  French      — àâæçèéêëîïôùûüœ
  es  Spanish     — ñ
  pl  Polish      — ąćęłńóśźż
  cs  Czech/Slovak— áčďéěíňřšťůýž
  ro  Romanian    — ăâîșț
  tr  Turkish     — çğışöü
  fi  Finnish     — åäö
  it  Italian     — àèéìíîòóùú
  en  English     — the/and/of/in/a (стоп-слова)

Транслитерированный русский:
  Имена с суффиксами skiy/aya/niy/vich/ovna/evna и длинными словами → ru

API
───
  detect(folder_name: str) -> str
      Возвращает ISO 639-1 код языка (например 'ru', 'en', 'de', 'zh', ...).
      Никогда не бросает исключений.

  detect_detailed(folder_name: str) -> DetectResult
      Возвращает именованный кортеж с деталями голосования.

Пример
──────
  >>> from lang_detector import detect
  >>> detect("Лев Толстой - Война и мир [Александр Клюквин, 2008, 192kbps, MP3]")
  'ru'
  >>> detect("夏目漱石 - こころ [朗読: 山田太郎, 2016, 96kbps, M4B]")
  'ja'
"""
from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple

__all__ = ["detect", "detect_detailed", "DetectResult", "SUPPORTED_LANGUAGES"]

# ─────────────────────────────────────────────────────────────────────────────
# Публичный список поддерживаемых языков
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
    "ar", "be", "cs", "de", "en", "es", "fi", "fr",
    "he", "hi", "hy", "it", "ja", "ko", "pl", "ro",
    "ru", "th", "tr", "uk", "zh",
})

# ─────────────────────────────────────────────────────────────────────────────
# Внутренние константы
# ─────────────────────────────────────────────────────────────────────────────

# Нелатинские скрипты, которые определяются однозначно (Rule 0)
_NON_LATIN_SCRIPTS: frozenset[str] = frozenset({"ar", "hi", "hy", "ja", "ko", "th", "zh"})

# Нормализация внутренних кодов → ISO 639-1
_NORMALIZE: dict[str, str] = {
    # Внутренние псевдокоды
    "ru/cyrillic": "ru",
    "ru-translit": "ru",
    "en/latin":    "en",
    # ISO коды
    "ru": "ru", "en": "en", "uk": "uk", "be": "be",
    "de": "de", "fr": "fr", "es": "es", "pl": "pl",
    "cs": "cs", "sk": "cs", "it": "it", "ro": "ro",
    "ar": "ar", "zh": "zh", "zh-cn": "zh", "zh-tw": "zh",
    "he": "he", "ja": "ja", "tr": "tr", "fi": "fi",
    "hi": "hi", "hy": "hy", "ko": "ko", "th": "th",
    "pt": "pt", "vi": "vi", "id": "id",
    # langdetect иногда возвращает близкие кириллические языки
    "bg": "ru", "mk": "ru", "sr": "ru",
    # Служебные
    "mixed":     "unknown",
    "unknown":   "unknown",
    "too_short": "unknown",
    "error":     "unknown",
}

# Веса методов в голосовании
_METHOD_WEIGHT: dict[str, int] = {"v1": 1, "v2": 2, "v4": 3}

# ─────────────────────────────────────────────────────────────────────────────
# Уникальные символы языков
# ─────────────────────────────────────────────────────────────────────────────

_LANG_CHAR_HINTS: dict[str, set[str]] = {
    "uk": set("єїіґ"),
    "be": set("ўі"),
    "de": set("äöüß"),
    "fr": set("àâæçèéêëîïôùûüœ"),
    "es": set("ñ"),
    "pl": set("ąćęłńóśźż"),
    "cs": set("áčďéěíňřšťůýž"),
    "ro": set("ăâîșț"),
    "tr": set("çğışöü"),
    "fi": set("åäö"),
    "it": set("àèéìíîòóùú"),
}

# Характерные слова для определения языка
# Не включаем ' i ' — Roman numeral ловушка (Part I, Vol. I)
_LANG_WORD_HINTS: dict[str, list[str]] = {
    "en": ["the ", " of ", " and ", " in ", " a ", "'s "],
    "de": [" der ", " die ", " das ", " ein ", " und "],
    "fr": [" le ", " la ", " les ", " de ", " l'", " d'"],
    "es": [" el ", " la ", " los ", " las ", " de "],
    "it": [" il ", " lo ", " gli ", " della ", " delle "],
}

# ─────────────────────────────────────────────────────────────────────────────
# Паттерны транслита и английских стоп-слов
# ─────────────────────────────────────────────────────────────────────────────

# Паттерны транслитерированного русского.
# Намеренно НЕ включаем: 'ov', 'ev', 'ich', 'ova', 'eva' — дают ложные
# срабатывания на немецких (Schachnovelle) и японских (Takahashi) именах.
_RU_TRANSLIT_PATTERNS: list[str] = [
    r"\b(aya|oye|ogo|ego|niy|naya|skiy|skaya|skie|skoe|ikh|yikh)\b",
    r"\b(ovna|evna|vich)\b",
    r"\b(по|из|на|за|до|от|во|со|об|под|над|про|для|без)\b",
]

# Паттерн для V2 (более полный список суффиксов)
_RU_TRANSLIT_RE = re.compile(
    r"\b(aya|skiy|skaya|skie|skoe|niya|niy|ogo|ego|ikh|yikh|evna|ovna|vich"
    r"|glavnoe|rodah|zhizn|noch|voin|mech|krov|zemla|zvezd)\b",
    re.IGNORECASE,
)

_EN_PATTERNS: list[str] = [
    r"\b(the|and|of|in|a|an|to|is|it|at|by|for|on|or|with|from)\b",
]


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательная функция
# ─────────────────────────────────────────────────────────────────────────────

def _strip_metadata(text: str) -> str:
    """Убирает [...] и (...) — метаданные формата (kbps, MP3, год и т.п.).

    Пример:
        'Автор - Название [Чтец, 2020, 128kbps, MP3]' → 'Автор - Название'
    """
    return re.sub(r"\[.*?\]|\(.*?\)", " ", text).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Детектор V1: Unicode-диапазоны
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v1(text: str) -> str:
    """Определяет язык по Unicode-скрипту символов в core-части текста."""
    core = _strip_metadata(text)

    cyrillic   = sum(1 for c in core if "\u0400" <= c <= "\u04FF")
    latin      = sum(1 for c in core if "A" <= c.upper() <= "Z")
    arabic     = sum(1 for c in core if "\u0600" <= c <= "\u06FF")
    cjk        = sum(1 for c in core if "\u4E00" <= c <= "\u9FFF")
    hebrew     = sum(1 for c in core if "\u0590" <= c <= "\u05FF")
    kana       = sum(1 for c in core if "\u3040" <= c <= "\u30FF")
    devanagari = sum(1 for c in core if "\u0900" <= c <= "\u097F")
    armenian   = sum(1 for c in core if "\u0530" <= c <= "\u058F")
    hangul     = sum(1 for c in core if "\uAC00" <= c <= "\uD7AF")
    thai       = sum(1 for c in core if "\u0E00" <= c <= "\u0E7F")

    # ja vs zh: кана уникальна для японского
    japanese = kana + (cjk if kana > 0 else 0)
    chinese  = cjk if kana == 0 else 0

    scores = {
        "ru/cyrillic": cyrillic,
        "en/latin":    latin,
        "ar":          arabic,
        "zh":          chinese,
        "he":          hebrew,
        "ja":          japanese,
        "hi":          devanagari,
        "hy":          armenian,
        "ko":          hangul,
        "th":          thai,
    }
    best, best_score = max(scores.items(), key=lambda x: x[1])
    total = sum(scores.values())
    if total == 0:
        return "unknown"
    if best_score / total < 0.3:
        return "mixed"
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Детектор V2: гибрид (Unicode + символы + слова)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v2(text: str) -> str:
    """Гибрид: нелатинские скрипты → кириллица → транслит → символы → слова."""
    core  = _strip_metadata(text)
    lower = core.lower()
    chars = set(lower)

    # — Ранний выход: однозначные нелатинские скрипты —
    if any("\u0900" <= c <= "\u097F" for c in core): return "hi"
    if any("\u0530" <= c <= "\u058F" for c in core): return "hy"
    if any("\uAC00" <= c <= "\uD7AF" for c in core): return "ko"
    if any("\u0E00" <= c <= "\u0E7F" for c in core): return "th"

    kana = sum(1 for c in core if "\u3040" <= c <= "\u30FF")
    cjk  = sum(1 for c in core if "\u4E00" <= c <= "\u9FFF")
    if kana > 0: return "ja"
    if cjk  > 0: return "zh"
    if any("\u0600" <= c <= "\u06FF" for c in core): return "ar"

    # — Кириллица —
    cyrillic = sum(1 for c in core if "\u0400" <= c <= "\u04FF")
    latin    = sum(1 for c in core if "A" <= c.upper() <= "Z")

    if cyrillic > 3:
        if chars & set("єїіґ"): return "uk"
        if "ў" in chars:        return "be"
        return "ru"

    # — Транслит —
    if latin > 0 and _RU_TRANSLIT_RE.search(lower):
        return "ru-translit"

    # — Уникальные символы Latin-языков —
    if latin > 0:
        for lang, hint_chars in _LANG_CHAR_HINTS.items():
            if chars & hint_chars:
                return lang

    # — Ключевые слова —
    for lang, words in _LANG_WORD_HINTS.items():
        if any(w in lower for w in words):
            return lang

    # — Fallback —
    if latin > cyrillic: return "en"
    if cyrillic == 0 and latin == 0: return "unknown"
    return "mixed"


# ─────────────────────────────────────────────────────────────────────────────
# Детектор V4: паттерны + транслит
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v4(text: str) -> str:
    """Определяет язык через регулярные выражения и эвристику длины слов."""
    core      = _strip_metadata(text)
    lower     = core.lower()
    full_lower = text.lower()

    # — Ранний выход: нелатинские скрипты —
    if any("\u0900" <= c <= "\u097F" for c in core): return "hi"
    if any("\u0530" <= c <= "\u058F" for c in core): return "hy"
    if any("\uAC00" <= c <= "\uD7AF" for c in core): return "ko"
    if any("\u0E00" <= c <= "\u0E7F" for c in core): return "th"

    kana   = sum(1 for c in core if "\u3040" <= c <= "\u30FF")
    cjk    = sum(1 for c in core if "\u4E00" <= c <= "\u9FFF")
    arabic = sum(1 for c in core if "\u0600" <= c <= "\u06FF")
    if kana   > 0:  return "ja"
    if cjk    > 0:  return "zh"
    if arabic > 2:  return "ar"

    # — Кириллица —
    cyrillic = sum(1 for c in core if "\u0400" <= c <= "\u04FF")
    if cyrillic > 3:
        if any(c in "єїіґ" for c in lower): return "uk"
        if "ў" in lower:                    return "be"
        return "ru"

    latin = sum(1 for c in core if "A" <= c.upper() <= "Z")
    if latin == 0:
        return "unknown"

    # 1. Спецсимволы языков (в ПОЛНОМ тексте — символ может быть в имени чтеца
    #    внутри скобок, например "Büttner" → ü → de)
    if set("äöüß") & set(full_lower):
        return "de"
    if set("àâæçèéêëîïôùûüœ") & set(full_lower):
        return "fr"

    # 2. Транслит
    for pat in _RU_TRANSLIT_PATTERNS:
        if re.search(pat, lower, re.IGNORECASE):
            return "ru-translit"

    # 3. Английские стоп-слова
    if any(re.search(p, lower) for p in _EN_PATTERNS):
        return "en"

    # 4. Эвристика: длинные слова без маркеров → вероятно транслит
    words = re.findall(r"[a-zA-Z]+", core)
    if words and sum(len(w) for w in words) / len(words) > 6:
        return "ru-translit"

    return "en"


# ─────────────────────────────────────────────────────────────────────────────
# Публичный API
# ─────────────────────────────────────────────────────────────────────────────

class DetectResult(NamedTuple):
    """Детальный результат определения языка."""
    lang: str
    """ISO 639-1 код языка или 'unknown'."""
    rule: str
    """Правило, которое дало результат: 'script-rule', 'translit-rule',
    'cyrillic-rule', или числовая строка вида 'vote:N'."""
    v1: str
    """Результат V1 (Unicode-диапазоны)."""
    v2: str
    """Результат V2 (гибрид)."""
    v4: str
    """Результат V4 (паттерны + эвристика)."""


def detect_detailed(folder_name: str) -> DetectResult:
    """Определяет язык и возвращает полный отчёт о принятом решении.

    Args:
        folder_name: Имя папки аудиокниги (поддерживает любые Unicode-скрипты).

    Returns:
        :class:`DetectResult` — именованный кортеж с lang, rule, v1, v2, v4.

    Никогда не бросает исключений.
    """
    try:
        return _detect_detailed_impl(folder_name)
    except Exception:  # pragma: no cover — страховка на случай неожиданных данных
        return DetectResult(lang="unknown", rule="error", v1="unknown", v2="unknown", v4="unknown")


def detect(folder_name: str) -> str:
    """Определяет язык аудиокниги по имени папки.

    Args:
        folder_name: Имя папки (например 'Толстой - Война и мир [2008, MP3]').

    Returns:
        ISO 639-1 код языка (``'ru'``, ``'en'``, ``'de'``, ...) или
        ``'unknown'`` если определить не удалось.

    Никогда не бросает исключений.
    """
    return detect_detailed(folder_name).lang


def _detect_detailed_impl(text: str) -> DetectResult:
    """Внутренняя реализация без try/except."""
    r1 = _detect_v1(text)
    r2 = _detect_v2(text)
    r4 = _detect_v4(text)

    n2 = _NORMALIZE.get(r2, r2)
    n4 = _NORMALIZE.get(r4, r4)

    has_cyrillic = any("\u0400" <= c <= "\u04FF" for c in text)

    # ── Правило 0: оба V2 и V4 дали один нелатинский скрипт ──
    if n2 in _NON_LATIN_SCRIPTS and n2 == n4:
        return DetectResult(lang=n2, rule="script-rule", v1=r1, v2=r2, v4=r4)

    # ── Правило 0b: V2 уверен, V1 согласен ──
    n1 = _NORMALIZE.get(r1, r1)
    if n2 in _NON_LATIN_SCRIPTS and n1 == n2:
        return DetectResult(lang=n2, rule="script-rule", v1=r1, v2=r2, v4=r4)

    # ── Правило 1: явный транслит (V4 специализируется) ──
    if r4 == "ru-translit":
        return DetectResult(lang="ru", rule="translit-rule", v1=r1, v2=r2, v4=r4)

    # ── Правило 2: кириллица + V4 уверен в ru/uk/be ──
    if has_cyrillic and n4 in ("ru", "uk", "be"):
        return DetectResult(lang=n4, rule="cyrillic-rule", v1=r1, v2=r2, v4=r4)

    # ── Правило 2b: V4 нашёл однозначный символ de/fr, кириллицы нет ──
    # Например: "Büttner" → ü → V4='de', но V2='en' (ü в скобках, core без ü).
    # V4 специально проверяет ПОЛНЫЙ текст для de/fr, поэтому доверяем ему.
    if not has_cyrillic and n4 in ("de", "fr"):
        return DetectResult(lang=n4, rule="char-rule", v1=r1, v2=r2, v4=r4)

    # ── Правило 3: взвешенное голосование V1+V2+V4 ──
    votes: Counter[str] = Counter()
    for key, raw, weight in (("v1", r1, 1), ("v2", r2, 2), ("v4", r4, 3)):
        norm = _NORMALIZE.get(raw, raw)
        if norm in ("unknown", "mixed", "error", "too_short"):
            continue
        votes[norm] += weight

    if votes:
        winner, score = votes.most_common(1)[0]
    else:
        winner, score = "unknown", 0

    return DetectResult(lang=winner, rule=f"vote:{score}", v1=r1, v2=r2, v4=r4)
