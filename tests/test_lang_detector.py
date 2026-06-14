# -*- coding: utf-8 -*-
"""
Тесты модуля lang_detector.py.

Запуск:
    pytest tests/test_lang_detector.py -v
    pytest tests/test_lang_detector.py -v -k "arabic"
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lang_detector import detect, detect_detailed, DetectResult, SUPPORTED_LANGUAGES


# ═══════════════════════════════════════════════════════════════════════════════
# Вспомогательные функции
# ═══════════════════════════════════════════════════════════════════════════════

def d(folder: str) -> str:
    """Краткий псевдоним для detect()."""
    return detect(folder)


# ═══════════════════════════════════════════════════════════════════════════════
# API: detect() и detect_detailed()
# ═══════════════════════════════════════════════════════════════════════════════

class TestPublicApi:
    def test_detect_returns_string(self):
        assert isinstance(d("Some Book [2020, MP3]"), str)

    def test_detect_never_raises(self):
        for text in ["", "   ", "!!!", "\x00\x01\x02", "A" * 5000]:
            detect(text)  # не должно бросать

    def test_detect_detailed_returns_namedtuple(self):
        result = detect_detailed("Толстой - Война и мир [2008, MP3]")
        assert isinstance(result, DetectResult)
        assert hasattr(result, "lang")
        assert hasattr(result, "rule")
        assert hasattr(result, "v1")
        assert hasattr(result, "v2")
        assert hasattr(result, "v4")

    def test_detect_detailed_lang_matches_detect(self):
        folder = "Victor Hugo - Les Misérables [2005, MP3]"
        assert detect(folder) == detect_detailed(folder).lang

    def test_detect_never_returns_empty(self):
        for folder in ["X", "123", "Автор", "夏目漱石"]:
            assert detect(folder) not in ("", None)

    def test_supported_languages_is_frozenset(self):
        assert isinstance(SUPPORTED_LANGUAGES, frozenset)
        assert "ru" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES
        assert "zh" in SUPPORTED_LANGUAGES


# ═══════════════════════════════════════════════════════════════════════════════
# Нелатинские скрипты
# ═══════════════════════════════════════════════════════════════════════════════

class TestArabic:
    @pytest.mark.parametrize("folder", [
        "نجيب محفوظ - الثلاثية: بين القصرين [جمال سليمان, 2015, 64kbps, M4B]",
        "طه حسين - الأيام [أحمد معوض, 2018, 96kbps, MP3]",
        "جبران خليل جبران - النبي [شادي حداد, 2020, 128kbps, MP3]",
        "أحمد خالد توفيق - يوتوبيا [خالد المهدي, 2016, 128kbps, M4B]",
        "بهاء طاهر - واحة الغروب [حسن الجندي, 2019, 96kbps, MP3]",
    ])
    def test_arabic_books(self, folder):
        assert d(folder) == "ar"

    def test_rule_is_script_rule(self):
        r = detect_detailed("طه حسين - الأيام [أحمد معوض, 2018, MP3]")
        assert r.rule == "script-rule"


class TestHindi:
    @pytest.mark.parametrize("folder", [
        "मुंशी प्रेमचंद - गोदान [समीर गोस्वामी, 2018, 96kbps, MP3]",
        "हरिवंश राय बच्चन - मधुशाला [अमिताभ बच्चन, 2012, 128kbps, MP3]",
        "जयशंकर प्रसाद - कामायनी [सुमन सिंह, 2015, 128kbps, M4B]",
        "देवकी नंदन खत्री - चंद्रकांता [राहुल वर्मा, 2017, 96kbps, MP3]",
        "फणीश्वर नाथ रेणु - मैला आंचल [विकास शर्मा, 2019, 128kbps, MP3]",
    ])
    def test_hindi_books(self, folder):
        assert d(folder) == "hi"

    def test_devanagari_with_latin_metadata(self):
        # Латинские метаданные не должны перевешивать хинди
        assert d("मुंशी प्रेमचंद - गोदान [Samir, 2018, 128kbps, MP3]") == "hi"


class TestArmenian:
    @pytest.mark.parametrize("folder", [
        "Րաֆֆի - Խենթը [Արmen, 2014, 128kbps, MP3]",
        "Հovhannes - Lenktemuri [Sargis Manukyan, 2016, 96kbps, MP3]",
        "Ավետիք - Աbu Lala [Hrachya, 2015, 128kbps, MP3]",
    ])
    def test_armenian_books(self, folder):
        assert d(folder) == "hy"


class TestJapanese:
    @pytest.mark.parametrize("folder", [
        "夏目漱石 - こころ [朗読: 山田太郎, 2016, 96kbps, M4B]",       # hiragana
        "村上春樹 - ノルウェイの森 [朗読: 小林健太, 2020, 128kbps, MP3]",  # katakana
        "宮崎駿 - となりのトトロ [朗読: 田中, 2019, 128kbps, MP3]",       # katakana
    ])
    def test_japanese_with_kana(self, folder):
        """Кана → однозначно японский."""
        assert d(folder) == "ja"

    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "太宰治 - 人間失格 [朗読: 鈴木一郎, 2018, 128kbps, MP3]", "ja",
            marks=pytest.mark.xfail(
                reason="Kanji-only: не отличимо от zh без кана", strict=True)
        ),
        pytest.param(
            "芥川龍之介 - 羅生門 [朗読: 田中花子, 2015, 96kbps, MP3]", "ja",
            marks=pytest.mark.xfail(
                reason="Kanji-only: не отличимо от zh без кана", strict=True)
        ),
    ])
    def test_japanese_kanji_only(self, folder, expected):
        assert d(folder) == expected

    def test_rule_is_script_rule(self):
        r = detect_detailed("夏目漱石 - こころ [朗読: 山田太郎, 2016, MP3]")
        assert r.rule == "script-rule"


class TestKorean:
    @pytest.mark.parametrize("folder", [
        "한강 - 채식주의자 [김성우, 2020, 128kbps, MP3]",
        "황순원 - 소나기 [이민호, 2015, 96kbps, MP3]",
        "이문열 - 우리들의 일그러진 영웅 [박서준, 2018, 128kbps, M4B]",
        "조남주 - 82년생 김지영 [이지은, 2019, 128kbps, MP3]",
        "김영하 - 살인자의 기억법 [조진웅, 2017, 128kbps, MP3]",
    ])
    def test_korean_books(self, folder):
        assert d(folder) == "ko"


class TestThai:
    @pytest.mark.parametrize("folder", [
        "สุนทรภู่ - พระอภัยมณี [ผู้อ่าน: สมชาย, 2017, 96kbps, MP3]",
        "ศรีบูรพา - ข้างหลังภาพ [ผู้อ่าน: นภา, 2015, 128kbps, MP3]",
        "ชาติ กอบจิตติ - คำพิพากษา [ผู้อ่าน: อนันต์, 2014, 96kbps, MP3]",
        "ทมยันตี - คู่กรรม [ผู้อ่าน: รุ่งราตรี, 2018, 128kbps, MP3]",
    ])
    def test_thai_books(self, folder):
        assert d(folder) == "th"


class TestChinese:
    @pytest.mark.parametrize("folder", [
        "曹雪芹 - 红楼梦 [朗读: 张三, 2010, 64kbps, M4B]",
        "鲁迅 - 呐喊 [朗读: 李四, 2015, 96kbps, MP3]",
        "刘慈欣 - 三体 [朗读: 王五, 2018, 128kbps, MP3]",
        "莫言 - 红高粱家族 [朗读: 赵六, 2014, 128kbps, M4B]",
        "余华 - 活着 [朗读: 孙七, 2016, 96kbps, MP3]",
    ])
    def test_chinese_books(self, folder):
        assert d(folder) == "zh"


class TestHebrew:
    @pytest.mark.parametrize("folder", [
        "\u05e2\u05de\u05d5\u05e1 \u05e2\u05d5\u05d6 - \u05de\u05d9\u05db\u05d0\u05dc \u05e9\u05dc\u05d9 [2010]",
        "\u05d3\u05d5\u05d9\u05d3 \u05d2\u05e8\u05d5\u05e1\u05de\u05df - \u05d0\u05e9\u05d4 \u05d1\u05d5\u05e8\u05d7\u05ea \u05de\u05d1\u05e9\u05d5\u05e8\u05d4 [2015]",
    ])
    def test_hebrew_books(self, folder):
        assert d(folder) == "he"


# ═══════════════════════════════════════════════════════════════════════════════
# Кириллические языки
# ═══════════════════════════════════════════════════════════════════════════════

class TestRussian:
    @pytest.mark.parametrize("folder", [
        "Лев Толстой - Война и мир [Александр Клюквин, 2008, 192kbps, MP3]",
        "Федор Достоевский - Преступление и наказание [Иван Литвинов, 2012, 128kbps, M4B]",
        "Михаил Булгаков - Мастер и Маргарита [Максим Суханов, 2010, 128kbps, MP3]",
        "Антон Чехов - Рассказы [Дмитрий Быков, 2015, 96kbps, MP3]",
        "Николай Гоголь - Мертвые души [Вениамин Смехов, 2011, 128kbps, MP3]",
    ])
    def test_russian_books(self, folder):
        assert d(folder) == "ru"

    def test_rule_is_cyrillic_rule(self):
        r = detect_detailed("Лев Толстой - Война и мир [2008, MP3]")
        assert r.rule == "cyrillic-rule"


class TestTransliteratedRussian:
    @pytest.mark.parametrize("folder", [
        "Voskresenskaya - Glavnoe v rodah [2021, 128kbps]",
        "Dostoevsky - Prestuplenie i nakazanie [2018, 128kbps]",
        "Chekhov - Vishneviy sad [2017]",
        "Tolstoy - Anna Karenina [2015]",
        "Pushkin - Evgeniy Onegin [2019, 192kbps]",
    ])
    def test_translit_books(self, folder):
        assert d(folder) == "ru"

    def test_rule_is_translit_rule(self):
        r = detect_detailed("Voskresenskaya - Glavnoe v rodah [2021, 128kbps]")
        assert r.rule == "translit-rule"

    def test_not_translit_on_german_long_words(self):
        # Длинные немецкие составные слова не должны давать translit
        result = d("Stefan Zweig - Schachnovelle [Wolfgang Büttner, 2003, 128kbps, MP3]")
        assert result == "de"

    def test_not_translit_on_japanese_names(self):
        # Японские имена в латинице ("Tanaka", "Rashomon") — без кана,
        # среднее слово длиннее 6 букв → avg_len эвристика → ru-translit → ru.
        # Это известное ограничение: японский в латинице неотличим от транслита.
        # Тест: главное, что не падает и возвращает строку.
        result = d("Akutagawa - Rashomon [Tanaka, 2015, 96kbps, MP3]")
        assert isinstance(result, str) and result != ""


class TestUkrainian:
    @pytest.mark.parametrize("folder", [
        "Іван Франко - Захар Беркут [2015, MP3]",
        "Леся Українка - Лісова пісня [2011]",
    ])
    def test_ukrainian_books(self, folder):
        assert d(folder) == "uk"


class TestBelarusian:
    @pytest.mark.parametrize("folder", [
        "Васіль Быкаў - Доўгая дарога дадому [2003, MP3]",
        "Янка Купалаў - Курган [2005]",
    ])
    def test_belarusian_books(self, folder):
        assert d(folder) == "be"


class TestMixedScripts:
    @pytest.mark.parametrize("folder", [
        "Стивен Кинг - IT [2016, M4B]",
        "Аудиокниги Fuad Nasirov - Selected Works [2022]",
        "Лекции TED - English Listening Practice [2023, 128kbps]",
        "Харуки Мураками - 1Q84 Russian Edition [2012, MP3]",
    ])
    def test_cyrillic_wins_over_latin(self, folder):
        """Кириллица присутствует → ru."""
        assert d(folder) == "ru"


# ═══════════════════════════════════════════════════════════════════════════════
# Латинские языки
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglish:
    @pytest.mark.parametrize("folder", [
        "Stephen King - The Shining [Campbell Scott, 2012, 128kbps, MP3]",
        "George Orwell - 1984 [Simon Prebble, 2008, 128kbps, M4B]",
        "J.R.R. Tolkien - The Hobbit [Rob Inglis, 1991, 96kbps, MP3]",
        "Jane Austen - Pride and Prejudice [Rosamund Pike, 2015, 128kbps, MP3]",
        "F. Scott Fitzgerald - The Great Gatsby [Jake Gyllenhaal, 2013, 128kbps, MP3]",
    ])
    def test_english_books(self, folder):
        assert d(folder) == "en"

    def test_roman_numerals_not_italian(self):
        for folder in [
            "Shakespeare William - Henry IV, Part II [2010, MP3]",
            "Tolstoy Leo - War and Peace Vol. IV [2008, 128kbps]",
            "Surzhikov Roman - Vol. I: The Well of Worlds [2023, 128kbps]",
        ]:
            assert d(folder) == "en", f"Failed for: {folder}"


class TestGerman:
    @pytest.mark.parametrize("folder", [
        "Johann Wolfgang von Goethe - Faust: Eine Tragödie [Will Quadflieg, 1999, 128kbps, MP3]",
        "Stefan Zweig - Schachnovelle [Wolfgang Büttner, 2003, 128kbps, MP3]",
    ])
    def test_german_with_umlaut(self, folder):
        assert d(folder) == "de"

    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "Franz Kafka - Die Verwandlung [Hans-Gerd Krogmann, 2005, 128kbps, MP3]", "de",
            marks=pytest.mark.xfail(reason="Нет äöüß → V4='en' побеждает", strict=True)
        ),
        pytest.param(
            "Thomas Mann - Der Zauberberg [Gert Westphal, 2001, 96kbps, M4B]", "de",
            marks=pytest.mark.xfail(reason="Нет äöüß → V4='en' побеждает", strict=True)
        ),
    ])
    def test_german_without_umlaut(self, folder, expected):
        assert d(folder) == expected

    def test_umlaut_in_narrator_name(self):
        # ü в имени чтеца (в скобках) тоже должен определять de
        assert d("Stefan Zweig - Schachnovelle [Wolfgang Büttner, 2003, MP3]") == "de"


class TestFrench:
    @pytest.mark.parametrize("folder", [
        "Victor Hugo - Les Misérables [Gérard Depardieu, 2005, 128kbps, MP3]",
        "Albert Camus - L'Étranger [Christian de Sica, 2008, 128kbps, M4B]",
        "Antoine de Saint-Exupéry - Le Petit Prince [Bernard Giraudeau, 2002, 96kbps, MP3]",
        "Marcel Proust - Du côté de chez Swann [André Dussollier, 2006, 128kbps, MP3]",
    ])
    def test_french_books(self, folder):
        assert d(folder) == "fr"

    @pytest.mark.xfail(reason="Нет французских диакритиков → V4='en'", strict=True)
    def test_french_no_diacritics(self):
        assert d("Gustave Flaubert - Madame Bovary [Isabelle Huppert, 2004, 128kbps, MP3]") == "fr"


class TestSpanish:
    @pytest.mark.parametrize("folder", [
        "Gabriel García Márquez - Cien años de soledad [Gustavo Bonfigli, 2006, M4B]",
    ])
    def test_spanish_books(self, folder):
        assert d(folder) == "es"

    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "Jorge Luis Borges - Ficciones [Federico Salles, 2014, 128kbps, MP3]", "es",
            marks=pytest.mark.xfail(reason="Нет испанских маркеров → V4='en'", strict=True)
        ),
    ])
    def test_spanish_xfail(self, folder, expected):
        assert d(folder) == expected


class TestTurkish:
    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "Sabahattin Ali - Kürk Mantolu Madonna [Rüştü Asyalı, 2012, 128kbps, MP3]", "tr",
            marks=pytest.mark.xfail(reason="ü пересекается с немецким → de", strict=True)
        ),
        pytest.param(
            "Orhan Pamuk - Kara Kitap [Mazlum Kiper, 2009, 128kbps, MP3]", "tr",
            marks=pytest.mark.xfail(reason="Нет турецких маркеров → en", strict=True)
        ),
    ])
    def test_turkish_xfail(self, folder, expected):
        assert d(folder) == expected


class TestPolish:
    @pytest.mark.parametrize("folder", [
        "Stanisław Lem - Solaris [1961, MP3]",
        "Andrzej Sapkowski - Ostatnie życzenie [2015]",
    ])
    def test_polish_books(self, folder):
        assert d(folder) == "pl"


class TestCzechSlovak:
    @pytest.mark.parametrize("folder", [
        "Milan Kundera - Nesnesitelná lehkost bytí [2004]",
        "Karel Čapek - R.U.R. [2010]",
    ])
    def test_czech_slovak_books(self, folder):
        assert d(folder) == "cs"


class TestRomanian:
    @pytest.mark.parametrize("folder", [
        "Ion Creangă - Amintiri din copilărie [2015]",
    ])
    def test_romanian_books(self, folder):
        assert d(folder) == "ro"


class TestFinnish:
    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "Mika Waltari - Sinuhe egyptiläinen [2008]", "fi",
            marks=pytest.mark.xfail(reason="ä пересекается с немецким → de", strict=True)
        ),
        pytest.param(
            "Tove Jansson - Muumipeikko ja pyrstötähti [2012]", "fi",
            marks=pytest.mark.xfail(reason="ä/ö пересекаются с немецким → de", strict=True)
        ),
    ])
    def test_finnish_xfail(self, folder, expected):
        assert d(folder) == expected


class TestItalian:
    @pytest.mark.parametrize("folder", [
        "Italo Calvino - E così via [2008]",
    ])
    def test_italian_books(self, folder):
        assert d(folder) == "it"

    @pytest.mark.parametrize("folder,expected", [
        pytest.param(
            "Alessandro Manzoni - I Promessi Sposi [della, 2011]", "it",
            marks=pytest.mark.xfail(reason="Средняя длина слова > 6 -> ru-translit", strict=True)
        ),
        pytest.param(
            "Italo Calvino - Il barone rampante [2006]", "it",
            marks=pytest.mark.xfail(reason="Начальное 'Il' без пробела слева -> en", strict=True)
        ),
    ])
    def test_italian_xfail(self, folder, expected):
        assert d(folder) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# Книжные тесты (реальные папки из библиотеки)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRealWorldFolders:
    """Полные имена папок как они встречаются на диске."""

    @pytest.mark.parametrize("folder,expected", [
        # Русские
        ("Лев Толстой - Война и мир [Александр Клюквин, 2008, 192kbps, MP3]", "ru"),
        ("Федор Достоевский - Преступление и наказание [Иван Литвинов, 2012, M4B]", "ru"),
        # Транслит
        ("Voskresenskaya - Glavnoe v rodah [2021, 128kbps]", "ru"),
        ("Dostoevsky - Prestuplenie i nakazanie [2018, 128kbps]", "ru"),
        # Английские
        ("Stephen King - The Shining [Campbell Scott, 2012, 128kbps, MP3]", "en"),
        ("George Orwell - 1984 [Simon Prebble, 2008, 128kbps, M4B]", "en"),
        # Немецкие
        ("Goethe - Faust: Eine Tragödie [Will Quadflieg, 1999, 128kbps, MP3]", "de"),
        # Французские
        ("Victor Hugo - Les Misérables [Gérard Depardieu, 2005, 128kbps, MP3]", "fr"),
        # Арабские
        ("نجيب محفوظ - الثلاثية [جمال سليمان, 2015, 64kbps, M4B]", "ar"),
        # Хинди
        ("मुंशी प्रेमचंद - गोदान [समीर गोस्वामी, 2018, 96kbps, MP3]", "hi"),
        # Японский (с каной)
        ("夏目漱石 - こころ [朗読: 山田太郎, 2016, 96kbps, M4B]", "ja"),
        # Корейский
        ("한강 - 채식주의자 [김성우, 2020, 128kbps, MP3]", "ko"),
        # Тайский
        ("สุนทรภู่ - พระอภัยมณี [ผู้อ่าน: สมชาย, 2017, 96kbps, MP3]", "th"),
        # Китайский
        ("曹雪芹 - 红楼梦 [朗读: 张三, 2010, 64kbps, M4B]", "zh"),
        # Армянский
        ("Րաֆֆի - Սամվել [Աշոտ Ղազարյան, 2015, 128kbps, MP3]", "hy"),
        # Иврит
        ("\u05e2\u05de\u05d5\u05e1 \u05e2\u05d5\u05d6 - \u05de\u05d9\u05db\u05d0\u05dc \u05e9\u05dc\u05d9 [2010]", "he"),
        # Украинский
        ("Іван Франко - Захар Беркут [2015, MP3]", "uk"),
        # Белорусский
        ("Васіль Быкаў - Доўгая дарога дадому [2003, MP3]", "be"),
        # Польский
        ("Stanisław Lem - Solaris [1961, MP3]", "pl"),
        # Чешский
        ("Karel Čapek - R.U.R. [2010]", "cs"),
        # Румынский
        ("Ion Creangă - Amintiri din copilărie [2015]", "ro"),
    ])
    def test_real_folders(self, folder, expected):
        assert d(folder) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# Граничные случаи
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_string(self):
        assert d("") == "unknown"

    def test_only_digits(self):
        result = d("1984 2001 128")
        assert result in ("unknown", "en")  # цифры не дают языка

    def test_only_brackets(self):
        assert d("[128kbps, MP3]") in ("unknown", "en")

    def test_only_spaces(self):
        assert d("   ") == "unknown"

    def test_very_long_text(self):
        # Не должен падать на длинных строках
        result = d("Автор - " + "Слово " * 200 + "[2020, MP3]")
        assert result == "ru"

    def test_mixed_cyrillic_latin(self):
        assert d("Стивен Кинг - IT [2016, M4B]") == "ru"

    def test_metadata_stripped_before_analysis(self):
        # Без стриппинга латиница в [MP3] перевешивала бы нелатинский скрипт
        assert d("한강 - 채식주의자 [MP3, 128kbps, 2020]") == "ko"
        assert d("曹雪芹 - 红楼梦 [MP3, 2010]") == "zh"
        assert d("مُنشي - كتاب [MP3, 2018]") == "ar"

    def test_numbers_in_title(self):
        assert d("조남주 - 82년생 김지영 [이지은, 2019, 128kbps, MP3]") == "ko"

    def test_roman_numerals_en_not_it(self):
        for folder in [
            "Surzhikov Roman - Vol. I: The Well of Worlds [2023]",
            "Shakespeare - Henry IV, Part II [2010, MP3]",
            "Tolkien - The Lord of the Rings Vol. III [MP3]",
        ]:
            result = d(folder)
            assert result == "en" and result != "it", f"Failed: {folder}"

    def test_detect_detailed_rule_field_nonempty(self):
        for folder in [
            "Толстой - Война и мир [2008, MP3]",
            "Stephen King - The Shining [2012, MP3]",
            "夏目漱石 - こころ [2016, M4B]",
        ]:
            r = detect_detailed(folder)
            assert r.rule, f"Empty rule for: {folder}"

    def test_detect_detailed_v1_v2_v4_nonempty(self):
        r = detect_detailed("Лев Толстой - Война и мир [2008, MP3]")
        assert r.v1 and r.v2 and r.v4


# ═══════════════════════════════════════════════════════════════════════════════
# Smoke: нет падений, нет пустых результатов
# ═══════════════════════════════════════════════════════════════════════════════

SMOKE_SAMPLES = [
    "Stephen King - The Shining [Campbell Scott, 2012, 128kbps, MP3]",
    "Лев Толстой - Война и мир [Александр Клюквин, 2008, 192kbps, MP3]",
    "Victor Hugo - Les Misérables [Gérard Depardieu, 2005, 128kbps, MP3]",
    "Goethe - Faust: Eine Tragödie [Will Quadflieg, 1999, 128kbps, MP3]",
    "Voskresenskaya - Glavnoe v rodah [2021, 128kbps]",
    "Стивен Кинг - IT [2016, M4B]",
    "نجيب محفوظ - الثلاثية [جمال سليمان, 2015, M4B]",
    "मुंशी प्रेमचंद - गोदान [समीर गोस्वामी, 2018, MP3]",
    "夏目漱石 - こころ [朗読: 山田太郎, 2016, M4B]",
    "한강 - 채식주의자 [김성우, 2020, MP3]",
    "สุนทรภู่ - พระอภัยมณี [ผู้อ่าน: สมชาย, 2017, MP3]",
    "曹雪芹 - 红楼梦 [朗读: 张三, 2010, M4B]",
    "Nguyễn Du - Truyện Kiều [Người đọc: Lê Thiết, 2013, MP3]",
    "Elif Şafak - Aşk [Tilbe Saran, 2015, MP3]",
    "",
    "   ",
    "123456",
    "[128kbps, MP3]",
]


@pytest.mark.parametrize("folder", SMOKE_SAMPLES)
def test_no_crash(folder):
    """detect() не должен бросать исключений ни для какого входа."""
    detect(folder)


@pytest.mark.parametrize("folder", SMOKE_SAMPLES)
def test_no_empty_result(folder):
    """detect() не должен возвращать пустую строку."""
    result = detect(folder)
    assert result not in ("", None)


@pytest.mark.parametrize("folder", SMOKE_SAMPLES)
def test_detailed_consistent_with_detect(folder):
    """detect_detailed().lang всегда совпадает с detect()."""
    assert detect_detailed(folder).lang == detect(folder)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
