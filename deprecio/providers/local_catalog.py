"""Local YAML Catalog Provider for Deprecio."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from deprecio.models.device import Device
from .base import BaseSpecsProvider


class LocalCatalogProvider(BaseSpecsProvider):
    """Поставщик спецификаций на основе локальных YAML-файлов каталога."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/devices")
        self._devices: Dict[str, Device] = {}
        self.reload()

    def reload(self) -> None:
        """Сканирует каталог и загружает все спецификации в память."""
        self._devices.clear()
        if not self.data_dir.exists():
            return

        for yaml_file in self.data_dir.glob("**/*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "model_id" in data:
                        device = Device(**data)
                        self._devices[device.model_id] = device
            except Exception:
                # Пропуск некорректных или черновых файлов
                continue

    def get_device(self, model_id: str) -> Optional[Device]:
        return self._devices.get(model_id)

    def search_devices(self, query: str) -> List[Device]:
        q = query.lower().strip()
        results: List[Device] = []
        for dev in self._devices.values():
            if q in dev.name.lower() or q in dev.brand.lower() or q in dev.lineage.series.lower():
                results.append(dev)
        return results

    def find_analogs(
        self,
        device: Device,
        price_target_rub: Optional[float] = None,
        tolerance_percent: float = 0.15,
    ) -> List[Device]:
        """Подбирает аналоги по совпадению класса линейки (tier) за вычетом самой модели."""
        analogs: List[Device] = []
        for candidate in self._devices.values():
            if candidate.model_id == device.model_id:
                continue

            # Проверка соответствия классу устройства (Flagship, Sub-flagship и т.д.)
            if candidate.lineage.tier == device.lineage.tier:
                analogs.append(candidate)

        return analogs
