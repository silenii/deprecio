"""Pydantic models shared by the HTTP API."""

from typing import Any

from pydantic import BaseModel


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


class ErrorResponse(BaseModel):
    """Stable error envelope returned by every API error handler."""

    code: str
    message: str
    details: Any | None = None
