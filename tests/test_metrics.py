"""Unit tests for core depreciation metrics and Sweet Spot analysis."""

import unittest
from deprecio.core import (
    MarketStage,
    analyze_sweet_spot,
    calculate_depreciation_drop,
    calculate_edition_gap,
    calculate_residual_value,
)


class TestCoreMetrics(unittest.TestCase):
    def test_calculate_residual_value_normal(self):
        # Телефон стоил 100 000 ₽ на старте, сейчас на вторичке 65 000 ₽
        rv = calculate_residual_value(current_price=65000, msrp_price=100000)
        self.assertEqual(rv, 65.0)

    def test_calculate_residual_value_invalid_msrp(self):
        with self.assertRaises(ValueError):
            calculate_residual_value(current_price=50000, msrp_price=0)

    def test_calculate_depreciation_drop(self):
        drop = calculate_depreciation_drop(current_price=65000, msrp_price=100000)
        self.assertEqual(drop, -35.0)

    def test_calculate_edition_gap(self):
        # Официальный Ростест/EAC: медиана 60 000 ₽
        eac_prices = [58000, 60000, 62000]
        # Китайская версия (CN): медиана 48 000 ₽ (-20% дешевле)
        cn_prices = [46000, 48000, 50000]

        gap = calculate_edition_gap(base_prices=eac_prices, comparison_prices=cn_prices)
        self.assertEqual(gap, -20.0)

    def test_calculate_edition_gap_empty(self):
        gap = calculate_edition_gap(base_prices=[], comparison_prices=[50000])
        self.assertIsNone(gap)

    def test_analyze_sweet_spot_stages(self):
        # 1. Свежий релиз (1 месяц) -> фаза быстрого падения
        fresh = analyze_sweet_spot(months_since_release=1, current_price=90000, msrp_price=100000)
        self.assertFalse(fresh.is_sweet_spot)
        self.assertEqual(fresh.market_stage, MarketStage.RAPID_DECAY)

        # 2. Зона Sweet Spot (8 месяцев) -> стабильное плато
        sweet = analyze_sweet_spot(months_since_release=8, current_price=58000, msrp_price=100000)
        self.assertTrue(sweet.is_sweet_spot)
        self.assertEqual(sweet.market_stage, MarketStage.SWEET_SPOT)
        self.assertIn("ЗОНА SWEET SPOT", sweet.advice_buyer)

        # 3. Старая модель (24 месяца) -> глубокая уценка
        legacy = analyze_sweet_spot(months_since_release=24, current_price=35000, msrp_price=100000)
        self.assertFalse(legacy.is_sweet_spot)
        self.assertEqual(legacy.market_stage, MarketStage.LEGACY_PLATEAU)


if __name__ == "__main__":
    unittest.main()
