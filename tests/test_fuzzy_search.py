"""Unit tests for Smart Fuzzy Search and Transliteration Engine."""

import pytest
from deprecio.core.fuzzy_search import (
    BRAND_TRANSLIT,
    calculate_match_score,
    fuzzy_search_devices,
    normalize_search_text,
)
from deprecio.models.device import Device
from deprecio.providers import CachedSpecsProvider


@pytest.fixture
def sample_devices():
    """Тестовый набор устройств."""
    provider = CachedSpecsProvider()
    return list(provider._memory_cache.values())


def test_normalize_search_text():
    # Проверка транслитерации и очистки знаков
    assert "iphone 15 pro" == normalize_search_text("Айфон 15 Pro")
    assert "nothing phone 2a" == normalize_search_text("Nothing Phone (2a)")
    assert "samsung s24 ultra" == normalize_search_text("Самсунг s24 ультра")
    assert "pixel 8" == normalize_search_text("Пиксель 8")


def test_calculate_match_score_exact_and_substring():
    score_exact = calculate_match_score("Nothing Phone 2a", "Nothing Phone (2a)", "Nothing")
    assert score_exact >= 0.95

    score_sub = calculate_match_score("2a", "Nothing Phone (2a)", "Nothing")
    assert score_sub >= 0.85

    score_tokens = calculate_match_score("nothing 2a", "Nothing Phone (2a)", "Nothing")
    assert score_tokens >= 0.85


def test_fuzzy_search_partial_queries(sample_devices):
    # Тест запроса 'Nothing Phone 2a'
    results_2a = fuzzy_search_devices("Nothing Phone 2a", sample_devices, min_score=0.45)
    assert len(results_2a) > 0
    top_dev, score = results_2a[0]
    assert "2a" in top_dev.name
    assert score >= 0.85

    # Тест частичного запроса '2a'
    results_short = fuzzy_search_devices("2a", sample_devices, min_score=0.45)
    assert any("2a" in dev.name for dev, _ in results_short)

    # Тест префикса 's24'
    results_s24 = fuzzy_search_devices("s24", sample_devices, min_score=0.45)
    assert any("S24" in dev.name for dev, _ in results_s24)


def test_fuzzy_search_russian_translit(sample_devices):
    # 'айфон 15' должен находить iPhone 15
    results_iphone = fuzzy_search_devices("айфон 15", sample_devices, min_score=0.45)
    assert len(results_iphone) > 0
    top_iphone, _ = results_iphone[0]
    assert "iPhone 15" in top_iphone.name

    # 'пиксель 8' должен находить Pixel 8
    results_pixel = fuzzy_search_devices("пиксель 8", sample_devices, min_score=0.45)
    assert len(results_pixel) > 0
    top_pixel, _ = results_pixel[0]
    assert "Pixel 8" in top_pixel.name


def test_cached_provider_fuzzy_integration():
    provider = CachedSpecsProvider()
    assert len(provider._memory_cache) >= 10

    # Поиск по неполному имени
    devs = provider.search_devices("nothing 2a")
    assert len(devs) > 0
    assert "2a" in devs[0].name

    # Поиск по русскому названию
    devs_ru = provider.search_devices("айфон 15")
    assert len(devs_ru) > 0
    assert "iPhone 15" in devs_ru[0].name
