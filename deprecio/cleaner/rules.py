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

EDITION_PATTERNS: Dict[EditionType, List[str]] = {
    EditionType.EAC_ROSTEST: [
        "ростест", "rostest", "официальный", "официал", "офиц",
        "eac", "рст", "гарантия рф", "гарантия россия",
    ],
    EditionType.CN: [
        "китай", "китайская версия", "cn версия", " cn ", "for china",
        "chinese", "глобалка без band 20",
    ],
    EditionType.GLOBAL_EU: [
        "global", "глобал", "европейская версия", "eu", "international",
        "международная версия",
    ],
    EditionType.US: [
        "американская версия", "us версия", " us ", "for usa",
        "esim only", "snapdragon us",
    ],
    EditionType.IN: [
        "индийская версия", " in ", "india", "for india",
    ],
}


def detect_edition_from_text(text: str) -> Optional[EditionType]:
    """
    Определяет региональную версию смартфона по тексту объявления.
    Приоритет: EAC_ROSTEST > CN > GLOBAL_EU > US > IN.
    Возвращает None если версия не определена.
    """
    text_lower = text.lower()
    priority = [
        EditionType.EAC_ROSTEST,
        EditionType.CN,
        EditionType.GLOBAL_EU,
        EditionType.US,
        EditionType.IN,
    ]
    for edition in priority:
        for kw in EDITION_PATTERNS[edition]:
            if kw in text_lower:
                return edition
    return None


def detect_defect_from_text(text: str) -> Optional[str]:
    """Проверка текста на наличие маркеров дефектов и неликвида."""
    text_lower = text.lower()
    for keyword in DEFECT_KEYWORDS:
        if keyword in text_lower:
            return keyword
    return None
