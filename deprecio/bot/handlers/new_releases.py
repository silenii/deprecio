"""Handler for recently released smartphones and their Sweet Spot forecast."""

from datetime import date, timedelta
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from deprecio.bot.keyboards import get_back_keyboard
from deprecio.core import MarketStage, analyze_sweet_spot
from deprecio.forecast import generate_price_forecast
from deprecio.models.device import Device
from deprecio.providers import CachedSpecsProvider

router = Router(name="new_releases_router")


def _release_date(device: Device) -> Optional[date]:
    dates = [edition.release_date for edition in device.editions if edition.release_date]
    return min(dates) if dates else None


def _months_since(release_date: date, today: date) -> int:
    return max(0, (today.year - release_date.year) * 12 + today.month - release_date.month)


def _month_label(iso_date: str) -> str:
    target = date.fromisoformat(iso_date)
    months = ("января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря")
    return f"{months[target.month - 1]} {target.year}"


@router.message(Command("new"))
@router.message(F.text == "🆕 Новинки")
async def handle_new_releases(message: Message, catalog: CachedSpecsProvider) -> None:
    today = date.today()
    cutoff = today - timedelta(days=90)
    devices = []
    for device in catalog.search_devices(""):
        released = _release_date(device)
        if released and released >= cutoff:
            devices.append((released, device))

    devices.sort(key=lambda item: item[0], reverse=True)
    if not devices:
        await message.answer("🆕 За последние 3 месяца новых моделей не найдено.", reply_markup=get_back_keyboard())
        return

    blocks = ["🆕 **Новинки за последние 3 месяца**"]
    for released, device in devices:
        months_old = _months_since(released, today)
        profile = device.forecast_profile
        expected_months = profile.expected_sweet_spot_months if profile else 6
        stats = await catalog.get_market_stats(device)
        current_price = stats.median_price_rub
        analysis = analyze_sweet_spot(months_old, current_price, current_price / 0.6,
                                      expected_plateau_months=expected_months)
        forecast = generate_price_forecast(device, current_price, months_horizon=expected_months,
                                            base_date=today)
        sweet_point = next(point for point in forecast.points if point.months_ahead == expected_months)
        months_left = max(0, expected_months - months_old)
        phase = {
            MarketStage.RAPID_DECAY: "📉 Быстрое падение цены",
            MarketStage.APPROACHING_PLATEAU: "📊 Приближение к плато",
        }.get(analysis.market_stage, analysis.market_stage.value)
        drop = round((sweet_point.predicted_price_rub / current_price - 1) * 100)
        blocks.append(
            f"🆕 **{device.brand} {device.name}** (вышел {months_old} мес. назад)\n"
            f"• Фаза: {phase}\n"
            f"• Войдёт в Sweet Spot через: ~{months_left} мес. (≈ {_month_label(sweet_point.target_date)})\n"
            f"• Текущая медиана Авито: ≈ {current_price:,.0f} ₽\n"
            f"• Прогноз в Sweet Spot: ≈ {sweet_point.predicted_price_rub:,.0f} ₽ ({drop:+d}%)"
        )

    await message.answer("\n\n".join(blocks), reply_markup=get_back_keyboard(), parse_mode="Markdown")
