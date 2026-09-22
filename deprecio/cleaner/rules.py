"""Stop-words, defect patterns, and edition keyword matchers for Avito listings."""

import re
from typing import Dict, List, Optional
from deprecio.models.device import EditionType
from deprecio.models.listing import ItemCondition

# Ключевые слова, указывающие на непригодность или серьезный дефект
DEFECT_KEYWORDS: List[str] = [
    "на запчасти",
    "под восстановление",
    "не включается",
    "кирпич",
    "утопленник",
    "после воды",
    "разбит экран",
    "разбито стекло",
    "трещина на экране",
    "полоса на экране",
    "пятно на матрице",
    "выгорание",
    "заблокирован",
    "icloud",
    "айклауд",
    "байпас",
    "bypass",
    "frp",
    "mi аккаунт",
    "mi account",
    "demo",
    "демо",
    "не работает face id",
    "не работает nfc",
    "без отпечатка",
]

# Паттерны для определения региональной версии устройства
EDITION_PATTERNS: Dict[EditionType, List[str]] = {
    EditionType.EAC_ROSTEST: [
        r"\bростест\b",
        r"\bрст\b",
        r"\beac\b",
        r"\bеас\b",
        r"\bru/a\b",
        r"\bофициальный\b",
    ],
    EditionType.CN: [
        r"\bкитай\b",
        r"\bкитаец\b",
        r"\bcn\b",
        r"\bch/a\b",
        r"\boriginos\b",
        r"\bкитайская версия\b",
    ],
    EditionType.US: [
        r"\bсша\b",
        r"\bамериканец\b",
        r"\busa\b",
        r"\bll/a\b",
        r"\besim only\b",
    ],
    EditionType.GLOBAL_EU: [
        r"\bглобал\b",
        r"\bглобалка\b",
        r"\bglobal\b",
        r"\beu\b",
        r"\bевропеец\b",
        r"\bzd/a\b",
    ],
    EditionType.IN: [
        r"\bиндия\b",
        r"\bиндиец\b",
        r"\bhn/a\b",
    ],
}


def detect_edition_from_text(text: str) -> Optional[EditionType]:
    """Автоматическое распознавание региональной версии по тексту объявления."""
    text_lower = text.lower()
    for edition, patterns in EDITION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return edition
    return None


def detect_defect_from_text(text: str) -> Optional[str]:
    """Проверка текста на наличие маркеров дефектов и неликвида."""
    text_lower = text.lower()
    for keyword in DEFECT_KEYWORDS:
        if keyword in text_lower:
            return keyword
    return None
