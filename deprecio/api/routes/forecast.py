"""Price forecast endpoint."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from deprecio.api.dependencies import get_specs_provider
from deprecio.forecast.calculator import generate_price_forecast
from deprecio.providers.base import BaseSpecsProvider
from deprecio.providers.exceptions import DeviceNotFoundError

router = APIRouter(prefix="/forecast", tags=["forecast"])
Provider = Annotated[BaseSpecsProvider, Depends(get_specs_provider)]


class ForecastResponse(BaseModel):
    """JSON representation; point RV percentages use the current price base."""

    device_id: str
    device_name: str
    current_estimated_rub: float
    monthly_decay_rate: float
    sweet_spot_month: int
    points: list[dict]
    summary_verdict: str


@router.get("/{model_id}", response_model=ForecastResponse)
def get_forecast(
    model_id: str,
    provider: Provider,
    current_price_rub: Annotated[float, Query(gt=0)],
    months_horizon: Annotated[int, Query(ge=1, le=120)] = 12,
) -> ForecastResponse:
    """Generate a forecast using the shared forecasting engine."""
    try:
        device = provider.get_device(model_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Device not found") from exc
    report = generate_price_forecast(device, current_price_rub, months_horizon)
    return ForecastResponse(**asdict(report))
