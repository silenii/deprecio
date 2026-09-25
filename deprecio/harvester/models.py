"""Data models for Secondary Market Statistics and Aggregated Pricing."""

from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from deprecio.models.device import EditionType
from deprecio.models.listing import ItemCondition


class EditionMarketStats(BaseModel):
    """Статистика цен для конкретной региональной версии смартфона на вторичке."""
    edition_type: EditionType = Field(..., description="Региональная версия (Ростест, CN, Global, US)")
    count: int = Field(..., description="Количество очищенных объявлений")
    median_price_rub: float = Field(..., description="Медианная цена в рублях")
    min_price_rub: float = Field(..., description="Минимальная цена")
    max_price_rub: float = Field(..., description="Максимальная цена")
    gap_vs_eac_percent: float = Field(0.0, description="Разница цены в % по сравнению с Ростестом")


class MarketStats(BaseModel):
    """Сводная рыночная статистика по всем версиям конкретной модели."""
    model_id: str = Field(..., description="Идентификатор модели из каталога")
    model_name: str = Field(..., description="Полное название модели")
    snapshot_date: date = Field(..., description="Дата снятия среза данных")
    total_listings: int = Field(0, description="Общее число объявлений до очистки")
    clean_listings: int = Field(0, description="Число объявлений после фильтрации")
    by_edition: Dict[EditionType, EditionMarketStats] = Field(
        default_factory=dict,
        description="Статистика по каждой региональной версии"
    )

    @property
    def eac_median_price(self) -> Optional[float]:
        """Медианная цена Ростест-версии или None если нет данных."""
        stats = self.by_edition.get(EditionType.EAC_ROSTEST)
        return stats.median_price_rub if stats else None
