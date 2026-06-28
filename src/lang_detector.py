# -*- coding: utf-8 -*-
"""
lang_detector.py — audiobook language detection based on the folder name.

Supported Languages
───────────────────
Non-Latin scripts (unambiguous detection):
  ar  Arabic      — U+0600–U+06FF
  hi  Hindi       — U+0900–U+097F  (Devanagari)
  hy  Armenian    — U+0530–U+058F
  ja  Japanese    — U+3040–U+30FF  (Kana) + CJK
  ko  Korean      — U+AC00–U+D7AF  (Hangul)
  th  Thai        — U+0E00–U+0E7F
  zh  Chinese     — U+4E00–U+9FFF  (CJK without Kana)

Cyrillic scripts:
  ru  Russian     — Cyrillic without specific characters
  uk  Ukrainian   — єїіґ
  be  Belarusian  — ў

Latin scripts (heuristics by characters and words):
  de  German      — äöüß
  fr  French      — àâæçèéêëîïôùûüœ
  es  Spanish     — ñ
  pl  Polish      — ąćęłńóśźż
  cs  Czech/Slovak— áčďéěíňřšťůýž
  ro  Romanian    — ăâîșț
  tr  Turkish     — çğışöü
  fi  Finnish     — åäö
  it  Italian     — àèéìíîòóùú
  en  English     — the/and/of/in/a (stop words)

Transliterated Russian:
  Names with suffixes skiy/aya/niy/vich/ovna/evna and long words → ru

API
───
  detect(folder_name: str) -> str
      Returns the ISO 639-1 language code (e.g., 'ru', 'en', 'de', 'zh', ...).
      Never raises exceptions.

  detect_detailed(folder_name: str) -> DetectResult
      Returns a named tuple with voting details.

Example
───────
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
# Public list of supported languages
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
    "ar", "be", "cs", "de", "en", "es", "fi", "fr",
    "he", "hi", "hy", "it", "ja", "ko", "pl", "ro",
    "ru", "th", "tr", "uk", "zh",
})

# ─────────────────────────────────────────────────────────────────────────────
# Internal constants
# ─────────────────────────────────────────────────────────────────────────────

# Non-Latin scripts determined unambiguously (Rule 0)
_NON_LATIN_SCRIPTS: frozenset[str] = frozenset({"ar", "hi", "hy", "ja", "ko", "th", "zh"})

# Normalization of internal codes → ISO 639-1
_NORMALIZE: dict[str, str] = {
    # Internal pseudo-codes
    "ru/cyrillic": "ru",
    "ru-translit": "ru",
    "en/latin":    "en",
    # ISO codes
    "ru": "ru", "en": "en", "uk": "uk", "be": "be",
    "de": "de", "fr": "fr", "es": "es", "pl": "pl",
    "cs": "cs", "sk": "cs", "it": "it", "ro": "ro",
    "ar": "ar", "zh": "zh", "zh-cn": "zh", "zh-tw": "zh",
    "he": "he", "ja": "ja", "tr": "tr", "fi": "fi",
    "hi": "hi", "hy": "hy", "ko": "ko", "th": "th",
    "pt": "pt", "vi": "vi", "id": "id",
    # langdetect sometimes returns similar Cyrillic languages
    "bg": "ru", "mk": "ru", "sr": "ru",
    # Service codes
    "mixed":     "unknown",
    "unknown":   "unknown",
    "too_short": "unknown",
    "error":     "unknown",
}

# Method weights in voting
_METHOD_WEIGHT: dict[str, int] = {"v1": 1, "v2": 2, "v4": 3}

# ─────────────────────────────────────────────────────────────────────────────
# Unique characters of languages
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

# Distinctive words for language detection
# Do not include ' i ' — Roman numeral trap (Part I, Vol. I)
_LANG_WORD_HINTS: dict[str, list[str]] = {
    "en": ["the ", " of ", " and ", " in ", " a ", "'s "],
    "de": [" der ", " die ", " das ", " ein ", " und "],
    "fr": [" le ", " la ", " les ", " de ", " l'", " d'"],
    "es": [" el ", " la ", " los ", " las ", " de "],
    "it": [" il ", " lo ", " gli ", " della ", " delle "],
}

# ─────────────────────────────────────────────────────────────────────────────
# Transliteration patterns and English stop words
# ─────────────────────────────────────────────────────────────────────────────

# Transliterated Russian patterns.
# Deliberately do NOT include: 'ov', 'ev', 'ich', 'ova', 'eva' — they produce false
# positives on German (Schachnovelle) and Japanese (Takahashi) names.
_RU_TRANSLIT_PATTERNS: list[str] = [
    r"\b(aya|oye|ogo|ego|niy|naya|skiy|skaya|skie|skoe|ikh|yikh)\b",
    r"\b(ovna|evna|vich)\b",
    r"\b(по|из|на|за|до|от|во|со|об|под|над|про|для|без)\b",
]

# Pattern for V2 (a more comprehensive list of suffixes)
_RU_TRANSLIT_RE = re.compile(
    r"\b(aya|skiy|skaya|skie|skoe|niya|niy|ogo|ego|ikh|yikh|evna|ovna|vich"
    r"|glavnoe|rodah|zhizn|noch|voin|mech|krov|zemla|zvezd)\b",
    re.IGNORECASE,
)

_EN_PATTERNS: list[str] = [
    r"\b(the|and|of|in|a|an|to|is|it|at|by|for|on|or|with|from)\b",
    r"\b(this|that|these|those|his|her|their|your|its|who|which|whose|whom|what|where|when|why|how|we|they|our|us|him|them|me|was|were|been|have|has|had|does|did|will|would|should|could|can|about|after|before|into|over|under|out|collection|fiction|science|various|mystery|history|short|story|stories|book|books|volume|vol|part|selected|collected|works|librivox|volunteers|volunteer|audiobook|audiobooks|narrated|read|reading|reader|new|great|little|world|life|woman|time|years|house|home|love|night|tales|black|white|blue|green|dark|light|good|bad|best)\b",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper function
# ─────────────────────────────────────────────────────────────────────────────

def _strip_metadata(text: str) -> str:
    """Removes [...] and (...) — format metadata (kbps, MP3, year, etc.).

    Example:
        'Author - Title [Narrator, 2020, 128kbps, MP3]' → 'Author - Title'
    """
    return re.sub(r"\[.*?\]|\(.*?\)", " ", text).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Detector V1: Unicode ranges
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v1(text: str) -> str:
    """Detects language by the Unicode script of characters in the core text."""
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

    # ja vs zh: Kana is unique to Japanese
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
# Detector V2: hybrid (Unicode + characters + words)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v2(text: str) -> str:
    """Hybrid: non-Latin scripts → Cyrillic → translit → characters → words."""
    core  = _strip_metadata(text)
    lower = core.lower()
    chars = set(lower)

    # — Early exit: unambiguous non-Latin scripts —
    if any("\u0900" <= c <= "\u097F" for c in core): return "hi"
    if any("\u0530" <= c <= "\u058F" for c in core): return "hy"
    if any("\uAC00" <= c <= "\uD7AF" for c in core): return "ko"
    if any("\u0E00" <= c <= "\u0E7F" for c in core): return "th"

    kana = sum(1 for c in core if "\u3040" <= c <= "\u30FF")
    cjk  = sum(1 for c in core if "\u4E00" <= c <= "\u9FFF")
    if kana > 0: return "ja"
    if cjk  > 0: return "zh"
    if any("\u0600" <= c <= "\u06FF" for c in core): return "ar"

    # — Cyrillic —
    cyrillic = sum(1 for c in core if "\u0400" <= c <= "\u04FF")
    latin    = sum(1 for c in core if "A" <= c.upper() <= "Z")

    if cyrillic > 3:
        if "ў" in chars:        return "be"
        if chars & set("єїіґ"): return "uk"
        return "ru"

    # — Translit —
    if latin > 0 and _RU_TRANSLIT_RE.search(lower):
        return "ru-translit"

    # — Unique characters of Latin languages —
    if latin > 0:
        for lang, hint_chars in _LANG_CHAR_HINTS.items():
            if chars & hint_chars:
                return lang

    # — Keywords —
    for lang, words in _LANG_WORD_HINTS.items():
        if any(w in lower for w in words):
            return lang

    # — Fallback —
    if latin > cyrillic: return "en"
    if cyrillic == 0 and latin == 0: return "unknown"
    return "mixed"


# ─────────────────────────────────────────────────────────────────────────────
# Detector V4: patterns + translit
# ─────────────────────────────────────────────────────────────────────────────

def _detect_v4(text: str) -> str:
    """Detects language using regular expressions and word length heuristics."""
    core      = _strip_metadata(text)
    lower     = core.lower()
    full_lower = text.lower()

    # — Early exit: non-Latin scripts —
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

    # — Cyrillic —
    cyrillic = sum(1 for c in core if "\u0400" <= c <= "\u04FF")
    if cyrillic > 3:
        if "ў" in lower:                    return "be"
        if any(c in "єїіґ" for c in lower): return "uk"
        return "ru"

    latin = sum(1 for c in core if "A" <= c.upper() <= "Z")
    if latin == 0:
        return "unknown"

    # 1. Special language characters (in FULL text — the character might be in the narrator's name
    #    inside brackets, e.g., "Büttner" → ü → de)
    full_chars = set(full_lower)
    for lang, hint_chars in _LANG_CHAR_HINTS.items():
        if lang in ("uk", "be"):
            continue
        if full_chars & hint_chars:
            return lang

    # 2. Translit
    for pat in _RU_TRANSLIT_PATTERNS:
        if re.search(pat, lower, re.IGNORECASE):
            return "ru-translit"

    # 3. English stop words
    if any(re.search(p, lower) for p in _EN_PATTERNS):
        return "en"

    # 4. Heuristic: long words without markers → likely translit
    words = re.findall(r"[a-zA-Z]+", core)
    if words and sum(len(w) for w in words) / len(words) > 6:
        return "ru-translit"

    return "en"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class DetectResult(NamedTuple):
    """Detailed language detection result."""
    lang: str
    """ISO 639-1 language code or 'unknown'."""
    rule: str
    """The rule that determined the result: 'script-rule', 'translit-rule',
    'cyrillic-rule', or a numeric string like 'vote:N'."""
    v1: str
    """Result from V1 (Unicode ranges)."""
    v2: str
    """Result from V2 (hybrid)."""
    v4: str
    """Result from V4 (patterns + heuristics)."""


def detect_detailed(folder_name: str) -> DetectResult:
    """Detects language and returns a complete report of the decision made.

    Args:
        folder_name: The audiobook folder name (supports any Unicode scripts).

    Returns:
        :class:`DetectResult` — a named tuple with lang, rule, v1, v2, v4.

    Never raises exceptions.
    """
    try:
        return _detect_detailed_impl(folder_name)
    except Exception:  # pragma: no cover — safety net for unexpected data
        return DetectResult(lang="unknown", rule="error", v1="unknown", v2="unknown", v4="unknown")


def detect(folder_name: str) -> str:
    """Detects audiobook language from the folder name.

    Args:
        folder_name: Folder name (e.g., 'Tolstoy - War and Peace [2008, MP3]').

    Returns:
        ISO 639-1 language code (``'ru'``, ``'en'``, ``'de'``, ...) or
        ``'unknown'`` if detection failed.

    Never raises exceptions.
    """
    return detect_detailed(folder_name).lang


def _fix_encoding(text: str) -> str:
    """Correct text encoding issues (e.g., CP1251 read as Latin-1)"""
    if not text or not isinstance(text, str):
        return text
        
    try:
        if any(128 <= ord(c) <= 255 for c in text):
            fixed = text.encode('latin-1').decode('cp1251')
            if any(1040 <= ord(c) <= 1103 for c in fixed): # A-я in Unicode
                # Ensure no single word contains both Latin and Cyrillic characters,
                # which would indicate a false correction on accented Latin characters
                words = re.findall(r'[A-Za-z\u0400-\u04FF\u0401\u0451]+', fixed)
                has_mixed = False
                for w in words:
                    has_latin = any(('a' <= c <= 'z') or ('A' <= c <= 'Z') for c in w)
                    has_cyrillic = any('\u0400' <= c <= '\u04FF' or c in '\u0401\u0451' for c in w)
                    if has_latin and has_cyrillic:
                        has_mixed = True
                        break
                if not has_mixed:
                    return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
        
    return text


def _detect_detailed_impl(text: str) -> DetectResult:
    """Internal implementation without try/except."""
    text = _fix_encoding(text)
    r1 = _detect_v1(text)
    r2 = _detect_v2(text)
    r4 = _detect_v4(text)


    n2 = _NORMALIZE.get(r2, r2)
    n4 = _NORMALIZE.get(r4, r4)

    has_cyrillic = any("\u0400" <= c <= "\u04FF" for c in text)

    # ── Rule 0: both V2 and V4 yielded the same non-Latin script ──
    if n2 in _NON_LATIN_SCRIPTS and n2 == n4:
        return DetectResult(lang=n2, rule="script-rule", v1=r1, v2=r2, v4=r4)

    # ── Rule 0b: V2 is confident, V1 agrees ──
    n1 = _NORMALIZE.get(r1, r1)
    if n2 in _NON_LATIN_SCRIPTS and n1 == n2:
        return DetectResult(lang=n2, rule="script-rule", v1=r1, v2=r2, v4=r4)

    # ── Rule 1: explicit translit (V4 specializes) ──
    if r4 == "ru-translit":
        return DetectResult(lang="ru", rule="translit-rule", v1=r1, v2=r2, v4=r4)

    # ── Rule 2: Cyrillic + V4 is confident in ru/uk/be ──
    if has_cyrillic and n4 in ("ru", "uk", "be"):
        return DetectResult(lang=n4, rule="cyrillic-rule", v1=r1, v2=r2, v4=r4)

    # ── Rule 2b: V4 found an unambiguous de/fr character, no Cyrillic present ──
    # For example: "Büttner" → ü → V4='de', but V2='en' (ü inside brackets, core without ü).
    # V4 specifically checks the FULL text for de/fr, so we trust it.
    if not has_cyrillic and n4 in ("de", "fr"):
        return DetectResult(lang=n4, rule="char-rule", v1=r1, v2=r2, v4=r4)

    # ── Rule 3: weighted voting V1+V2+V4 ──
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
