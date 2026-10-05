"""Favorites commands and callbacks."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from deprecio.favorites import SQLiteFavoritesRepository
from deprecio.providers import CachedSpecsProvider
from deprecio.bot.keyboards import get_back_keyboard, get_device_card_keyboard

router = Router(name="favorites_router")
PAGE_SIZE = 10


def _pages(page: int, more: bool) -> InlineKeyboardMarkup:
    buttons = []
    if page:
        buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"favorites:page:{page - 1}")
        )
    if more:
        buttons.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"favorites:page:{page + 1}")
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[buttons]
        or [[InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main")]]
    )


async def _show(
    message: Message,
    user_id: int,
    page: int,
    favorites: SQLiteFavoritesRepository,
    catalog: CachedSpecsProvider,
) -> None:
    items = favorites.list(user_id, page, PAGE_SIZE + 1)
    more, items = len(items) > PAGE_SIZE, items[:PAGE_SIZE]
    if not items:
        await message.answer("⭐ Избранное пока пусто.", reply_markup=get_back_keyboard())
        return
    names = [
        f"• {catalog.get_device(item.model_id).name if catalog.get_device(item.model_id) else item.model_id}"
        for item in items
    ]
    await message.answer(
        "⭐ **Избранное**\n\n" + "\n".join(names),
        reply_markup=_pages(page, more),
        parse_mode="Markdown",
    )


@router.message(Command("favorites"))
@router.message(F.text == "⭐ Избранное")
async def show_favorites(
    message: Message, favorites: SQLiteFavoritesRepository, catalog: CachedSpecsProvider
) -> None:
    await _show(message, message.from_user.id, 0, favorites, catalog)


@router.callback_query(F.data.startswith("favorites:page:"))
async def favorites_page(
    callback: CallbackQuery, favorites: SQLiteFavoritesRepository, catalog: CachedSpecsProvider
) -> None:
    await _show(
        callback.message,
        callback.from_user.id,
        int(callback.data.rsplit(":", 1)[1]),
        favorites,
        catalog,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("favorite:"))
async def favorite_action(
    callback: CallbackQuery, favorites: SQLiteFavoritesRepository, catalog: CachedSpecsProvider
) -> None:
    _, action, model_id = callback.data.split(":", 2)
    changed = (
        favorites.add(callback.from_user.id, model_id)
        if action == "add"
        else favorites.remove(callback.from_user.id, model_id)
    )
    if not changed:
        await callback.answer("Уже добавлено." if action == "add" else "Запись уже удалена.")
        return
    if catalog.get_device(model_id):
        await callback.message.edit_reply_markup(
            reply_markup=get_device_card_keyboard(model_id, is_favorite=action == "add")
        )
    await callback.answer("Добавлено в избранное." if action == "add" else "Удалено из избранного.")
