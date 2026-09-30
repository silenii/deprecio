"""Единые параметры аналитики при неполных данных каталога.

Порядок выбора: явное значение устройства -> профиль бренда -> профиль Tier ->
нейтральный профиль. Даты используются только как аналитическая опора, поэтому
при отсутствии даты берётся дата, рассчитанная от текущего дня; это не выдаётся
за фактическую дату релиза. Курсы ниже являются консервативными курсами расчёта,
а не котировками биржи, и централизованы здесь для одинакового результата.
"""

from datetime import date
from typing import Optional

from deprecio.models.device import Currency, Device

DEFAULT_PROFILES = {
    "Budget": (15000.0, 4, 64, 48),
    "Mid-range": (30000.0, 6, 128, 36),
    "Sub-flagship": (55000.0, 8, 128, 24),
    "Flagship": (85000.0, 8, 256, 18),
    "Ultra-Flagship": (120000.0, 12, 256, 12),
}
BRAND_PROFILES = {
    "apple": (90000.0, 8, 128, 18),
    "samsung": (80000.0, 8, 256, 18),
    "google": (70000.0, 8, 128, 18),
}
RUB_PER_UNIT = {Currency.RUB: 1.0, Currency.USD: 92.0, Currency.EUR: 100.0, Currency.CNY: 12.7}


def convert_to_rub(amount: float, currency: Currency | str) -> float:
    """Convert a positive local MSRP to RUB using the centralized rates."""
    currency = Currency(currency)
    if amount <= 0:
        raise ValueError("MSRP должен быть положительным")
    return round(amount * RUB_PER_UNIT[currency], 2)


def default_parameters(tier: str, brand: str = "", today: Optional[date] = None) -> dict:
    """Return fallback MSRP, memory and estimated release date for analytics."""
    profile = BRAND_PROFILES.get(brand.strip().lower(), DEFAULT_PROFILES.get(tier, DEFAULT_PROFILES["Mid-range"]))
    msrp, ram, storage, age_months = profile
    current = today or date.today()
    month = current.month - age_months
    year = current.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return {"msrp_rub": msrp, "ram_gb": ram, "storage_gb": storage, "release_date": date(year, month, 1)}


def device_msrp_rub(device: Device) -> float:
    """Get the first known MSRP in RUB, otherwise use the shared profile."""
    for edition in device.editions:
        for variant in edition.memory_variants:
            if variant.msrp_local > 0:
                return convert_to_rub(variant.msrp_local, variant.currency)
    return default_parameters(device.lineage.tier, device.brand)["msrp_rub"]
