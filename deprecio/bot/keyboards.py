"""Inline and Reply keyboards for Deprecio Telegram Bot."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота."""
    keyboard = [
        [
            KeyboardButton(text="🔍 Найти смартфон"),
            KeyboardButton(text="🟢 Зона Sweet Spot"),
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


def get_device_card_keyboard(model_id: str) -> InlineKeyboardMarkup:
    """Инлайн-кнопки под карточкой смартфона."""
    buttons = [
        [
            InlineKeyboardButton(text="🔮 Прогноз уценки", callback_data=f"forecast:{model_id}"),
            InlineKeyboardButton(text="💡 Найти аналоги", callback_data=f"analogs:{model_id}"),
        ],
        [
            InlineKeyboardButton(text="⚖️ Сравнить CN и EAC", callback_data=f"editions:{model_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад в меню", callback_data="menu:main")]]
    )
