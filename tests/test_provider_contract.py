"""Contract tests shared by the local and cached catalog providers."""

import json

import pytest

from deprecio.providers import CachedSpecsProvider, LocalCatalogProvider
from deprecio.providers.exceptions import CatalogDataError, DeviceNotFoundError


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