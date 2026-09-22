"""Data models for Secondary Market Listings (Avito, C2C)."""

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from .device import EditionType


class MarketPlatform(str, Enum):
    AVITO = "AVITO"
    YULA = "YULA"
    MARKETPLACE_USED = "MARKETPLACE_USED"
    OTHER = "OTHER"


class ItemCondition(str, Enum):
    """Состояние устройства по градации вторичного рынка."""
    NEW_SEALED = "NEW_SEALED"         # Новый, не вскрывался (запечатанная заводская пломба)
    LIKE_NEW = "LIKE_NEW"             # Идеальное / Как новый (в пленках, без следов)
    EXCELLENT = "EXCELLENT"           # Отличное (микроцарапины без сколов)
    GOOD = "GOOD"                     # Хорошее (заметные следы эксплуатации)
    DEFECTIVE = "DEFECTIVE"           # С дефектом (выгорание, трещина стекла, не работает FaceID/NFC)
    FOR_PARTS = "FOR_PARTS"           # На запчасти / кирпич / заблокирован


class ListingBundle(BaseModel):
    """Комплектность конкретного лота в объявлении."""
    has_original_box: bool = Field(False, description="Наличие оригинальной коробки")
    has_original_charger: bool = Field(False, description="Наличие оригинального блока быстрой зарядки")
    has_receipt: bool = Field(False, description="Наличие чека покупки / действующей гарантии")


class SecondaryListing(BaseModel):
    """Объявление о продаже смартфона на вторичном рынке (Авито)."""
    listing_id: str = Field(..., description="ID объявления на площадке")
    platform: MarketPlatform = Field(MarketPlatform.AVITO, description="Площадка (Авито и др.)")
    url: Optional[str] = Field(None, description="Ссылка на объявление")
    title: str = Field(..., description="Заголовок объявления")
    description_text: Optional[str] = Field(None, description="Полный текст описания продавца")
    price_rub: float = Field(..., description="Цена в рублях")
    city: str = Field("Россия", description="Город / регион продажи")
    
    # Распознанные параметры лота
    model_id: Optional[str] = Field(None, description="Определенная модель из каталога")
    detected_edition: Optional[EditionType] = Field(None, description="Распознанная версия (CN, EAC, US и др.)")
    ram_gb: Optional[int] = Field(None, description="Оперативная память")
    storage_gb: Optional[int] = Field(None, description="Накопитель")
    condition: ItemCondition = Field(ItemCondition.GOOD, description="Определенное состояние лота")
    bundle: ListingBundle = Field(default_factory=ListingBundle)
    battery_health_percent: Optional[int] = Field(None, description="Остаточная емкость АКБ (%)")
    
    # Статус валидации и очистки
    is_outlier: bool = Field(False, description="Помечено ли объявление как выброс / скам")
    outlier_reason: Optional[str] = Field(None, description="Причина исключения из расчета")
    published_at: Optional[date] = Field(None, description="Дата публикации объявления")
