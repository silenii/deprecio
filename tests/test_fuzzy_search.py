"""Unit tests for Smart Fuzzy Search, Strict Generation Matching, and Global Database."""

import pytest
from deprecio.core.fuzzy_search import (
    BRAND_TRANSLIT,
    calculate_match_score,
    extract_model_numbers,
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
    assert "s24" == normalize_search_text("с24")
    assert "a55" == normalize_search_text("а55")
    assert "2a" == normalize_search_text("2а")


def test_strict_number_discrimination():
    # Запрос с числом '7' (Redmi Note 7) не должен сопоставляться с моделью '13' (Redmi Note 13 Pro+)
    score_redmi = calculate_match_score("redmi note 7", "Xiaomi Redmi Note 13 Pro+", "Xiaomi")
    assert score_redmi == 0.0

    # iPhone 11 не должен сопоставляться с iPhone 15
    score_iphone = calculate_match_score("iphone 11", "Apple iPhone 15 Pro", "Apple")
    assert score_iphone == 0.0

    # s24 не должен сопоставляться с s23
    score_samsung = calculate_match_score("s24", "Samsung Galaxy S23", "Samsung")
    assert score_samsung == 0.0

    # Корректное совпадение того же поколения
    assert calculate_match_score("redmi note 7", "Xiaomi Redmi Note 7", "Xiaomi") >= 0.90
    assert calculate_match_score("s24", "Samsung Galaxy S24", "Samsung") >= 0.90


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


def test_global_database_search():
    provider = CachedSpecsProvider()

    # Поиск Redmi Note 7 находит именно Redmi Note 7, а не 13 Pro+
    redmi7_list = provider.search_devices("redmi note 7")
    assert len(redmi7_list) > 0
    top_redmi = redmi7_list[0]
    assert "Redmi Note 7" in top_redmi.name
    assert "13" not in top_redmi.name
    assert top_redmi.chipset is not None

    # Поиск старого iPhone 7
    iphone7_list = provider.search_devices("iphone 7")
    assert len(iphone7_list) > 0
    assert "iPhone 7" in iphone7_list[0].name

    # Поиск Samsung Galaxy S10
    s10_list = provider.search_devices("galaxy s10")
    assert len(s10_list) > 0
    assert "S10" in s10_list[0].name
