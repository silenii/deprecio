"""Data models for Secondary Market Statistics and Aggregated Pricing."""

from datetime import date
from typing import Dict, Optional
from pydantic import BaseModel, Field
from deprecio.models.device import EditionType


class EditionMarketStats(BaseModel):
    """Статистика цен для конкретной региональной версии смартфона на вторичке."""
    edition_type: EditionType = Field(..., description="Региональная версия (Ростест, CN, Global, US)")
    count: int = Field(..., description="Количество очищенных объявлений")
    median_price_rub: float = Field(..., description="Медианная цена в рублях")
    min_price_rub: float = Field(..., description="Минимальная цена")
    max_price_rub: float = Field(..., description="Максимальная цена")
    gap_vs_eac_percent: float = Field(0.0, description="Разница цены в % по сравнению с Ростестом")


class MarketStats(BaseModel):
    """Сводная рыночная статистика по всем версиям модели."""
    model_id: str
    model_name: str
    snapshot_date: date = Field(default_factory=date.today)

    # Счётчики выборки
    total_raw_listings: int = Field(0, description="Всего объявлений до очистки")
    clean_listings_count: int = Field(0, description="После фильтрации IQR + дефектов")
    defective_count: int = Field(0, description="Отсеяно дефектных")
    outliers_count: int = Field(0, description="Отсеяно ценовых выбросов")

    # Ценовой профиль (рубли)
    min_price_rub: float = 0.0
    p25_price_rub: float = 0.0
    median_price_rub: float = 0.0
    p75_price_rub: float = 0.0
    max_price_rub: float = 0.0

    # Разбивка по версиям и состояниям
    editions: Dict[str, "EditionMarketStats"] = Field(default_factory=dict)
    condition_medians: Dict[str, float] = Field(default_factory=dict)

    @property
    def eac_median_price(self) -> Optional[float]:
        s = self.editions.get(EditionType.EAC_ROSTEST.value)
        return s.median_price_rub if s else None
