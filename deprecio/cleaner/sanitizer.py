"""Sanitizer and Statistical Outlier Filter for Secondary Market Listings."""

from typing import List, Tuple
from deprecio.models.listing import ItemCondition, SecondaryListing
from .rules import detect_defect_from_text, detect_edition_from_text


class ListingSanitizer:
    """Пайплайн очистки и валидации объявлений со вторичного рынка."""

    @staticmethod
    def classify_and_filter_defects(listing: SecondaryListing) -> SecondaryListing:
        """Анализирует текст и помечает дефектные/заблокированные объявления."""
        full_text = f"{listing.title} {listing.description_text or ''}"

        # Определение региональной версии, если не была указана
        if not listing.detected_edition:
            listing.detected_edition = detect_edition_from_text(full_text)

        # Проверка на дефекты и стоп-слова
        defect_found = detect_defect_from_text(full_text)
        if defect_found:
            listing.condition = ItemCondition.DEFECTIVE
            listing.is_outlier = True
            listing.outlier_reason = f"Обнаружен маркер дефекта: '{defect_found}'"
            return listing

        # Отсечение заведомо фиктивных цен (заглушки '1 рубль', 'цена за чехол')
        if listing.price_rub < 3000:
            listing.is_outlier = True
            listing.outlier_reason = f"Нереалистично низкая цена: {listing.price_rub} ₽"

        return listing

    @staticmethod
    def filter_price_outliers_iqr(
        listings: List[SecondaryListing],
        iqr_multiplier: float = 1.5,
    ) -> Tuple[List[SecondaryListing], List[SecondaryListing]]:
        """
        Статистическая фильтрация ценовых аномалий методом межквартильного размаха (IQR).
        
        Возвращает кортеж: (валидные_объявления, выбросы).
        """
        # Берем только недефектные объявления для расчета квантилей
        candidates = [item for item in listings if not item.is_outlier]
        if len(candidates) < 4:
            # Слишком малая выборка для расчета статистического IQR
            valid = [item for item in listings if not item.is_outlier]
            outliers = [item for item in listings if item.is_outlier]
            return valid, outliers

        prices = sorted([item.price_rub for item in candidates])
        n = len(prices)

        q1 = prices[int(n * 0.25)]
        q3 = prices[int(n * 0.75)]
        iqr = q3 - q1

        lower_bound = max(0, q1 - iqr_multiplier * iqr)
        upper_bound = q3 + iqr_multiplier * iqr

        valid_items: List[SecondaryListing] = []
        outlier_items: List[SecondaryListing] = []

        for item in listings:
            if item.is_outlier:
                outlier_items.append(item)
                continue

            if item.price_rub < lower_bound or item.price_rub > upper_bound:
                item.is_outlier = True
                item.outlier_reason = (
                    f"Цена {item.price_rub} ₽ вне диапазона IQR [{lower_bound:.0f} - {upper_bound:.0f} ₽]"
                )
                outlier_items.append(item)
            else:
                valid_items.append(item)

        return valid_items, outlier_items
