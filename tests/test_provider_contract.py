"""Contract tests shared by the local and cached catalog providers."""

import json

import pytest

from deprecio.providers import CachedSpecsProvider, LocalCatalogProvider
from deprecio.providers.exceptions import CatalogDataError, DeviceNotFoundError
from deprecio.models.device import (
    Currency,
    Device,
    DeviceLineage,
    EditionType,
    MemoryVariant,
    RegionalEdition,
)


def test_empty_local_catalog_has_stable_contract(tmp_path):
    provider = LocalCatalogProvider(tmp_path)

    assert provider.search_devices("phone") == []
    with pytest.raises(DeviceNotFoundError):
        provider.get_device("missing")


def test_broken_yaml_record_is_reported(tmp_path):
    (tmp_path / "broken.yaml").write_text("model_id: [", encoding="utf-8")

    with pytest.raises(CatalogDataError):
        LocalCatalogProvider(tmp_path)


def test_broken_json_cache_is_reported(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "broken.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(CatalogDataError):
        CachedSpecsProvider(cache_dir=cache, catalog_file=tmp_path / "missing.json")


def test_cached_search_deduplicates_model_ids(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([sample_device.model_dump(mode="json")]), encoding="utf-8")
    provider = CachedSpecsProvider(
        cache_dir=tmp_path / "cache", catalog_file=catalog, global_db_file=tmp_path / "missing.db"
    )

    provider._memory_cache[sample_device.model_id] = sample_device
    results = provider.search_devices("Xiaomi 14")

    assert [device.model_id for device in results] == [sample_device.model_id]


def _device(model_id, tier="Flagship", msrp=85000):
    return Device(
        model_id=model_id,
        name=model_id,
        brand="Test",
        lineage=DeviceLineage(series="Series", tier=tier),
        editions=[RegionalEdition(
            edition_type=EditionType.US,
            memory_variants=[MemoryVariant(ram_gb=8, storage_gb=256, msrp_local=msrp, currency=Currency.RUB)],
        )],
    )


@pytest.fixture(params=[LocalCatalogProvider, CachedSpecsProvider])
def analog_provider(request, tmp_path):
    provider_class = request.param
    source = [_device("source", msrp=100000), _device("near", msrp=105000), _device("far", msrp=115000), _device("other-tier", tier="Budget", msrp=100000)]
    if provider_class is LocalCatalogProvider:
        for device in source:
            (tmp_path / f"{device.model_id}.yaml").write_text(device.model_dump_json(), encoding="utf-8")
        return provider_class(tmp_path)
    provider = provider_class(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "missing.json", global_db_file=tmp_path / "missing.db")
    provider._memory_cache.clear()
    provider._memory_cache.update({device.model_id: device for device in source})
    return provider


def test_analog_price_filter_contract(analog_provider):
    source = analog_provider.get_device("source")
    results = analog_provider.find_analogs(source, price_target_rub=100000, tolerance_percent=0.1)

    assert [device.model_id for device in results] == ["near"]


def test_analog_price_filter_sorts_by_closeness(analog_provider):
    source = analog_provider.get_device("source")
    results = analog_provider.find_analogs(source, price_target_rub=100000, tolerance_percent=0.2)

    assert [device.model_id for device in results] == ["near", "far"]


def test_analog_filter_validates_tolerance(analog_provider):
    source = analog_provider.get_device("source")
    with pytest.raises(ValueError):
        analog_provider.find_analogs(source, price_target_rub=100000, tolerance_percent=1.01)


def test_analog_filter_uses_fallback_msrp(analog_provider):
    source = analog_provider.get_device("source")
    fallback = _device("fallback", msrp=0)
    fallback.editions[0].memory_variants.clear()
    if isinstance(analog_provider, LocalCatalogProvider):
        analog_provider._devices[fallback.model_id] = fallback
    else:
        analog_provider._memory_cache[fallback.model_id] = fallback

    assert any(
        device.model_id == "fallback"
        for device in analog_provider.find_analogs(source, 85000, 0)
    )
