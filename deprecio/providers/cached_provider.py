"""Hybrid Cached Specifications Provider combining GSMArena and Local Cache."""

import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
from deprecio.core.fuzzy_search import calculate_match_score, fuzzy_search_devices, normalize_search_text
from deprecio.models.device import Device
from .base import BaseSpecsProvider
from .gsmarena_client import GSMArenaClient
from .gsmarena_parser import GSMArenaParser


class CachedSpecsProvider(BaseSpecsProvider):
    """Поставщик спецификаций с гибридным каталогом, глобальной базой (10 600+ моделей) и GSMArena."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        client: Optional[GSMArenaClient] = None,
        catalog_file: Optional[Path] = None,
        global_db_file: Optional[Path] = None,
    ):
        self.cache_dir = cache_dir or Path(".cache/devices")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or GSMArenaClient()

        # Поиск файла избранного каталога
        if catalog_file and catalog_file.exists():
            self.catalog_file: Optional[Path] = catalog_file
        elif Path("data/catalog.json").exists():
            self.catalog_file = Path("data/catalog.json")
        else:
            default_cat = Path(__file__).resolve().parent.parent.parent / "data" / "catalog.json"
            self.catalog_file = default_cat if default_cat.exists() else None

        # Поиск глобальной базы SQLite (10 600+ устройств)
        if global_db_file and global_db_file.exists():
            self.global_db_file: Optional[Path] = global_db_file
        elif Path("data/global_devices.db").exists():
            self.global_db_file = Path("data/global_devices.db")
        else:
            default_db = Path(__file__).resolve().parent.parent.parent / "data" / "global_devices.db"
            self.global_db_file = default_db if default_db.exists() else None

        self._memory_cache: Dict[str, Device] = {}
        self._load_catalog()
        self._load_disk_cache()

    def _load_catalog(self) -> None:
        """Загружает встроенную базу устройств из data/catalog.json."""
        if not self.catalog_file or not self.catalog_file.exists():
            return
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                for item in items:
                    dev = Device(**item)
                    self._memory_cache[dev.model_id] = dev
        except Exception:
            pass

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
        dev = self._memory_cache.get(model_id)
        if dev:
            return dev
        # Поиск по глобальной базе при прямом запросе model_id
        if self.global_db_file and self.global_db_file.exists():
            try:
                conn = sqlite3.connect(self.global_db_file)
                cur = conn.cursor()
                cur.execute("SELECT brand, name, raw_specs FROM phones WHERE id = ? OR clean_name LIKE ? LIMIT 1", (model_id, f"%{model_id.replace('-', ' ')}%"))
                row = cur.fetchone()
                conn.close()
                if row:
                    brand, name, raw_specs = row
                    specs_dict = json.loads(raw_specs) if raw_specs else {}
                    specs_dict["name"] = name
                    specs_dict["brand"] = brand
                    parsed = GSMArenaParser.parse_device(specs_dict)
                    if parsed:
                        self._memory_cache[parsed.model_id] = parsed
                        return parsed
            except Exception:
                pass
        return None

    def _search_global_db(self, query: str, limit: int = 5) -> List[Device]:
        """Полнотекстовый поиск по глобальной базе данных SQLite (10 600+ устройств GSMArena)."""
        if not self.global_db_file or not self.global_db_file.exists():
            return []

        clean_q = normalize_search_text(query)
        tokens = clean_q.split()
        if not tokens:
            return []

        clauses = " AND ".join(["clean_name LIKE ?" for _ in tokens])
        params = [f"%{t}%" for t in tokens]

        results = []
        try:
            conn = sqlite3.connect(self.global_db_file)
            cur = conn.cursor()
            cur.execute(f"SELECT brand, name, raw_specs FROM phones WHERE {clauses} LIMIT 25", params)
            rows = cur.fetchall()
            conn.close()

            for brand, name, raw_specs in rows:
                try:
                    specs_dict = json.loads(raw_specs) if raw_specs else {}
                except Exception:
                    specs_dict = {}
                specs_dict["name"] = name
                specs_dict["brand"] = brand
                dev = GSMArenaParser.parse_device(specs_dict)
                if dev:
                    score = calculate_match_score(query, dev.name, dev.brand)
                    if score >= 0.50:
                        results.append((dev, score))

            results.sort(key=lambda x: x[1], reverse=True)
            devices = [dev for dev, _ in results[:limit]]
            for dev in devices:
                self._memory_cache[dev.model_id] = dev
            return devices
        except Exception:
            return []

    def search_devices(self, query: str) -> List[Device]:
        """Умный поиск: сначала по избранному каталогу, затем по глобальной базе 10 600+ моделей."""
        q = query.strip()
        if not q:
            return list(self._memory_cache.values())

        # 1. Поиск по закэшированным и избранным устройствам
        curated_matches = fuzzy_search_devices(q, list(self._memory_cache.values()), min_score=0.45)
        if curated_matches and curated_matches[0][1] >= 0.85:
            return [dev for dev, _ in curated_matches]

        # 2. Если уверенного совпадения нет — ищем в глобальной базе GSMArena (10 600+ моделей)
        global_matches = self._search_global_db(q)
        if global_matches:
            seen = set()
            combined = []
            for dev in global_matches + [d for d, _ in curated_matches]:
                if dev.model_id not in seen:
                    seen.add(dev.model_id)
                    combined.append(dev)
            return combined

        return [dev for dev, _ in curated_matches]

    async def get_or_fetch_device(self, query: str) -> Optional[Device]:
        """
        Умный поиск:
        1. Сначала ищет в каталоге и локальном кэше через fuzzy matching;
        2. Если не найдено — обращается к GSMArena, парсит и кэширует.
        """
        # 1. Проверка локального кэша и каталога
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
