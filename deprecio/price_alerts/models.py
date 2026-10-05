"""Domain models for price alerts."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PriceAlert:
    user_id: int
    model_id: str
    target_price_rub: float
    enabled: bool
    created_at: datetime
    last_notified_price_rub: float | None = None
    last_checked_at: datetime | None = None


@dataclass(frozen=True)
class PriceAlertEvent:
    user_id: int
    model_id: str
    current_price_rub: float
    target_price_rub: float
