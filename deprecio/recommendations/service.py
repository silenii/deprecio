"""Explainable recommendation service built on the existing catalog and analytics."""

import inspect
from datetime import date
from typing import Any

from deprecio.core.analytics_defaults import device_msrp_rub
from deprecio.models.device import Device
from deprecio.providers.base import BaseSpecsProvider


def _value(device: Device, path: str) -> Any:
    value: Any = device
    for part in path.split("."):
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _release_year(device: Device) -> int | None:
    dates = [edition.release_date for edition in device.editions if edition.release_date]
    return min(dates).year if dates else None


class RecommendationService:
    """Select and rank devices using deterministic, inspectable score components."""

    def __init__(self, provider: BaseSpecsProvider, today: date | None = None) -> None:
        self.provider = provider
        self.today = today or date.today()

    async def _price(self, device: Device) -> tuple[float | None, str]:
        getter = getattr(self.provider, "get_market_stats", None)
        if getter:
            stats = getter(device)
            if inspect.isawaitable(stats):
                stats = await stats
            if stats and stats.median_price_rub > 0 and stats.clean_listings_count > 0:
                return stats.median_price_rub, "market_median"
        try:
            return device_msrp_rub(device), "msrp_fallback"
        except (TypeError, ValueError):
            return None, "unavailable"

    async def recommend(
        self,
        *,
        budget_min_rub: float | None = None,
        budget_max_rub: float | None = None,
        tier: str | None = None,
        brand: str | None = None,
        release_year: int | None = None,
        min_storage_gb: int | None = None,
        required_specs: dict[str, Any] | None = None,
        preferred_specs: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        if budget_min_rub is not None and budget_max_rub is not None and budget_min_rub > budget_max_rub:
            raise ValueError("budget_min_rub не может быть больше budget_max_rub")
        devices = self.provider.search_devices("")
        required_specs = required_specs or {}
        preferred_specs = preferred_specs or {}
        results: list[dict[str, Any]] = []
        insufficient: list[dict[str, Any]] = []
        for device in devices:
            if tier and device.lineage.tier.lower() != tier.lower():
                continue
            if brand and device.brand.lower() != brand.lower():
                continue
            year = _release_year(device)
            if release_year and year != release_year:
                continue
            storage = max((v.storage_gb for e in device.editions for v in e.memory_variants), default=None)
            if min_storage_gb and (storage is None or storage < min_storage_gb):
                continue
            if any(_value(device, key) != expected for key, expected in required_specs.items()):
                continue
            price, price_source = await self._price(device)
            item = {"device": device, "price_rub": price, "price_source": price_source}
            if price is None:
                insufficient.append(item)
                continue
            in_budget = (budget_min_rub is None or price >= budget_min_rub) and (budget_max_rub is None or price <= budget_max_rub)
            if not in_budget:
                continue
            freshness = max(0.0, min(1.0, (self.today.year - (year or self.today.year) + 1) / 6))
            freshness = 1.0 - freshness
            residual = max(0.0, min(1.0, price / device_msrp_rub(device)))
            matched = sum(_value(device, key) == expected for key, expected in preferred_specs.items())
            spec_score = matched / len(preferred_specs) if preferred_specs else 1.0
            budget_score = 1.0 if budget_min_rub is None and budget_max_rub is None else 1.0 - abs(price - (budget_max_rub or price)) / max(budget_max_rub or price, 1)
            components = {"budget": round(max(0.0, budget_score), 4), "freshness": round(freshness, 4), "residual_value": round(residual, 4), "specifications": round(spec_score, 4)}
            item["score"] = round(sum(components.values()) / 4, 4)
            item["score_components"] = components
            results.append(item)
        results.sort(key=lambda item: item["score"], reverse=True)
        return {"results": results[:limit], "insufficient_data": insufficient, "total": len(results)}
