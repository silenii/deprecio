"""Pydantic models shared by the HTTP API."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """A single point on the price forecast curve."""

    months_ahead: int
    target_date: str
    predicted_price_rub: float
    predicted_rv_percent: float
    trigger_event: str | None = None


class ForecastResponse(BaseModel):
    """JSON representation of a device price forecast."""

    device_id: str
    device_name: str
    current_estimated_rub: float
    monthly_decay_rate: float
    sweet_spot_month: int
    points: list[ForecastPoint]
    summary_verdict: str
    is_heuristic: bool = True


class ErrorResponse(BaseModel):
    """Stable error envelope returned by every API error handler."""

    code: str
    message: str
    details: Any | None = None


class MarketStatsResponse(BaseModel):
    """Public market snapshot; missing prices indicate no usable listings."""

    median_price_rub: float | None
    min_price_rub: float | None
    p25_price_rub: float | None
    p75_price_rub: float | None
    max_price_rub: float | None
    listings_count: int
    unknown_condition_count: int = 0
    memory_configuration: str | None = None
    condition_medians: dict[str, float] = Field(default_factory=dict)
    updated_at: date | None


class AnalyticsDeviceResponse(BaseModel):
    """Normalized device analytics shared by comparison and analog responses."""

    model_id: str
    name: str
    brand: str
    tier: str
    estimated_fields: list[str] = Field(default_factory=list)
    characteristics: dict[str, Any]
    msrp_rub: float
    current_price_rub: float | None
    residual_value_percent: float | None
    depreciation_drop_percent: float | None
    forecast_summary: str | None
    forecast_is_heuristic: bool = True
    market_stats: MarketStatsResponse | None


class CompareResponse(BaseModel):
    """Comparison of a bounded set of catalog devices."""

    devices: list[AnalyticsDeviceResponse]


class AnalogResponse(BaseModel):
    """Catalog analogs selected by tier and optional budget."""

    source_model_id: str
    results: list[AnalyticsDeviceResponse]
    total: int


class MarketCardResponse(BaseModel):
    """Market card for one device, including empty-data responses."""

    model_id: str
    model_name: str
    market_stats: MarketStatsResponse
