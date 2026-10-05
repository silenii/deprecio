"""Price alert evaluation, independent from Telegram."""

from typing import Any

from .models import PriceAlertEvent
from .repository import SQLitePriceAlertRepository


class PriceAlertService:
    def __init__(self, repository: SQLitePriceAlertRepository, provider: Any) -> None:
        self.repository = repository
        self.provider = provider

    async def check(self) -> list[PriceAlertEvent]:
        events: list[PriceAlertEvent] = []
        for alert in self.repository.due():
            device = self.provider.get_device(alert.model_id)
            stats = await self.provider.get_market_stats(device)
            price = getattr(stats, "median_price_rub", 0) or 0
            if price <= 0:
                continue
            notify = price <= alert.target_price_rub and price != alert.last_notified_price_rub
            self.repository.mark_checked(alert, price, notify)
            if notify:
                events.append(PriceAlertEvent(alert.user_id, alert.model_id, price, alert.target_price_rub))
        return events
