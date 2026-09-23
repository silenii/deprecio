"""Smart Fuzzy Search Engine with Transliteration and Token Matching for Smartphones."""

import difflib
import re
from typing import Dict, List, Optional, Tuple
from deprecio.models.device import Device

# Словарь транслитерации частых брендов и названий с русского на латиницу
BRAND_TRANSLIT: Dict[str, str] = {
    "айфон": "iphone",
    "самсунг": "samsung",
    "сяоми": "xiaomi",
    "редми": "redmi",
    "поко": "poco",
    "пиксель": "pixel",
    "насинг": "nothing",
    "ванплас": "oneplus",
    "реалми": "realme",
    "хонор": "honor",
    "виво": "vivo",
    "оппо": "oppo",
    "сони": "sony",
    "ультра": "ultra",
    "про": "pro",
    "плюс": "plus",
    "фон": "phone",
    "ноут": "note",
    "мини": "mini",
    "макс": "max",
}


def normalize_search_text(text: str) -> str:
    """Очищает строку запроса, приводит к нижнему регистру и заменяет русскую транслитерацию."""
    s = text.lower().strip()

    # Замена скобок и спецсимволов на пробелы
    s = re.sub(r"[\(\)\[\]\-_,/\.]", " ", s)

    # Транслитерация частых слов
    words = s.split()
    translated_words = [BRAND_TRANSLIT.get(w, w) for w in words]
    s = " ".join(translated_words)

    # Замена кириллических префиксов перед цифрами (с24 -> s24, а55 -> a55, 2а -> 2a)
    s = re.sub(r"\bс(\d+)", r"s\1", s)
    s = re.sub(r"\bа(\d+)", r"a\1", s)
    s = re.sub(r"(\d+)а\b", r"\1a", s)
    s = re.sub(r"\bф(\d+)", r"f\1", s)
    s = re.sub(r"\bх(\d+)", r"x\1", s)

    # Убираем дубли пробелов
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Известные бренды для предотвращения ложных межбрендовых сопоставлений
KNOWN_BRANDS = {
    "apple", "iphone", "samsung", "xiaomi", "redmi", "poco", "google", "nothing",
    "oneplus", "realme", "honor", "huawei", "vivo", "oppo", "sony", "nokia",
    "motorola", "meizu", "asus", "zte", "infinix", "tecno",
}

# Иерархия брендов и суббрендов
PARENT_BRANDS = {
    "redmi": "xiaomi",
    "poco": "xiaomi",
    "iphone": "apple",
}


def check_brand_compatibility(clean_q: str, clean_t: str, clean_b: str) -> bool:
    """Проверяет, не запрошен ли явно другой бренд (например, запрос oneplus для apple)."""
    q_words = set(clean_q.split())
    q_brands = q_words.intersection(KNOWN_BRANDS)
    if not q_brands:
        return True

    t_words = set(clean_t.split()).union({clean_b} if clean_b else set())
    for qb in q_brands:
        allowed = {qb, PARENT_BRANDS.get(qb, qb)}
        for child, parent in PARENT_BRANDS.items():
            if parent == qb:
                allowed.add(child)
        if not t_words.intersection(allowed):
            return False
    return True


def extract_model_numbers(text: str) -> set:
    """Извлекает числовые идентификаторы моделей (например, 24, 7, 2a, 13, 15)."""
    return set(re.findall(r"\d+[a-z]?", text))


def calculate_match_score(query: str, target_name: str, brand: str) -> float:
    """
    Вычисляет релевантность совпадения (от 0.0 до 1.0):
    1. Точное совпадение -> 1.0
    2. Вхождение подстроки целиком -> 0.95
    3. Все слова из запроса есть в названии модели -> 0.90
    4. Нечеткое совпадение через SequenceMatcher -> 0.0 .. 0.85
    """
    clean_q = normalize_search_text(query)
    clean_t = normalize_search_text(target_name)
    clean_b = normalize_search_text(brand)

    if not clean_q or not clean_t:
        return 0.0

    # Проверка совместимости брендов (OnePlus 11 не должен сопоставляться с Apple iPhone 11)
    if not check_brand_compatibility(clean_q, clean_t, clean_b):
        return 0.0

    # Проверка строгой согласованности числовых номеров поколений.
    # Если в запросе есть число (например 7 в 'Redmi Note 7'), а у кандидата
    # другое число (13 в 'Redmi Note 13'), они НЕ должны совпадать!
    q_nums = extract_model_numbers(clean_q)
    if q_nums:
        t_nums = extract_model_numbers(clean_t)
        for qn in q_nums:
            has_match = any(
                qn == tn or (len(qn) > 1 and tn.endswith(qn)) or (len(tn) > 1 and qn.endswith(tn))
                for tn in t_nums
            )
            if not has_match:
                return 0.0

    # 1. Полное совпадение
    if clean_q == clean_t:
        return 1.0

    # 2. Подстрока (например "nothing 2a" входит в "nothing phone 2a")
    if clean_q in clean_t:
        return 0.95

    # 3. Совпадение по токенам (все введенные слова есть в названии)
    q_tokens = set(clean_q.split())
    t_tokens = set(clean_t.split())
    if clean_b:
        t_tokens.add(clean_b)

    # Если все токены запроса найдены в названии
    if q_tokens.issubset(t_tokens):
        return 0.90

    # Если токены запроса начинаются с введенных префиксов (напр. 's24' или '2a')
    all_prefixes_match = True
    for q_tok in q_tokens:
        found_tok = any(t_tok.startswith(q_tok) or q_tok.startswith(t_tok) for t_tok in t_tokens)
        if not found_tok:
            all_prefixes_match = False
            break

    if all_prefixes_match and len(q_tokens) > 0:
        return 0.85

    # 4. Нечеткое сходство через SequenceMatcher
    ratio = difflib.SequenceMatcher(None, clean_q, clean_t).ratio()
    return round(ratio, 3)


def fuzzy_search_devices(
    query: str,
    devices: List[Device],
    min_score: float = 0.50,
) -> List[Tuple[Device, float]]:
    """
    Ищет устройства с нечетким сопоставлением и ранжирует по убыванию релевантности.
    """
    scored: List[Tuple[Device, float]] = []

    for dev in devices:
        score = calculate_match_score(query, dev.name, dev.brand)
        if score >= min_score:
            scored.append((dev, score))

    # Сортировка по очкам релевантности
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
