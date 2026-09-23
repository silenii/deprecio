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
    """Сводная аналитическая статистика по вторичному рынку смартфона."""
    model_id: str = Field(..., description="ID модели устройства")
    model_name: str = Field(..., description="Название модели устройства")
    total_raw_listings: int = Field(..., description="Всего собрано объявлений в снапшоте")
    clean_listings_count: int = Field(..., description="Количество валидных объявлений после очистки")
    defective_count: int = Field(..., description="Отсеяно дефектных / заблокированных лотов")
    outliers_count: int = Field(..., description="Отсеяно статистических ценовых выбросов IQR")
    
    # Ключевые ценовые метрики
    min_price_rub: float = Field(..., description="Минимальная цена валидного лота")
    p25_price_rub: float = Field(..., description="25-й перцентиль цены (выгодный порог)")
    median_price_rub: float = Field(..., description="Медианная рыночная цена")
    p75_price_rub: float = Field(..., description="75-й перцентиль цены (верхняя граница нормы)")
    max_price_rub: float = Field(..., description="Максимальная адекватная цена")
    
    # Распределение по региональным версиям
    editions: Dict[str, EditionMarketStats] = Field(default_factory=dict, description="Метрики по версиям (CN, EAC, Global)")
    
    # Распределение по состояниям
    condition_medians: Dict[str, float] = Field(default_factory=dict, description="Медианные цены по состояниям")
    
    updated_at: date = Field(default_factory=date.today, description="Дата актуализации снапшота")
