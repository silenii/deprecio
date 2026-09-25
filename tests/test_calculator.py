"""Unit tests for price decay forecasting calculator."""

import unittest
from datetime import date
from deprecio.forecast.calculator import generate_price_forecast, DeviceForecastReport
from deprecio.models.device import Device, ForecastProfile, DeviceLineage


class TestGeneratePriceForecast(unittest.TestCase):
    """Test cases for generate_price_forecast function."""

    def setUp(self):
        """Set up test fixtures."""
        self.lineage = DeviceLineage(series="Test", tier="Flagship")
        self.base_date = date(2026, 1, 15)

    def test_forecast_with_default_profile_does_not_crash(self):
        """Test that function doesn't crash with ForecastProfile() defaults."""
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=ForecastProfile(),
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=12,
            base_date=self.base_date,
        )

        self.assertIsInstance(report, DeviceForecastReport)
        self.assertEqual(report.device_id, "test-device")
        self.assertEqual(report.device_name, "Test Device")
        self.assertEqual(report.current_estimated_rub, 60000)
        self.assertEqual(len(report.points), 12)

    def test_forecast_points_structure(self):
        """Test that all forecast points are properly structured."""
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=ForecastProfile(),
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=6,
            base_date=self.base_date,
        )

        self.assertEqual(len(report.points), 6)

        for i, point in enumerate(report.points, start=1):
            self.assertEqual(point.months_ahead, i)
            self.assertIsNotNone(point.target_date)
            self.assertGreater(point.predicted_price_rub, 0)
            self.assertGreater(point.predicted_rv_percent, 0)

    def test_sweet_spot_trigger_event(self):
        """Test that 'Sweet Spot' trigger is set at expected_sweet_spot_months."""
        profile = ForecastProfile(expected_sweet_spot_months=3)
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=profile,
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=6,
            base_date=self.base_date,
        )

        # Find month 3 point
        sweet_spot_point = next(p for p in report.points if p.months_ahead == 3)
        self.assertEqual(sweet_spot_point.trigger_event, "Sweet Spot")

        # Other months should have None trigger
        other_points = [p for p in report.points if p.months_ahead != 3]
        for point in other_points:
            self.assertIsNone(point.trigger_event)

    def test_summary_verdict_slow_decay(self):
        """Test summary verdict for decay_rate < 0.03 (slow)."""
        profile = ForecastProfile(brand_decay_monthly_rate=0.02)
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=profile,
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=3,
            base_date=self.base_date,
        )

        self.assertIn("Медленная амортизация", report.summary_verdict)
        self.assertIn("хорошо держит цену", report.summary_verdict)

    def test_summary_verdict_standard_decay(self):
        """Test summary verdict for 0.03 <= decay_rate < 0.06 (standard)."""
        profile = ForecastProfile(brand_decay_monthly_rate=0.045)
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=profile,
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=3,
            base_date=self.base_date,
        )

        self.assertIn("Стандартная амортизация", report.summary_verdict)
        self.assertIn("типичная для флагманов", report.summary_verdict)

    def test_summary_verdict_fast_decay(self):
        """Test summary verdict for decay_rate >= 0.06 (fast)."""
        profile = ForecastProfile(brand_decay_monthly_rate=0.08)
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=profile,
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=3,
            base_date=self.base_date,
        )

        self.assertIn("Быстрая амортизация", report.summary_verdict)
        self.assertIn("китайских суббрендов", report.summary_verdict)

    def test_price_decay_convergence(self):
        """Test that prices decay monotonically towards plateau."""
        profile = ForecastProfile(
            brand_decay_monthly_rate=0.05,
            historical_plateau_rv=0.60,
        )
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=profile,
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=24,
            base_date=self.base_date,
        )

        plateau_price = 60000 * 0.60  # 36000

        # Prices should decrease over time
        prices = [p.predicted_price_rub for p in report.points]
        self.assertTrue(all(prices[i] >= prices[i + 1] for i in range(len(prices) - 1)))

        # All prices should be >= plateau price
        for price in prices:
            self.assertGreaterEqual(price, plateau_price)
        
        # First price should be close to current
        self.assertLess(report.points[0].predicted_price_rub, 60000)

    def test_target_date_format(self):
        """Test that target_date is in ISO format."""
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=ForecastProfile(),
        )

        report = generate_price_forecast(
            device=device,
            current_price_rub=60000,
            months_horizon=3,
            base_date=date(2026, 1, 15),
        )

        for point in report.points:
            # Should be in ISO format: YYYY-MM-DD
            self.assertRegex(point.target_date, r"^\d{4}-\d{2}-\d{2}$")

    def test_months_horizon_respected(self):
        """Test that only requested number of months are generated."""
        device = Device(
            model_id="test-device",
            name="Test Device",
            brand="TestBrand",
            lineage=self.lineage,
            forecast_profile=ForecastProfile(),
        )

        for horizon in [1, 6, 12, 24]:
            report = generate_price_forecast(
                device=device,
                current_price_rub=60000,
                months_horizon=horizon,
                base_date=self.base_date,
            )

            self.assertEqual(len(report.points), horizon)


if __name__ == "__main__":
    unittest.main()
