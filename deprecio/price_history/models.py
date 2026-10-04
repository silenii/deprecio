"""Domain model for a market price snapshot."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from deprecio.harvester.models import MarketStats


class PriceHistoryPoint(BaseModel):
    model_id: str
    timestamp: datetime
    source: str
    currency: str = "RUB"
    sample_size: int = Field(ge=0)
    median_price_rub: float = Field(ge=0)
    min_price_rub: float = Field(ge=0)
    max_price_rub: float = Field(ge=0)
    p25_price_rub: float = Field(ge=0)
    p75_price_rub: float = Field(ge=0)
    defective_count: int = Field(default=0, ge=0)
    outliers_count: int = Field(default=0, ge=0)
    condition_medians: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_market_stats(cls, stats: MarketStats, source: str, timestamp: datetime) -> "PriceHistoryPoint":
        return cls(
            model_id=stats.model_id,
            timestamp=timestamp.astimezone(timezone.utc),
            source=source,
            sample_size=stats.clean_listings_count,
            median_price_rub=stats.median_price_rub,
            min_price_rub=stats.min_price_rub,
            max_price_rub=stats.max_price_rub,
            p25_price_rub=stats.p25_price_rub,
            p75_price_rub=stats.p75_price_rub,
            defective_count=stats.defective_count,
            outliers_count=stats.outliers_count,
            condition_medians=stats.condition_medians,
        )
