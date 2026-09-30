from datetime import date

from deprecio.core.analytics_defaults import convert_to_rub, default_parameters


def test_defaults_prioritize_brand_over_tier():
    values = default_parameters("Budget", "Apple", date(2026, 6, 15))
    assert values["msrp_rub"] == 90000.0


def test_defaults_are_deterministic_and_provide_release_date():
    values = default_parameters("Flagship", "Unknown", date(2026, 6, 15))
    assert values["release_date"] == date(2024, 12, 1)


def test_currency_conversion():
    assert convert_to_rub(100, "USD") == 9200.0