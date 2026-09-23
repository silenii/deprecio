"""Unit tests for GSMArena client, parser, and caching layer."""

import tempfile
import unittest
from pathlib import Path
from deprecio.models.device import EditionType
from deprecio.providers import CachedSpecsProvider, GSMArenaParser


class TestGSMArenaIntegration(unittest.TestCase):
    def setUp(self):
        # Мок сырого ответа спецификаций GSMArena
        self.mock_raw_s24 = {
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

    def test_parser_extracts_correct_fields(self):
        device = GSMArenaParser.parse_device(self.mock_raw_s24)
        self.assertIsNotNone(device)
        self.assertEqual(device.name, "Samsung Galaxy S24 Ultra")
        self.assertEqual(device.brand, "Samsung")
        self.assertIn("Snapdragon 8 Gen 3", device.chipset)

        # Проверка версий и комплектации
        self.assertGreater(len(device.editions), 0)
        edition = device.editions[0]
        self.assertEqual(edition.edition_type, EditionType.EAC_ROSTEST)
        self.assertTrue(edition.hardware.has_band_20)
        self.assertTrue(edition.hardware.has_band_7)
        self.assertTrue(edition.hardware.has_esim)
        self.assertTrue(edition.hardware.has_nfc)

        # Проверка зарядки (у Samsung нет блока в коробке, но мощность определена)
        self.assertFalse(edition.bundle.has_charger)
        self.assertEqual(edition.bundle.charger_wattage_w, 45)

        # Проверка вариантов памяти
        self.assertEqual(len(edition.memory_variants), 3)
        self.assertEqual(edition.memory_variants[0].storage_gb, 256)
        self.assertEqual(edition.memory_variants[0].ram_gb, 12)
        self.assertEqual(edition.memory_variants[2].storage_gb, 1024)

    def test_parser_detects_chinese_version_without_band_20(self):
        mock_cn = dict(self.mock_raw_s24)
        mock_cn["specifications_table"]["network"]["4g_bands"] = "1, 3, 5, 7, 8, 38, 39, 40, 41"
        device = GSMArenaParser.parse_device(mock_cn)
        cn_edition = next((e for e in device.editions if e.edition_type == EditionType.CN), None)
        self.assertIsNotNone(cn_edition)
        self.assertFalse(cn_edition.hardware.has_band_20)
        self.assertEqual(cn_edition.edition_type, EditionType.CN)

    def test_cached_provider_disk_storage(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            provider = CachedSpecsProvider(cache_dir=Path(tmp_dir))
            device = GSMArenaParser.parse_device(self.mock_raw_s24)

            # Сохраняем в кэш
            provider._save_to_disk_cache(device)

            # Создаем новый инстанс провайдера на той же папке
            new_provider = CachedSpecsProvider(cache_dir=Path(tmp_dir))
            cached_dev = new_provider.get_device(device.model_id)

            self.assertIsNotNone(cached_dev)
            self.assertEqual(cached_dev.name, "Samsung Galaxy S24 Ultra")
            self.assertGreaterEqual(len(cached_dev.editions), 3)


if __name__ == "__main__":
    unittest.main()
