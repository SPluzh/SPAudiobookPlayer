from difflib import SequenceMatcher

# マппинг клавиш раскладки (физические позиции на клавиатуре)
EN_TO_RU = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е',
    'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
    '[': 'х', ']': 'ъ', 'a': 'ф', 's': 'ы', 'd': 'в',
    'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л',
    'l': 'д', ';': 'ж', "'": 'э', 'z': 'я', 'x': 'ч',
    'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь',
    ',': 'б', '.': 'ю', '`': 'ё'
}

RU_TO_EN = {v: k for k, v in EN_TO_RU.items()}

def transliterate(text: str) -> str:
    """Конвертация текста из одной раскладки в другую (RU<->EN)."""
    result = []
    for char in text:
        is_upper = char.isupper()
        char_lower = char.lower()
        
        if char_lower in EN_TO_RU:
            converted = EN_TO_RU[char_lower]
        elif char_lower in RU_TO_EN:
            converted = RU_TO_EN[char_lower]
        else:
            converted = char_lower
            
        result.append(converted.upper() if is_upper else converted)
    return "".join(result)

def smart_search(query: str, text: str) -> bool:
    """
    Комбинированный нечёткий поиск.
    Returns True если текст соответствует запросу.
    """
    if not query:
        return True
        
    query = query.lower()
    text = text.lower()
    
    # 1. Точное вхождение
    if query in text:
        return True
        
    # 2. Все слова запроса содержатся в тексте
    words = query.split()
    if len(words) > 1 and all(w in text for w in words):
        return True
        
    # 3. Транслитерация раскладки
    translit_query = transliterate(query)
    if translit_query != query:
        if translit_query in text:
            return True
        translit_words = translit_query.split()
        if len(translit_words) > 1 and all(w in text for w in translit_words):
            return True
            
    # 4. Нечёткое сравнение по словам
    text_words = text.split()
    if not text_words:
        return False
        
    # Проверяем для оригинального запроса
    all_words_found = True
    for q_word in words:
        found = False
        for t_word in text_words:
            # Оптимизация: если короткое слово совпадает как подстрока
            if len(q_word) <= 3 and q_word in t_word:
                found = True
                break
                
            ratio = SequenceMatcher(None, q_word, t_word).ratio()
            if ratio >= 0.7:
                found = True
                break
        if not found:
            all_words_found = False
            break
            
    if all_words_found:
        return True
        
    # Проверяем нечёткое сравнение для транслитерированного запроса
    if translit_query != query:
        translit_words = translit_query.split()
        all_translit_found = True
        for q_word in translit_words:
            found = False
            for t_word in text_words:
                if len(q_word) <= 3 and q_word in t_word:
                    found = True
                    break
                    
                ratio = SequenceMatcher(None, q_word, t_word).ratio()
                if ratio >= 0.7:
                    found = True
                    break
            if not found:
                all_translit_found = False
                break
        if all_translit_found:
            return True
            
    return False
