"""Unit tests for Avito Harvester, Secondary Market Snapshot Generation, and Aggregation."""

import tempfile
from pathlib import Path
import unittest

from deprecio.harvester import MarketAggregator, MarketStats, SnapshotGenerator
from deprecio.models.device import Currency, Device, DeviceLineage, EditionType, HardwareSpecs, BundleContents, MemoryVariant, RegionalEdition
from deprecio.models.listing import ItemCondition, MarketPlatform
from deprecio.providers import CachedSpecsProvider


class TestAvitoHarvester(unittest.TestCase):
    """Тестирование модуля сбора и агрегации объявлений вторичного рынка (Авито)."""

    def setUp(self):
        # Тестовая модель устройства с несколькими версиями
        self.device = Device(
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

    def test_snapshot_generator_produces_realistic_sample(self):
        listings = SnapshotGenerator.generate_listings(self.device, count=35)
        self.assertEqual(len(listings), 35)

        # Проверка базовых полей каждого объявления
        for item in listings:
            self.assertEqual(item.platform, MarketPlatform.AVITO)
            self.assertEqual(item.model_id, self.device.model_id)
            self.assertGreater(item.price_rub, 0)
            self.assertTrue(len(item.city) > 0)
            self.assertTrue(len(item.title) > 0)
            self.assertTrue(len(item.description_text) > 0)

        # Проверка наличия разных региональных версий
        detected_editions = {it.detected_edition for it in listings if it.detected_edition}
        self.assertIn(EditionType.EAC_ROSTEST, detected_editions)
        self.assertIn(EditionType.CN, detected_editions)

    def test_snapshot_includes_injected_defects_and_outliers(self):
        listings = SnapshotGenerator.generate_listings(self.device, count=35)

        # Проверка дефектных лотов (разбитый экран / на запчасти)
        defective = [it for it in listings if it.condition == ItemCondition.DEFECTIVE]
        self.assertGreaterEqual(len(defective), 1)

        # Проверка фейковых выбросов (например, цена 1 рубль за чехол)
        penny_ads = [it for it in listings if it.price_rub <= 10.0]
        self.assertGreaterEqual(len(penny_ads), 1)

    def test_market_aggregator_cleans_and_calculates_metrics(self):
        raw_listings = SnapshotGenerator.generate_listings(self.device, count=35)
        stats = MarketAggregator.aggregate_market_data(self.device, raw_listings)

        self.assertIsInstance(stats, MarketStats)
        self.assertEqual(stats.model_id, self.device.model_id)
        self.assertEqual(stats.total_raw_listings, 35)

        # Дефекты и выбросы должны быть отсеяны
        self.assertGreater(stats.defective_count, 0)
        self.assertGreater(stats.outliers_count, 0)
        self.assertLess(stats.clean_listings_count, stats.total_raw_listings)

        # Проверка корректности порядка цен и перцентилей
        self.assertLessEqual(stats.min_price_rub, stats.p25_price_rub)
        self.assertLessEqual(stats.p25_price_rub, stats.median_price_rub)
        self.assertLessEqual(stats.median_price_rub, stats.p75_price_rub)
        self.assertLessEqual(stats.p75_price_rub, stats.max_price_rub)

    def test_edition_price_gap_cn_vs_eac(self):
        raw_listings = SnapshotGenerator.generate_listings(self.device, count=50)
        stats = MarketAggregator.aggregate_market_data(self.device, raw_listings)

        eac_stats = stats.editions.get(EditionType.EAC_ROSTEST.value)
        cn_stats = stats.editions.get(EditionType.CN.value)

        self.assertIsNotNone(eac_stats)
        self.assertIsNotNone(cn_stats)

        # Китайская версия на вторичке должна быть дешевле Ростеста (отрицательный gap)
        self.assertLess(cn_stats.median_price_rub, eac_stats.median_price_rub)
        self.assertLess(cn_stats.gap_vs_eac_percent, 0.0)

    def test_snapshot_persistence_disk_io(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            listings = SnapshotGenerator.generate_listings(self.device, count=15)
            saved_file = SnapshotGenerator.save_snapshot(self.device, listings, base_dir=base_path)
            self.assertTrue(saved_file.exists())

            loaded = SnapshotGenerator.load_snapshot(self.device.model_id, base_dir=base_path)
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded), 15)
            self.assertEqual(loaded[0].listing_id, listings[0].listing_id)

    def test_cached_specs_provider_get_market_stats(self):
        provider = CachedSpecsProvider()
        stats = provider.get_market_stats(self.device)

        self.assertIsNotNone(stats)
        self.assertEqual(stats.model_id, self.device.model_id)
        self.assertGreater(stats.median_price_rub, 0)
        self.assertIn(EditionType.EAC_ROSTEST.value, stats.editions)

        # Повторный вызов берет из кэша
        cached_stats = provider.get_market_stats(self.device)
        self.assertIs(stats, cached_stats)


if __name__ == "__main__":
    unittest.main()
