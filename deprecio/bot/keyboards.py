"""Inline and Reply keyboards for Deprecio Telegram Bot."""

from typing import List, Optional, Tuple
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    keyboard = [
        [
            KeyboardButton(text="🔍 Найти смартфон"),
            KeyboardButton(text="🟢 Зона Sweet Spot"),
            KeyboardButton(text="🆕 Новинки"),
            KeyboardButton(text="⭐ Избранное"),
        ],
        [
            KeyboardButton(text="⚖️ Версии CN vs EAC"),
            KeyboardButton(text="ℹ️ Как это работает?"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или введите модель...",
    )


def get_device_card_keyboard(
    model_id: str,
    alternative_matches: Optional[List[Tuple[str, str]]] = None,
    is_favorite: bool = False,
) -> InlineKeyboardMarkup:
    """Инлайн-кнопки под карточкой смартфона с опцией выбора других совпадений."""
    buttons = [
        [InlineKeyboardButton(text="⭐ Удалить из избранного" if is_favorite else "☆ Добавить в избранное", callback_data=f"favorite:{'remove' if is_favorite else 'add'}:{model_id}")],
        [
            InlineKeyboardButton(text="🔮 Прогноз уценки", callback_data=f"forecast:{model_id}"),
            InlineKeyboardButton(text="💡 Найти аналоги", callback_data=f"analogs:{model_id}"),
        ],
        [
            InlineKeyboardButton(text="⚖️ Сравнить CN и EAC", callback_data=f"editions:{model_id}"),
        ],
        [
            InlineKeyboardButton(text="📊 Сравнить с пред. поколением", callback_data=f"gen_compare:{model_id}"),
        ],
    ]

    if alternative_matches:
        for alt_id, alt_name in alternative_matches:
            buttons.append([
                InlineKeyboardButton(text=f"👉 Также: {alt_name}", callback_data=f"show_dev:{alt_id}")
            ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад в меню", callback_data="menu:main")]]
    )
