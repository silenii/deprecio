"""Unit test ensuring every YAML file in data/devices is valid against Pydantic Device model."""

import unittest
from pathlib import Path
import yaml
from deprecio.models.device import Device


class TestDeviceCatalogIntegrity(unittest.TestCase):
    def test_all_catalog_yaml_files_are_valid(self):
        catalog_dir = Path("data/devices")
        yaml_files = list(catalog_dir.glob("**/*.yaml"))
        self.assertGreater(len(yaml_files), 0, "Каталог устройств не должен быть пустым.")

        for file_path in yaml_files:
            with self.subTest(file=file_path.name):
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_data = yaml.safe_load(f)

                self.assertIsInstance(raw_data, dict, f"Файл {file_path} должен содержать словарь.")
                device = Device(**raw_data)
                self.assertTrue(len(device.model_id) > 0)
                self.assertTrue(len(device.editions) > 0, f"У {device.name} должна быть хотя бы одна версия.")


if __name__ == "__main__":
    unittest.main()
