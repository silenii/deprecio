"""Inline-mode handlers for searching devices in Telegram chats."""

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from deprecio.providers import CachedSpecsProvider

router = Router()
catalog = CachedSpecsProvider()


@router.inline_query()
async def handle_inline_search(query: InlineQuery) -> None:
    q = query.query.strip()
    if len(q) < 2:
        await query.answer([], cache_time=1)
        return

    devices = catalog.search_devices(q)[:5]
    results = []
    for dev in devices:
        text = (
            f"📱 {dev.name}\n"
            f"• Чипсет: {dev.chipset or 'Нет данных'}\n"
            f"• Класс: {dev.lineage.tier}\n"
            f"• Версии: {', '.join(e.edition_type.value for e in dev.editions)}\n"
            f"\nОткройте бота для полного анализа цен и прогноза уценки."
        )
        results.append(
            InlineQueryResultArticle(
                id=dev.model_id,
                title=dev.name,
                description=f"{dev.brand} · {dev.lineage.tier} · {dev.chipset or ''}",
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode=None,
                ),
            )
        )

    await query.answer(results, cache_time=30, is_personal=False)
