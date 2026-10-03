"""Price forecast endpoint."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.models import ForecastResponse
from deprecio.forecast.calculator import generate_price_forecast
from deprecio.providers.base import BaseSpecsProvider
from deprecio.providers.exceptions import DeviceNotFoundError

router = APIRouter(prefix="/forecast", tags=["forecast"])
Provider = Annotated[BaseSpecsProvider, Depends(get_specs_provider)]


@router.get("/{model_id}", response_model=ForecastResponse)
def get_forecast(
    model_id: str,
    provider: Provider,
    current_price_rub: Annotated[float, Query()],
    months_horizon: Annotated[int, Query()] = 12,
) -> ForecastResponse:
    """Generate a forecast using the shared forecasting engine."""
    try:
        device = provider.get_device(model_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Device not found") from exc
    try:
        if months_horizon > 120:
            raise ValueError("Горизонт прогноза не может превышать 120 месяцев.")
        report = generate_price_forecast(device, current_price_rub, months_horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ForecastResponse(**asdict(report))
