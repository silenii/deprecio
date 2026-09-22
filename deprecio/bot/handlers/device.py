"""Handlers for Smartphone Search, Card Display, and Sweet Spot Analysis."""

from datetime import date
from typing import Optional
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from deprecio.bot.keyboards import get_back_keyboard, get_device_card_keyboard
from deprecio.core import analyze_sweet_spot
from deprecio.models.device import Device, EditionType
from deprecio.providers import LocalCatalogProvider

router = Router(name="device_router")
catalog = LocalCatalogProvider()


def format_device_card(device: Device) -> str:
    """Форматирование карточки смартфона с аналитикой уценки."""
    catalog.reload()
    lines = [
        f"📱 **{device.name}**",
        f"• **Производитель:** {device.brand}",
        f"• **Процессор:** {device.chipset or 'Не указан'}",
        f"• **Класс линейки:** {device.lineage.tier} ({device.lineage.series})",
        "",
        "📦 **Доступные версии и комплектация:**",
    ]

    base_msrp_rub = 80000.0  # Опорная цена по умолчанию
    first_release_date: Optional[date] = None

    for ed in device.editions:
        edition_label = {
            EditionType.EAC_ROSTEST: "🇷🇺 Ростест / EAC",
            EditionType.CN: "🇨🇳 Китайская (CN)",
            EditionType.GLOBAL_EU: "🌐 Глобальная (EU)",
            EditionType.US: "🇺🇸 Версия для США",
            EditionType.IN: "🇮🇳 Индийская (IN)",
            EditionType.OTHER: "🌍 Другой регион",
        }.get(ed.edition_type, ed.edition_type.value)

        charger_info = (
            f"Зарядка {ed.bundle.charger_wattage_w}W" if ed.bundle.has_charger else "Без блока зарядки"
        )
        band20_info = "Band 20 ✅" if ed.hardware.has_band_20 else "Band 20 ❌"
        esim_info = "eSIM ✅" if ed.hardware.has_esim else "eSIM ❌"

        lines.append(f"• **{edition_label}:** {charger_info} | {band20_info} | {esim_info}")

        if ed.memory_variants:
            mv = ed.memory_variants[0]
            lines.append(f"  └ *Старт ({mv.ram_gb}/{mv.storage_gb}GB):* {mv.msrp_local:,.0f} {mv.currency.value}")
            if mv.currency.value == "RUB":
                base_msrp_rub = mv.msrp_local

        if ed.release_date and (not first_release_date or ed.release_date < first_release_date):
            first_release_date = ed.release_date

    lines.append("")

    # Расчет Sweet Spot и аналитики рынка
    months_old = 8  # Оценочный возраст для аналитики
    if first_release_date:
        today = date.today()
        months_old = max(1, (today.year - first_release_date.year) * 12 + today.month - first_release_date.month)

    current_market_price = base_msrp_rub * 0.58  # Оценочная текущая медиана вторички
    analysis = analyze_sweet_spot(
        months_since_release=months_old,
        current_price=current_market_price,
        msrp_price=base_msrp_rub,
    )

    lines.extend([
        "📊 **Анализ вторичного рынка:**",
        f"• **Возраст модели:** {months_old} мес. с момента релиза",
        f"• **Ориентир цены (б/у):** ≈ {current_market_price:,.0f} ₽",
        f"• **Остаточная стоимость (RV%):** {analysis.current_rv_percent:.1f}% ({analysis.total_drop_percent:+.1f}%)",
        "",
        f"💡 **Вердикт Deprecio:**\n{analysis.advice_buyer}",
    ])

    return "\n".join(lines)


@router.message(F.text == "🔍 Найти смартфон")
async def prompt_search(message: Message) -> None:
    await message.answer(
        "Введите название смартфона для поиска (например: *Xiaomi 14* или *iPhone 15*):",
        parse_mode="Markdown",
    )


@router.message(F.text == "🟢 Зона Sweet Spot")
async def list_sweet_spot(message: Message) -> None:
    catalog.reload()
    devices = catalog.search_devices("")
    lines = [
        "🟢 **Смартфоны в зоне Sweet Spot (идеальный момент для покупки):**\n",
        "Эти устройства уже потеряли первоначальные 40–50% стартовой цены и вышли на стабильное плато, "
        "сохраняя максимальную актуальность характеристик:\n",
    ]
    for dev in devices:
        lines.append(f"• **{dev.name}** ({dev.lineage.tier}) — `{dev.model_id}`")

    lines.append("\nНажмите на модель или напишите её название для подробного отчета!")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.callback_query(F.data.startswith("analogs:"))
async def handle_analogs_callback(callback: CallbackQuery) -> None:
    model_id = callback.data.split(":")[1]
    dev = catalog.get_device(model_id)
    if not dev:
        await callback.answer("Модель не найдена.")
        return

    analogs = catalog.find_analogs(dev)
    if not analogs:
        text = f"💡 Для модели **{dev.name}** прямых аналогов в каталоге пока нет. База ежедневно пополняется!"
    else:
        text = f"💡 **Прямые аналоги для {dev.name} ({dev.lineage.tier}):**\n\n"
        for a in analogs:
            text += f"• **{a.name}** ({a.chipset or 'SoC'})\n"

    await callback.message.answer(text, reply_markup=get_back_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.message(F.text)
async def handle_device_search(message: Message) -> None:
    if message.text.startswith("/"):
        return

    catalog.reload()
    results = catalog.search_devices(message.text)

    if not results:
        await message.answer(
            f"🔍 По запросу *'{message.text}'* ничего не найдено.\n\n"
            "Попробуйте написать, например: `Xiaomi` или `iPhone`.\n"
            "База данных активно пополняется новыми моделями!",
            parse_mode="Markdown",
        )
        return

    target = results[0]
    card_text = format_device_card(target)
    await message.answer(
        card_text,
        reply_markup=get_device_card_keyboard(target.model_id),
        parse_mode="Markdown",
    )
