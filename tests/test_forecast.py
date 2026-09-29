"""Unit tests for the price decay forecast engine."""

import pytest
from datetime import date

from deprecio.forecast import generate_price_forecast
from deprecio.models.device import Device, DeviceLineage, ForecastProfile


@pytest.fixture
def device():
    return Device(
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


def test_forecast_generates_points_and_drops(device):
    report = generate_price_forecast(
        device=device,
        current_price_rub=100000.0,
        months_horizon=12,
        base_date=date(2026, 9, 1),
    )

    assert report.device_id == "test-phone"
    # Функция генерирует точку для каждого месяца горизонта
    assert len(report.points) == 12

    # Цена монотонно убывает
    prices = [p.predicted_price_rub for p in report.points]
    for i in range(len(prices) - 1):
        assert prices[i] >= prices[i + 1]

    # Через 12 месяцев цена ниже стартовой, но выше плато (55 000 ₽)
    last_point = report.points[-1]
    assert last_point.predicted_price_rub < 100000.0
    assert last_point.predicted_price_rub >= 50000.0


def test_forecast_sweet_spot_trigger_set(device):
    """Sweet Spot trigger появляется ровно на expected_sweet_spot_months."""
    report = generate_price_forecast(
        device=device,
        current_price_rub=80000.0,
        months_horizon=12,
        base_date=date(2026, 9, 1),
    )

    # expected_sweet_spot_months = 6 → точка 6 должна иметь trigger "Sweet Spot"
    point_m6 = next(p for p in report.points if p.months_ahead == 6)
    assert point_m6.trigger_event == "Sweet Spot"

    # Остальные точки — без trigger
    other_points = [p for p in report.points if p.months_ahead != 6]
    for p in other_points:
        assert p.trigger_event is None


def test_forecast_plateau_lower_bound(device):
    """Прогнозная цена никогда не опускается ниже исторического плато."""
    report = generate_price_forecast(
        device=device,
        current_price_rub=100000.0,
        months_horizon=36,
        base_date=date(2026, 9, 1),
    )
    plateau = 100000.0 * 0.55  # historical_plateau_rv = 0.55
    for p in report.points:
        assert p.predicted_price_rub >= plateau, (
            f"Month {p.months_ahead}: {p.predicted_price_rub} < plateau {plateau}"
        )


@pytest.mark.parametrize("current_price", [-1.0, 0.0])
def test_forecast_rejects_non_positive_current_price(device, current_price):
    with pytest.raises(ValueError):
        generate_price_forecast(device=device, current_price_rub=current_price)


@pytest.mark.parametrize("months_horizon", [0, -1])
def test_forecast_rejects_invalid_horizon(device, months_horizon):
    with pytest.raises(ValueError):
        generate_price_forecast(
            device=device,
            current_price_rub=100000.0,
            months_horizon=months_horizon,
        )
