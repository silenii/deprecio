"""Unit tests for Avito Harvester, Secondary Market Snapshot Generation, and Aggregation."""

import tempfile
from pathlib import Path

import pytest

from deprecio.harvester import MarketAggregator, MarketStats, SnapshotGenerator
from deprecio.models.device import (
    Currency, Device, DeviceLineage, EditionType,
    HardwareSpecs, BundleContents, MemoryVariant, RegionalEdition,
)
from deprecio.models.listing import ItemCondition, MarketPlatform
from deprecio.providers import CachedSpecsProvider


@pytest.fixture
def device():
    """Тестовая модель устройства с несколькими версиями."""
    return Device(
        model_id="xiaomi-14",
        name="Xiaomi 14",
        brand="Xiaomi",
        chipset="Qualcomm Snapdragon 8 Gen 3",
        lineage=DeviceLineage(series="Xiaomi Numbered", tier="Flagship"),
        editions=[
            RegionalEdition(
                edition_type=EditionType.EAC_ROSTEST,
                announced=True,
                hardware=HardwareSpecs(has_band_20=True, has_esim=True, sim_slots="2x NanoSIM"),
                bundle=BundleContents(has_charger=True, charger_wattage_w=90, has_case=True),
                memory_variants=[MemoryVariant(ram_gb=12, storage_gb=256, msrp_local=89990.0, currency=Currency.RUB)],
            ),
            RegionalEdition(
                edition_type=EditionType.GLOBAL_EU,
                announced=True,
                hardware=HardwareSpecs(has_band_20=True, has_esim=True, sim_slots="2x NanoSIM"),
                bundle=BundleContents(has_charger=True, charger_wattage_w=90, has_case=True),
                memory_variants=[MemoryVariant(ram_gb=12, storage_gb=256, msrp_local=79990.0, currency=Currency.RUB)],
            ),
            RegionalEdition(
                edition_type=EditionType.CN,
                announced=True,
                hardware=HardwareSpecs(has_band_20=False, has_esim=False, sim_slots="2x NanoSIM"),
                bundle=BundleContents(has_charger=True, charger_wattage_w=90, has_case=True),
                memory_variants=[MemoryVariant(ram_gb=12, storage_gb=256, msrp_local=64990.0, currency=Currency.RUB)],
            ),
        ],
    )


def test_snapshot_generator_produces_realistic_sample(device):
    listings = SnapshotGenerator.generate_listings(device, count=35)
    assert len(listings) == 35

    for item in listings:
        assert item.platform == MarketPlatform.AVITO
        assert item.model_id == device.model_id
        assert item.price_rub > 0
        assert len(item.city) > 0
        assert len(item.title) > 0
        assert len(item.description_text) > 0

    detected_editions = {it.detected_edition for it in listings if it.detected_edition}
    assert EditionType.EAC_ROSTEST in detected_editions
    assert EditionType.CN in detected_editions


def test_snapshot_includes_injected_defects_and_outliers(device):
    listings = SnapshotGenerator.generate_listings(device, count=35)

    defective = [it for it in listings if it.condition == ItemCondition.DEFECTIVE]
    assert len(defective) >= 1

    penny_ads = [it for it in listings if it.price_rub <= 10.0]
    assert len(penny_ads) >= 1


def test_market_aggregator_cleans_and_calculates_metrics(device):
    raw_listings = SnapshotGenerator.generate_listings(device, count=35)
    stats = MarketAggregator.aggregate_market_data(device, raw_listings)

    assert isinstance(stats, MarketStats)
    assert stats.model_id == device.model_id
    assert stats.total_raw_listings == 35

    assert stats.p25_price_rub > 0
    assert stats.clean_listings_count > 0
    assert stats.defective_count > 0
    assert stats.outliers_count > 0
    assert stats.clean_listings_count < stats.total_raw_listings

    assert stats.min_price_rub <= stats.p25_price_rub
    assert stats.p25_price_rub <= stats.median_price_rub
    assert stats.median_price_rub <= stats.p75_price_rub
    assert stats.p75_price_rub <= stats.max_price_rub


def test_edition_price_gap_cn_vs_eac(device):
    raw_listings = SnapshotGenerator.generate_listings(device, count=50)
    stats = MarketAggregator.aggregate_market_data(device, raw_listings)

    eac_stats = stats.editions.get(EditionType.EAC_ROSTEST.value)
    cn_stats = stats.editions.get(EditionType.CN.value)

    assert eac_stats is not None
    assert cn_stats is not None

    # Китайская версия на вторичке должна быть дешевле Ростеста (отрицательный gap)
    assert cn_stats.median_price_rub < eac_stats.median_price_rub
    assert cn_stats.gap_vs_eac_percent < 0.0


def test_snapshot_persistence_disk_io(device):
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        listings = SnapshotGenerator.generate_listings(device, count=15)
        saved_file = SnapshotGenerator.save_snapshot(device, listings, base_dir=base_path)
        assert saved_file.exists()

        loaded = SnapshotGenerator.load_snapshot(device.model_id, base_dir=base_path)
        assert loaded is not None
        assert len(loaded) == 15
        assert loaded[0].listing_id == listings[0].listing_id


def test_cached_specs_provider_get_market_stats(device):
    import asyncio
    provider = CachedSpecsProvider()

    # get_market_stats is async — run it synchronously for the test
    stats = asyncio.run(provider.get_market_stats(device))

    assert stats is not None
    assert stats.model_id == device.model_id
    assert stats.median_price_rub > 0
    assert EditionType.EAC_ROSTEST.value in stats.editions

    # Повторный вызов берёт из кэша (синхронно через asyncio.run)
    cached_stats = asyncio.run(provider.get_market_stats(device))
    assert stats is cached_stats

