"""Handlers for Smartphone Search, Card Display, and Sweet Spot Analysis."""

from datetime import date
from typing import Optional
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from deprecio.bot.keyboards import get_back_keyboard, get_device_card_keyboard
from deprecio.core import analyze_sweet_spot
from deprecio.models.device import Device, EditionType
from deprecio.providers import CachedSpecsProvider

router = Router(name="device_router")
catalog = CachedSpecsProvider()


def format_device_card(device: Device) -> str:
    """Форматирование карточки смартфона с аналитикой уценки."""
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

    market_stats = catalog.get_market_stats(device)
    current_market_price = market_stats.median_price_rub

    analysis = analyze_sweet_spot(
        months_since_release=months_old,
        current_price=current_market_price,
        msrp_price=base_msrp_rub,
    )

    lines.extend([
        "📊 **Анализ вторичного рынка (Авито / РФ):**",
        f"• **Возраст модели:** {months_old} мес. с момента релиза",
        f"• **Медианная цена (б/у):** ≈ {current_market_price:,.0f} ₽",
        f"• **Диапазон рынка (IQR):** {market_stats.p25_price_rub:,.0f} — {market_stats.p75_price_rub:,.0f} ₽",
        f"• **Выборка лотов:** {market_stats.clean_listings_count} шт. (отсеяно выбросов/дефектов: {market_stats.defective_count + market_stats.outliers_count})",
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


@router.callback_query(F.data.startswith("forecast:"))
async def handle_forecast_callback(callback: CallbackQuery) -> None:
    from deprecio.forecast import generate_price_forecast

    model_id = callback.data.split(":")[1]
    dev = catalog.get_device(model_id)
    if not dev:
        await callback.answer("Модель не найдена.")
        return

    # Оценка стартовой цены из спецификаций
    base_price = 80000.0
    for ed in dev.editions:
        if ed.memory_variants:
            mv = ed.memory_variants[0]
            if mv.currency.value == "RUB":
                base_price = mv.msrp_local
                break

    market_stats = catalog.get_market_stats(dev)
    current_market_price = market_stats.median_price_rub

    report = generate_price_forecast(dev, current_price_rub=current_market_price, months_horizon=12)

    lines = [
        f"🔮 **Прогноз уценки: {dev.name}**\n",
        f"• Стартовая цена (MSRP): **{base_price:,.0f} ₽**",
        f"• Текущая медиана вторички (Авито): **{current_market_price:,.0f} ₽**",
        f"• Темп амортизации бренда: **{report.monthly_decay_rate * 100:.1f}% в месяц**",
        f"• Точка входа в Sweet Spot: **через {report.sweet_spot_month} мес.**\n",
        "📉 **Прогнозируемый график снижения цен:**",
    ]

    for p in report.points:
        line = f"• **+{p.months_ahead} мес. ({p.target_date}):** ≈ {p.predicted_price_rub:,.0f} ₽ ({p.predicted_rv_percent}%)"
        if p.trigger_event:
            line += f"\n   └ {p.trigger_event}"
        lines.append(line)

    lines.extend([
        "",
        f"💡 **Итог:** {report.summary_verdict}",
    ])

    await callback.message.answer("\n".join(lines), reply_markup=get_back_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("editions:"))
async def handle_editions_callback(callback: CallbackQuery) -> None:
    model_id = callback.data.split(":")[1]
    dev = catalog.get_device(model_id)
    if not dev:
        await callback.answer("Модель не найдена.")
        return

    market_stats = catalog.get_market_stats(dev)

    lines = [
        f"⚖️ **Сравнение региональных версий: {dev.name}**\n",
        "Различия между версиями и реальные цены вторичного рынка РФ:\n",
    ]

    for ed in dev.editions:
        edition_title = {
            EditionType.EAC_ROSTEST: "🇷🇺 Ростест / EAC (Официальная в РФ)",
            EditionType.CN: "🇨🇳 Китайская версия (CN)",
            EditionType.GLOBAL_EU: "🌐 Глобальная (Global / EU)",
            EditionType.US: "🇺🇸 Американская (US)",
            EditionType.IN: "🇮🇳 Индийская (IN)",
            EditionType.OTHER: "🌍 Другой регион",
        }.get(ed.edition_type, ed.edition_type.value)

        lines.append(f"📌 **{edition_title}**")
        lines.append(f"• ОС: `{ed.os_name or 'Заводская'}`")
        lines.append(
            f"• Комплект: {'Блок ' + str(ed.bundle.charger_wattage_w) + 'W' if ed.bundle.has_charger else '❌ Без зарядного блока'}"
            f"{', чехол в комплекте' if ed.bundle.has_case else ''}"
        )
        lines.append(
            f"• Связь: Band 20 {'✅' if ed.hardware.has_band_20 else '❌ (хуже ловит 4G вне городов)'} | "
            f"eSIM {'✅' if ed.hardware.has_esim else '❌'} | "
            f"SIM: {ed.hardware.sim_slots}"
        )
        if ed.memory_variants:
            mv = ed.memory_variants[0]
            lines.append(f"• Стартовая цена: {mv.msrp_local:,.0f} {mv.currency.value}")

        ed_stat = market_stats.editions.get(ed.edition_type.value)
        if ed_stat:
            gap_str = ""
            if ed_stat.gap_vs_eac_percent < 0:
                gap_str = f" 📉 ({ed_stat.gap_vs_eac_percent}% от Ростеста)"
            elif ed_stat.gap_vs_eac_percent > 0:
                gap_str = f" 📈 (+{ed_stat.gap_vs_eac_percent}% от Ростеста)"
            elif ed.edition_type == EditionType.EAC_ROSTEST:
                gap_str = " (эталон цен)"

            lines.append(f"• **Цена вторички (Авито):** ≈ {ed_stat.median_price_rub:,.0f} ₽{gap_str}")
            lines.append(f"  └ Диапазон: {ed_stat.min_price_rub:,.0f} – {ed_stat.max_price_rub:,.0f} ₽ (лотов: {ed_stat.count})")

        lines.append("")

    lines.append(
        "💡 **Совет по ликвидности:**\n"
        "Китайские версии (CN) на вторичке в РФ стабильно продаются на 15–25% дешевле Ростеста "
        "из-за китайской вилки и отсутствия Band 20. Учитывайте этот дисконт при покупке и перепродаже!"
    )

    await callback.message.answer("\n".join(lines), reply_markup=get_back_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("show_dev:"))
async def handle_show_device_callback(callback: CallbackQuery) -> None:
    model_id = callback.data.split(":")[1]
    dev = catalog.get_device(model_id)
    if not dev:
        await callback.answer("Модель не найдена.")
        return

    card_text = format_device_card(dev)
    await callback.message.edit_text(
        card_text,
        reply_markup=get_device_card_keyboard(dev.model_id),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(F.text)
async def handle_device_search(message: Message) -> None:
    if message.text.startswith("/"):
        return

    # Индикатор поиска
    status_msg = await message.answer(f"🔍 Ищу *'{message.text}'* в каталоге Deprecio...", parse_mode="Markdown")

    matches = catalog.search_devices(message.text)
    if not matches:
        # Пробуем запросить из внешнего источника
        target = await catalog.get_or_fetch_device(message.text)
    else:
        target = matches[0]

    if not target:
        await status_msg.edit_text(
            f"🔍 По запросу *'{message.text}'* ничего не найдено.\n\n"
            "Попробуйте написать, например: `Nothing 2a`, `Galaxy S24`, `Pixel 8`, `Xiaomi 14` или `Айфон 15`.",
            parse_mode="Markdown",
        )
        return

    alternatives = [(d.model_id, d.name) for d in matches[1:6]] if len(matches) > 1 else None

    card_text = format_device_card(target)
    
    # Проверка на точное совпадение (если пользователь искал poco x6, а нашли poco x6 pro)
    from deprecio.core.fuzzy_search import normalize_search_text, calculate_match_score
    score = calculate_match_score(message.text, target.name, target.brand)
    # Если совпадение неточное (не все слова из запроса входят в имя или нет точного номера)
    q_norm = normalize_search_text(message.text)
    t_norm = normalize_search_text(target.name)
    if score < 0.90 or (q_norm not in t_norm and q_norm != t_norm):
        warning = "⚠️ *Точное совпадение не найдено, показываем ближайший вариант:*\n\n"
        card_text = warning + card_text

    await status_msg.delete()
    await message.answer(
        card_text,
        reply_markup=get_device_card_keyboard(target.model_id, alternative_matches=alternatives),
        parse_mode="Markdown",
    )
