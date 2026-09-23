"""Hybrid Cached Specifications Provider combining GSMArena and Local Cache."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from deprecio.models.device import Device
from .base import BaseSpecsProvider
from .gsmarena_client import GSMArenaClient
from .gsmarena_parser import GSMArenaParser


class CachedSpecsProvider(BaseSpecsProvider):
    """Поставщик спецификаций с автоматическим кэшированием запросов из GSMArena."""

    def __init__(self, cache_dir: Optional[Path] = None, client: Optional[GSMArenaClient] = None):
        self.cache_dir = cache_dir or Path(".cache/devices")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or GSMArenaClient()
        self._memory_cache: Dict[str, Device] = {}
        self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        """Загружает сохраненные ранее модели из локального дискового кэша."""
        for json_file in self.cache_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    dev = Device(**data)
                    self._memory_cache[dev.model_id] = dev
            except Exception:
                continue

    def _save_to_disk_cache(self, device: Device) -> None:
        """Сохраняет распарсенную модель на диск."""
        self._memory_cache[device.model_id] = device
        file_path = self.cache_dir / f"{device.model_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(device.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_device(self, model_id: str) -> Optional[Device]:
        return self._memory_cache.get(model_id)

    def search_devices(self, query: str) -> List[Device]:
        """Локальный поиск по уже закэшированным устройствам."""
        q = query.lower().strip()
        results: List[Device] = []
        for dev in self._memory_cache.values():
            if q in dev.name.lower() or q in dev.brand.lower() or q in dev.model_id:
                results.append(dev)
        return results

    async def get_or_fetch_device(self, query: str) -> Optional[Device]:
        """
        Умный поиск:
        1. Сначала ищет в локальном кэше;
        2. Если нет — идет в GSMArena, парсит и сохраняет в кэш.
        """
        # 1. Проверка локального кэша
        cached = self.search_devices(query)
        if cached:
            return cached[0]

        # 2. Обращение к GSMArena
        try:
            search_results = await self.client.search(query)
            if not search_results:
                return None

            best_match = search_results[0]
            raw_specs = await self.client.get_device_raw_specs(best_match.slug)
            if not raw_specs:
                return None

            device = GSMArenaParser.parse_device(raw_specs)
            if device:
                self._save_to_disk_cache(device)
                return device
        except Exception:
            pass

        return None

    def find_analogs(
        self,
        device: Device,
        price_target_rub: Optional[float] = None,
        tolerance_percent: float = 0.15,
    ) -> List[Device]:
        """Поиск аналогов среди закэшированных устройств того же класса."""
        analogs: List[Device] = []
        for candidate in self._memory_cache.values():
            if candidate.model_id == device.model_id:
                continue
            if candidate.lineage.tier == device.lineage.tier:
                analogs.append(candidate)
        return analogs
