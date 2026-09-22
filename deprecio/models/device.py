"""Data models for Smartphones, Regional Editions, and Hardware Specs."""

from datetime import date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Currency(str, Enum):
    CNY = "CNY"
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"


class EditionType(str, Enum):
    """Regional edition / version of the smartphone."""
    CN = "CN"                   # Китайская версия
    EAC_ROSTEST = "EAC_ROSTEST" # Ростест / ЕАС (официальная в РФ)
    GLOBAL_EU = "GLOBAL_EU"     # Глобальная европейская версия
    US = "US"                   # Версия для рынка США
    IN = "IN"                   # Индийская версия
    OTHER = "OTHER"             # Другой регион


class BundleContents(BaseModel):
    """Комплектация коробки устройства."""
    has_charger: bool = Field(True, description="Наличие зарядного блока в коробке")
    charger_wattage_w: Optional[int] = Field(None, description="Мощность комплектного блока (Вт)")
    has_cable: bool = Field(True, description="Наличие кабеля зарядки")
    has_case: bool = Field(False, description="Наличие комплектного чехла")
    has_box: bool = Field(True, description="Наличие заводской коробки")


class HardwareSpecs(BaseModel):
    """Региональные аппаратные отличия."""
    has_band_20: bool = Field(True, description="Поддержка LTE Band 20 (важно для РФ вне мегаполисов)")
    has_band_7: bool = Field(True, description="Поддержка LTE Band 7")
    has_band_3: bool = Field(True, description="Поддержка LTE Band 3")
    has_esim: bool = Field(False, description="Поддержка виртуальной карты eSIM")
    sim_slots: str = Field("2x NanoSIM", description="Конфигурация SIM (2x NanoSIM, 1x NanoSIM + eSIM, eSIM only)")
    has_nfc: bool = Field(True, description="Наличие NFC модуля")
    display_pwm_hz: Optional[int] = Field(None, description="Частота ШИМ дисплея (Гц)")


class MemoryVariant(BaseModel):
    """Конфигурация памяти и стартовая цена."""
    ram_gb: int = Field(..., description="Объем оперативной памяти (ГБ)")
    storage_gb: int = Field(..., description="Объем накопителя (ГБ)")
    msrp_local: float = Field(..., description="Официальная стартовая розничная цена")
    currency: Currency = Field(..., description="Валюта стартовой цены")


class RegionalEdition(BaseModel):
    """Региональная версия конкретной модели смартфона."""
    edition_type: EditionType = Field(..., description="Тип версии (CN, EAC_ROSTEST, GLOBAL_EU, US, IN)")
    announced: bool = Field(True, description="Анонсирована ли версия")
    release_date: Optional[date] = Field(None, description="Дата старта продаж")
    os_name: Optional[str] = Field(None, description="Предустановленная ОС/оболочка")
    hardware: HardwareSpecs = Field(default_factory=HardwareSpecs)
    bundle: BundleContents = Field(default_factory=BundleContents)
    memory_variants: List[MemoryVariant] = Field(default_factory=list)


class DeviceLineage(BaseModel):
    """Иерархия модели и поколение."""
    series: str = Field(..., description="Название линейки (напр. Number, Ultra, Pro)")
    tier: str = Field("Flagship", description="Класс (Flagship, Sub-flagship, Mid-range, Budget)")
    predecessor_id: Optional[str] = Field(None, description="Идентификатор модели прошлого поколения")


class ForecastProfile(BaseModel):
    """Параметры предиктивной модели уценки."""
    brand_decay_monthly_rate: float = Field(0.045, description="Ожидаемый темп уценки в месяц (% от текущей)")
    expected_sweet_spot_months: int = Field(6, description="Срок выхода на ценовое плато (мес)")
    historical_plateau_rv: float = Field(0.60, description="Типичная остаточная стоимость на плато (60% = 0.60)")


class Device(BaseModel):
    """Основная модель смартфона в каталоге Deprecio."""
    model_id: str = Field(..., description="Уникальный слаг, напр. 'brand-model'")
    name: str = Field(..., description="Полное название модели")
    brand: str = Field(..., description="Производитель")
    chipset: Optional[str] = Field(None, description="Процессор / SoC")
    lineage: DeviceLineage
    editions: List[RegionalEdition] = Field(default_factory=list)
    forecast_profile: Optional[ForecastProfile] = None
