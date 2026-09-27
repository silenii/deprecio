"""Unit tests for GSMArena client, parser, and caching layer."""

import tempfile
from pathlib import Path

import pytest

from deprecio.models.device import EditionType
from deprecio.providers import CachedSpecsProvider, GSMArenaParser


@pytest.fixture
def mock_raw_s24():
    """Мок сырого ответа спецификаций GSMArena."""
    return {
        "phone_name": "Samsung Galaxy S24 Ultra",
        "slug": "samsung_galaxy_s24_ultra-12771",
        "brand": "Samsung",
        "specifications_table": {
            "network": {
                "technology": "GSM / CDMA / HSPA / EVDO / LTE / 5G",
                "4g_bands": "1, 2, 3, 4, 5, 7, 8, 12, 13, 17, 18, 19, 20, 25, 26, 28, 38, 39, 40, 41, 66",
            },
            "launch": {
                "announced": "2024, January 17",
                "status": "Available. Released 2024, January 24",
            },
            "platform": {
                "os": "Android 14, One UI 6.1.1",
                "chipset": "Qualcomm SM8650-AC Snapdragon 8 Gen 3 (4 nm)",
            },
            "memory": {
                "internal": "256GB 12GB RAM, 512GB 12GB RAM, 1TB 12GB RAM",
            },
            "body": {
                "sim": "Nano-SIM and eSIM or Dual SIM (2 Nano-SIMs and eSIM, dual stand-by)",
            },
            "battery": {
                "charging": "45W wired, PD3.0, 65% in 30 min",
            },
            "comms": {
                "nfc": "Yes",
            },
        },
    }


def test_parser_extracts_correct_fields(mock_raw_s24):
    device = GSMArenaParser.parse_device(mock_raw_s24)
    assert device is not None
    assert device.name == "Samsung Galaxy S24 Ultra"
    assert device.brand == "Samsung"
    assert "Snapdragon 8 Gen 3" in device.chipset

    # Проверка версий и комплектации
    assert len(device.editions) > 0
    edition = device.editions[0]
    assert edition.edition_type == EditionType.EAC_ROSTEST
    assert edition.hardware.has_band_20
    assert edition.hardware.has_band_7
    assert edition.hardware.has_esim
    assert edition.hardware.has_nfc

    # Проверка зарядки (у Samsung нет блока в коробке, но мощность определена)
    assert not edition.bundle.has_charger
    assert edition.bundle.charger_wattage_w == 45

    # Проверка вариантов памяти
    assert len(edition.memory_variants) == 3
    assert edition.memory_variants[0].storage_gb == 256
    assert edition.memory_variants[0].ram_gb == 12
    assert edition.memory_variants[2].storage_gb == 1024


def test_parser_detects_chinese_version_without_band_20(mock_raw_s24):
    import copy
    mock_cn = copy.deepcopy(mock_raw_s24)
    mock_cn["specifications_table"]["network"]["4g_bands"] = "1, 3, 5, 7, 8, 38, 39, 40, 41"
    device = GSMArenaParser.parse_device(mock_cn)
    cn_edition = next((e for e in device.editions if e.edition_type == EditionType.CN), None)
    assert cn_edition is not None
    assert not cn_edition.hardware.has_band_20
    assert cn_edition.edition_type == EditionType.CN


def test_cached_provider_disk_storage(mock_raw_s24):
    with tempfile.TemporaryDirectory() as tmp_dir:
        provider = CachedSpecsProvider(cache_dir=Path(tmp_dir))
        device = GSMArenaParser.parse_device(mock_raw_s24)

        # Сохраняем в кэш
        provider._save_to_disk_cache(device)

        # Создаём новый экземпляр провайдера на той же папке
        new_provider = CachedSpecsProvider(cache_dir=Path(tmp_dir))
        cached_dev = new_provider.get_device(device.model_id)

        assert cached_dev is not None
        assert cached_dev.name == "Samsung Galaxy S24 Ultra"
        assert len(cached_dev.editions) >= 3
