"""Analytics and comparison HTTP contracts."""

import inspect
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.models import (
    AnalogResponse,
    AnalyticsDeviceResponse,
    CompareResponse,
    MarketCardResponse,
    MarketStatsResponse,
)
from deprecio.core.analytics_defaults import device_msrp_rub
from deprecio.core.metrics import calculate_depreciation_drop, calculate_residual_value
from deprecio.forecast.calculator import generate_price_forecast
from deprecio.models.device import Device
from deprecio.providers.base import BaseSpecsProvider
from deprecio.providers.exceptions import DeviceNotFoundError

router = APIRouter(prefix="/analytics", tags=["analytics"])
Provider = Annotated[BaseSpecsProvider, Depends(get_specs_provider)]


async def _market(provider: BaseSpecsProvider, device: Device) -> MarketStatsResponse | None:
    getter = getattr(provider, "get_market_stats", None)
    if getter is None:
        return None
    stats = getter(device)
    if inspect.isawaitable(stats):
        stats = await stats
    if stats is None:
        return None
    count = stats.clean_listings_count
    return MarketStatsResponse(
        median_price_rub=stats.median_price_rub if count else None,
        min_price_rub=stats.min_price_rub if count else None,
        p25_price_rub=stats.p25_price_rub if count else None,
        p75_price_rub=stats.p75_price_rub if count else None,
        max_price_rub=stats.max_price_rub if count else None,
        listings_count=count,
        updated_at=stats.updated_at,
    )


async def _device_response(provider: BaseSpecsProvider, device: Device) -> AnalyticsDeviceResponse:
    msrp = device_msrp_rub(device)
    market = await _market(provider, device)
    current = market.median_price_rub if market and market.listings_count else None
    forecast_summary = None
    if current is not None:
        forecast_summary = generate_price_forecast(device, current, 12).summary_verdict
    return AnalyticsDeviceResponse(
        model_id=device.model_id,
        name=device.name,
        brand=device.brand,
        tier=device.lineage.tier,
        characteristics={"chipset": device.chipset, "series": device.lineage.series,
                         "editions": [edition.edition_type for edition in device.editions]},
        msrp_rub=msrp,
        current_price_rub=current,
        residual_value_percent=calculate_residual_value(current, msrp) if current is not None else None,
        depreciation_drop_percent=calculate_depreciation_drop(current, msrp) if current is not None else None,
        forecast_summary=forecast_summary,
        market_stats=market,
    )


def _get_device(provider: BaseSpecsProvider, model_id: str) -> Device:
    try:
        return provider.get_device(model_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Device not found") from exc


@router.get("/compare", response_model=CompareResponse, responses={404: {"model": dict}, 422: {"model": dict}})
async def compare_devices(
    model_ids: Annotated[list[str], Query(min_length=2, max_length=5, description="2-5 model IDs")],
    provider: Provider,
) -> CompareResponse:
    devices = [_get_device(provider, model_id) for model_id in model_ids]
    return CompareResponse(devices=[await _device_response(provider, device) for device in devices])


@router.get("/analogs/{model_id}", response_model=AnalogResponse)
async def find_analogs(
    model_id: str,
    provider: Provider,
    tier: str | None = Query(None, description="Override target tier"),
    budget_min_rub: float | None = Query(None, ge=0),
    budget_max_rub: float | None = Query(None, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> AnalogResponse:
    source = _get_device(provider, model_id)
    if budget_min_rub is not None and budget_max_rub is not None and budget_min_rub > budget_max_rub:
        raise HTTPException(status_code=400, detail="budget_min_rub не может быть больше budget_max_rub")
    target_tier = tier or source.lineage.tier
    candidates = [device for device in provider.search_devices("") if device.lineage.tier.lower() == target_tier.lower()]
    price_target = budget_max_rub or budget_min_rub
    analogs = provider.filter_analogs(source, candidates, price_target, 1.0) if price_target is not None else [
        device for device in candidates if device.model_id != source.model_id
    ]
    if budget_min_rub is not None:
        analogs = [device for device in analogs if device_msrp_rub(device) >= budget_min_rub]
    return AnalogResponse(source_model_id=model_id, results=[await _device_response(provider, device) for device in analogs[:limit]], total=min(len(analogs), limit))


@router.get("/devices/{model_id}/market", response_model=MarketCardResponse)
async def market_card(model_id: str, provider: Provider) -> MarketCardResponse:
    device = _get_device(provider, model_id)
    market = await _market(provider, device)
    if market is None:
        market = MarketStatsResponse(median_price_rub=None, min_price_rub=None, p25_price_rub=None,
                                     p75_price_rub=None, max_price_rub=None, listings_count=0, updated_at=None)
    return MarketCardResponse(model_id=device.model_id, model_name=device.name, market_stats=market)
