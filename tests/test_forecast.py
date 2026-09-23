"""Unit tests for the price decay forecast engine."""

import unittest
from datetime import date
from deprecio.forecast import generate_price_forecast
from deprecio.models.device import Device, DeviceLineage, ForecastProfile


class TestForecastCalculator(unittest.TestCase):
    def setUp(self):
        self.device = Device(
            model_id="test-phone",
            name="Тестовый Смартфон",
            brand="TestBrand",
            lineage=DeviceLineage(series="Test Series", tier="Flagship"),
            forecast_profile=ForecastProfile(
                brand_decay_monthly_rate=0.05,
                expected_sweet_spot_months=6,
                historical_plateau_rv=0.55,
            ),
        )

    def test_forecast_generates_points_and_drops(self):
        report = generate_price_forecast(
            device=self.device,
            current_price_rub=100000.0,
            months_horizon=12,
            base_date=date(2026, 9, 1),
        )

        self.assertEqual(report.device_id, "test-phone")
        self.assertEqual(len(report.points), 6)  # milestones: 1, 2, 3, 6, 9, 12

        # Проверка, что цена монотонно убывает со временем
        prices = [p.predicted_price_rub for p in report.points]
        for i in range(len(prices) - 1):
            self.assertGreaterEqual(prices[i], prices[i + 1])

        # Через 12 месяцев цена должна приблизиться к плато (55 000 ₽)
        last_point = report.points[-1]
        self.assertLess(last_point.predicted_price_rub, 100000.0)
        self.assertGreaterEqual(last_point.predicted_price_rub, 50000.0)

    def test_forecast_detects_seasonal_triggers(self):
        # Базовая дата: сентябрь 2026. Через 2 месяца -> ноябрь 2026 (11.11)
        report = generate_price_forecast(
            device=self.device,
            current_price_rub=80000.0,
            base_date=date(2026, 9, 1),
        )

        point_m2 = next(p for p in report.points if p.months_ahead == 2)
        self.assertIn("11.11", point_m2.trigger_event)

        point_m3 = next(p for p in report.points if p.months_ahead == 3)
        self.assertIn("Новогодние скидки", point_m3.trigger_event)


if __name__ == "__main__":
    unittest.main()
