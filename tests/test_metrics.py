"""Unit tests for core depreciation metrics and Sweet Spot analysis."""

from deprecio.core import (
    MarketStage,
    analyze_sweet_spot,
    calculate_depreciation_drop,
    calculate_edition_gap,
    calculate_residual_value,
)


def test_calculate_residual_value_normal():
    # Телефон стоил 100 000 ₽ на старте, сейчас на вторичке 65 000 ₽
    rv = calculate_residual_value(current_price=65000, msrp_price=100000)
    assert rv == 65.0


def test_calculate_residual_value_invalid_msrp():
    import pytest

    with pytest.raises(ValueError):
        calculate_residual_value(current_price=50000, msrp_price=0)


def test_calculate_depreciation_drop():
    drop = calculate_depreciation_drop(current_price=65000, msrp_price=100000)
    assert drop == -35.0


def test_calculate_edition_gap():
    eac_prices = [70000, 72000, 68000]
    cn_prices = [55000, 57000, 53000]
    gap = calculate_edition_gap(eac_prices, cn_prices)
    assert gap is not None
    assert gap < 0


def test_edition_gap_empty_list():
    assert calculate_edition_gap([], [60000]) is None


def test_analyze_sweet_spot_rapid_decay():
    result = analyze_sweet_spot(months_since_release=1, current_price=90000, msrp_price=100000)
    assert result.market_stage == MarketStage.RAPID_DECAY
    assert result.is_sweet_spot is False


def test_analyze_sweet_spot_sweet_spot():
    result = analyze_sweet_spot(months_since_release=8, current_price=58000, msrp_price=100000)
    assert result.market_stage == MarketStage.SWEET_SPOT
    assert result.is_sweet_spot is True


def test_analyze_sweet_spot_legacy_plateau():
    result = analyze_sweet_spot(months_since_release=24, current_price=35000, msrp_price=100000)
    assert result.market_stage == MarketStage.LEGACY_PLATEAU
    assert result.is_sweet_spot is False
