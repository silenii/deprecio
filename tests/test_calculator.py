"""Unit tests for price decay forecasting calculator."""

import re
import pytest
from datetime import date

from deprecio.forecast.calculator import generate_price_forecast, DeviceForecastReport
from deprecio.models.device import Device, ForecastProfile, DeviceLineage


@pytest.fixture
def lineage():
    return DeviceLineage(series="Test", tier="Flagship")


@pytest.fixture
def base_date():
    return date(2026, 1, 15)


@pytest.fixture
def test_device(lineage):
    return Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=ForecastProfile(),
    )


def test_forecast_with_default_profile_does_not_crash(test_device, base_date):
    """Test that function doesn't crash with ForecastProfile() defaults."""
    report = generate_price_forecast(
        device=test_device,
        current_price_rub=60000,
        months_horizon=12,
        base_date=base_date,
    )

    assert isinstance(report, DeviceForecastReport)
    assert report.device_id == "test-device"
    assert report.device_name == "Test Device"
    assert report.current_estimated_rub == 60000
    assert len(report.points) == 12


def test_forecast_points_structure(test_device, base_date):
    """Test that all forecast points are properly structured."""
    report = generate_price_forecast(
        device=test_device,
        current_price_rub=60000,
        months_horizon=6,
        base_date=base_date,
    )

    assert len(report.points) == 6

    for i, point in enumerate(report.points, start=1):
        assert point.months_ahead == i
        assert point.target_date is not None
        assert point.predicted_price_rub > 0
        assert point.predicted_rv_percent > 0


def test_sweet_spot_trigger_event(lineage, base_date):
    """Test that 'Sweet Spot' trigger is set at expected_sweet_spot_months."""
    profile = ForecastProfile(expected_sweet_spot_months=3)
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=profile,
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=6,
        base_date=base_date,
    )

    sweet_spot_point = next(p for p in report.points if p.months_ahead == 3)
    assert sweet_spot_point.trigger_event == "Sweet Spot"

    other_points = [p for p in report.points if p.months_ahead != 3]
    for point in other_points:
        assert point.trigger_event is None


def test_summary_verdict_slow_decay(lineage, base_date):
    """Test summary verdict for decay_rate < 0.03 (slow)."""
    profile = ForecastProfile(brand_decay_monthly_rate=0.02)
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=profile,
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=3,
        base_date=base_date,
    )

    assert "Медленная амортизация" in report.summary_verdict
    assert "хорошо держит цену" in report.summary_verdict


def test_summary_verdict_standard_decay(lineage, base_date):
    """Test summary verdict for 0.03 <= decay_rate < 0.06 (standard)."""
    profile = ForecastProfile(brand_decay_monthly_rate=0.045)
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=profile,
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=3,
        base_date=base_date,
    )

    assert "Стандартная амортизация" in report.summary_verdict
    assert "типичная для флагманов" in report.summary_verdict


def test_summary_verdict_fast_decay(lineage, base_date):
    """Test summary verdict for decay_rate >= 0.06 (fast)."""
    profile = ForecastProfile(brand_decay_monthly_rate=0.08)
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=profile,
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=3,
        base_date=base_date,
    )

    assert "Быстрая амортизация" in report.summary_verdict
    assert "китайских суббрендов" in report.summary_verdict


def test_price_decay_convergence(lineage, base_date):
    """Test that prices decay monotonically towards plateau."""
    profile = ForecastProfile(
        brand_decay_monthly_rate=0.05,
        historical_plateau_rv=0.60,
    )
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=profile,
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=24,
        base_date=base_date,
    )

    plateau_price = 60000 * 0.60  # 36000
    prices = [p.predicted_price_rub for p in report.points]

    # Prices should decrease over time
    assert all(prices[i] >= prices[i + 1] for i in range(len(prices) - 1))

    # All prices should be >= plateau price
    for price in prices:
        assert price >= plateau_price

    # First price should be lower than current
    assert report.points[0].predicted_price_rub < 60000


def test_target_date_format(lineage):
    """Test that target_date is in ISO format."""
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=ForecastProfile(),
    )

    report = generate_price_forecast(
        device=device,
        current_price_rub=60000,
        months_horizon=3,
        base_date=date(2026, 1, 15),
    )

    for point in report.points:
        assert re.search(r"^\d{4}-\d{2}-\d{2}$", point.target_date)


def test_months_horizon_respected(test_device, base_date):
    """Test that only requested number of months are generated."""
    for horizon in [1, 6, 12, 24]:
        report = generate_price_forecast(
            device=test_device,
            current_price_rub=60000,
            months_horizon=horizon,
            base_date=base_date,
        )
        assert len(report.points) == horizon


@pytest.mark.parametrize(
    "field,value",
    [
        ("brand_decay_monthly_rate", -0.01),
        ("brand_decay_monthly_rate", 1.0),
        ("historical_plateau_rv", -0.01),
        ("expected_sweet_spot_months", 0),
    ],
)
def test_forecast_profile_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        ForecastProfile(**{field: value})


def test_forecast_is_stable_for_120_months(test_device, base_date):
    report = generate_price_forecast(test_device, 60000, months_horizon=120, base_date=base_date)

    assert len(report.points) == 120
    assert all(point.predicted_price_rub >= 0 for point in report.points)
    assert all(point.predicted_rv_percent >= 0 for point in report.points)
    assert report.points[-1].predicted_price_rub >= 60000 * 0.60


def test_plateau_above_current_price_is_capped(lineage, base_date):
    device = Device(
        model_id="test-device",
        name="Test Device",
        brand="TestBrand",
        lineage=lineage,
        forecast_profile=ForecastProfile(historical_plateau_rv=1.5),
    )

    report = generate_price_forecast(device, 60000, months_horizon=12, base_date=base_date)

    assert all(point.predicted_price_rub == 60000 for point in report.points)
    assert all(point.predicted_rv_percent == 100.0 for point in report.points)
