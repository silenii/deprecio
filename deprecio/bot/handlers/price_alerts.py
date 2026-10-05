"""Telegram commands for price subscriptions."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from deprecio.price_alerts import PriceAlertLimitError, SQLitePriceAlertRepository
from deprecio.providers import CachedSpecsProvider

router = Router(name="price_alerts_router")


@router.message(Command("price_alert"))
async def create_alert(message: Message, price_alerts: SQLitePriceAlertRepository, catalog: CachedSpecsProvider) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: /price_alert model_id цена")
        return
    try:
        price = float(parts[2].replace(",", "."))
        if not catalog.get_device(parts[1]):
            raise ValueError("модель не найдена")
        price_alerts.upsert(message.from_user.id, parts[1], price)
    except (ValueError, PriceAlertLimitError) as exc:
        await message.answer(f"Не удалось создать подписку: {exc}")
        return
    await message.answer("Подписка включена.")


@router.message(Command("price_alerts"))
async def list_alerts(message: Message, price_alerts: SQLitePriceAlertRepository) -> None:
    alerts = price_alerts.list(message.from_user.id)
    await message.answer("\n".join(f"{a.model_id}: {a.target_price_rub:g} руб. ({'вкл' if a.enabled else 'выкл'})" for a in alerts) or "Подписок нет.")


async def _toggle(message: Message, repository: SQLitePriceAlertRepository, enabled: bool) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not repository.set_enabled(message.from_user.id, parts[1], enabled):
        await message.answer("Формат: /price_alert_on model_id" if enabled else "Формат: /price_alert_off model_id")
        return
    await message.answer("Подписка включена." if enabled else "Подписка отключена.")


@router.message(Command("price_alert_on"))
async def enable_alert(message: Message, price_alerts: SQLitePriceAlertRepository) -> None:
    await _toggle(message, price_alerts, True)


@router.message(Command("price_alert_off"))
async def disable_alert(message: Message, price_alerts: SQLitePriceAlertRepository) -> None:
    await _toggle(message, price_alerts, False)


@router.message(Command("price_alert_delete"))
async def delete_alert(message: Message, price_alerts: SQLitePriceAlertRepository) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not price_alerts.delete(message.from_user.id, parts[1]):
        await message.answer("Формат: /price_alert_delete model_id")
        return
    await message.answer("Подписка удалена.")
