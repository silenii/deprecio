"""Unit test ensuring template and fixture YAML files are valid against Pydantic Device model."""

import unittest
from pathlib import Path
import yaml
from deprecio.models.device import Device


class TestDeviceCatalogIntegrity(unittest.TestCase):
    def test_device_template_is_valid(self):
        template_file = Path("data/templates/device_template.yaml")
        self.assertTrue(template_file.exists(), "Файл шаблона устройства должен существовать.")

        with open(template_file, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        self.assertIsInstance(raw_data, dict, "Шаблон должен быть валидным YAML-словарем.")
        device = Device(**raw_data)
        self.assertTrue(len(device.model_id) > 0)
        self.assertTrue(len(device.editions) > 0, "У шаблона должна быть хотя бы одна версия.")


if __name__ == "__main__":
    unittest.main()
