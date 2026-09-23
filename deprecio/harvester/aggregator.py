"""Secondary Market Data Aggregator and Price Sanitization Pipeline."""

import statistics
from datetime import date
from typing import Dict, List, Optional
from deprecio.cleaner import ListingSanitizer
from deprecio.models.device import Device, EditionType
from deprecio.models.listing import ItemCondition, SecondaryListing
from .models import EditionMarketStats, MarketStats


class MarketAggregator:
    """Агрегатор рыночной статистики цен объявлений со вторичного рынка."""

    @classmethod
    def aggregate_market_data(
        cls,
        device: Device,
        raw_listings: List[SecondaryListing],
    ) -> MarketStats:
        """
        Полный цикл очистки и аналитики выборки:
        1. Отсечение дефектов и заблокированных устройств
        2. Фильтрация ценовых аномалий и спама методом IQR
        3. Расчет медианной цены, перцентилей и разницы версий (CN vs EAC)
        """
        total_raw = len(raw_listings)

        # 1. Классификация и отсечение дефектов
        classified_listings: List[SecondaryListing] = []
        defective_count = 0
        for item in raw_listings:
            clean_item = ListingSanitizer.classify_and_filter_defects(item)
            if clean_item.is_outlier and clean_item.condition == ItemCondition.DEFECTIVE:
                defective_count += 1
            classified_listings.append(clean_item)

        # 2. IQR фильтрация аномальных цен
        valid_listings, outliers = ListingSanitizer.filter_price_outliers_iqr(classified_listings)
        outliers_count = len(outliers) - defective_count

        if not valid_listings:
            # Если после очистки ничего не осталось, берем сырые недефектные цены
            valid_listings = [it for it in classified_listings if it.condition != ItemCondition.DEFECTIVE]
            if not valid_listings:
                valid_listings = raw_listings

        prices = sorted([item.price_rub for item in valid_listings])
        n = len(prices)

        min_price = prices[0]
        max_price = prices[-1]
        median_price = statistics.median(prices)
        p25_price = prices[max(0, int(n * 0.25))]
        p75_price = prices[min(n - 1, int(n * 0.75))]

        # 3. Анализ по региональным версиям (Ростест, Global, CN, US)
        editions_stats: Dict[str, EditionMarketStats] = {}
        eac_median: Optional[float] = None

        # Сначала находим опорную медиану Ростеста
        eac_items = [it for it in valid_listings if it.detected_edition == EditionType.EAC_ROSTEST]
        if eac_items:
            eac_prices = [it.price_rub for it in eac_items]
            eac_median = statistics.median(eac_prices)
            editions_stats[EditionType.EAC_ROSTEST.value] = EditionMarketStats(
                edition_type=EditionType.EAC_ROSTEST,
                count=len(eac_items),
                median_price_rub=round(eac_median / 100) * 100,
                min_price_rub=min(eac_prices),
                max_price_rub=max(eac_prices),
                gap_vs_eac_percent=0.0,
            )

        # Анализ остальных версий относительно Ростеста
        for ed_type in [EditionType.GLOBAL_EU, EditionType.CN, EditionType.US]:
            ed_items = [it for it in valid_listings if it.detected_edition == ed_type]
            if ed_items:
                ed_prices = [it.price_rub for it in ed_items]
                ed_med = statistics.median(ed_prices)
                gap = 0.0
                if eac_median and eac_median > 0:
                    gap = round(((ed_med - eac_median) / eac_median) * 100, 1)

                editions_stats[ed_type.value] = EditionMarketStats(
                    edition_type=ed_type,
                    count=len(ed_items),
                    median_price_rub=round(ed_med / 100) * 100,
                    min_price_rub=min(ed_prices),
                    max_price_rub=max(ed_prices),
                    gap_vs_eac_percent=gap,
                )

        # 4. Анализ по состояниям (Как новый, Отличное, Хорошее)
        condition_medians: Dict[str, float] = {}
        for cond in [ItemCondition.LIKE_NEW, ItemCondition.EXCELLENT, ItemCondition.GOOD]:
            cond_items = [it for it in valid_listings if it.condition == cond]
            if cond_items:
                condition_medians[cond.value] = round(statistics.median([it.price_rub for it in cond_items]) / 100) * 100

        return MarketStats(
            model_id=device.model_id,
            model_name=device.name,
            total_raw_listings=total_raw,
            clean_listings_count=len(valid_listings),
            defective_count=defective_count,
            outliers_count=max(0, outliers_count),
            min_price_rub=round(min_price / 100) * 100,
            p25_price_rub=round(p25_price / 100) * 100,
            median_price_rub=round(median_price / 100) * 100,
            p75_price_rub=round(p75_price / 100) * 100,
            max_price_rub=round(max_price / 100) * 100,
            editions=editions_stats,
            condition_medians=condition_medians,
            updated_at=date.today(),
        )
