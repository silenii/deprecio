"""Device and Market Data Models."""

from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Currency(str, Enum):
    CNY = "CNY"
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"


class MarketType(str, Enum):
    CN = "CN"
    GLOBAL = "GLOBAL"
    RU = "RU"


class MemoryVariant(BaseModel):
    """Specific RAM/Storage tier of a device."""
    ram_gb: int = Field(..., description="RAM size in gigabytes")
    storage_gb: int = Field(..., description="Internal storage size in gigabytes")
    msrp: float = Field(..., description="Official launch retail price")
    currency: Currency = Field(..., description="Currency of launch MSRP")


class MarketVariant(BaseModel):
    """Market-specific details (CN vs Global)."""
    market: MarketType
    announced: bool = True
    release_date: Optional[date] = None
    os_name: Optional[str] = None
    has_band_20: bool = False
    has_esim: bool = False
    variants: List[MemoryVariant] = Field(default_factory=list)


class DeviceLineage(BaseModel):
    """Historical context and lineage of the device."""
    series: str = Field(..., description="e.g. X-Series, Galaxy S, Xiaomi Number")
    tier: str = Field("Flagship", description="Flagship, Sub-flagship, Mid-range, Budget")
    predecessor_id: Optional[str] = Field(None, description="Model ID of the previous generation")


class ForecastProfile(BaseModel):
    """Parameters for price decay forecasting."""
    brand_decay_monthly_rate: float = Field(0.045, description="Expected monthly depreciation %")
    expected_sweet_spot_months: int = Field(6, description="Months until price plateau")
    historical_plateau_rv: float = Field(0.60, description="Typical residual value at plateau (e.g. 60%)")


class Device(BaseModel):
    """Primary Device Model."""
    model_id: str = Field(..., description="Unique slug, e.g. 'vivo-x500'")
    name: str = Field(..., description="Full human-readable name, e.g. 'vivo X500'")
    brand: str = Field(..., description="Brand name, e.g. 'vivo'")
    chipset: Optional[str] = Field(None, description="SoC, e.g. 'Dimensity 9400+'")
    lineage: DeviceLineage
    markets: List[MarketVariant] = Field(default_factory=list)
    forecast_profile: Optional[ForecastProfile] = None
