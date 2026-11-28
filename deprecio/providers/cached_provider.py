"""Hybrid Cached Specifications Provider combining GSMArena and Local Cache."""

import json
import asyncio
import logging
from pathlib import Path
import sqlite3
import httpx
from pydantic import ValidationError
from typing import Dict, List, Optional
from deprecio.bot.config import BotConfig
from deprecio.core.fuzzy_search import calculate_match_score, fuzzy_search_devices, normalize_search_text
from deprecio.models.device import Device
from .base import BaseSpecsProvider
from .exceptions import CatalogDataError, DeviceNotFoundError, MarketDataUnavailableError
from .gsmarena_client import GSMArenaClient
from .gsmarena_parser import GSMArenaParser

logger = logging.getLogger(__name__)


class CachedSpecsProvider(BaseSpecsProvider):
    """Поставщик спецификаций с гибридным каталогом, глобальной базой (10 600+ моделей) и GSMArena."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        client: Optional[GSMArenaClient] = None,
        catalog_file: Optional[Path] = None,
        global_db_file: Optional[Path] = None,
        config: Optional[BotConfig] = None,
    ):
        self._config = config
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
        self._market_stats_cache: Dict[str, object] = {}
        self._load_catalog()
        self._load_disk_cache()

    def _load_catalog(self) -> None:
        """Загружает встроенную базу устройств из data/catalog.json и дополняет региональные версии."""
        if not self.catalog_file or not self.catalog_file.exists():
            return
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                for item in items:
                    dev = Device(**item)
                    if len(dev.editions) <= 1:
                        first_ed = dev.editions[0] if dev.editions else None
                        if first_ed:
                            dev.editions = GSMArenaParser._generate_regional_editions(
                                brand=dev.brand,
                                name=dev.name,
                                release_date=first_ed.release_date,
                                hardware=first_ed.hardware,
                                bundle=first_ed.bundle,
                                variants=first_ed.memory_variants,
                            )
                    self._memory_cache[dev.model_id] = dev
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise CatalogDataError(f"Invalid catalog file: {self.catalog_file}") from exc

    def _load_disk_cache(self) -> None:
        """Загружает сохраненные ранее модели из локального дискового кэша."""
        for json_file in self.cache_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    dev = Device(**data)
                    self._memory_cache[dev.model_id] = dev
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise CatalogDataError(f"Invalid cache file: {json_file}") from exc

    def _save_to_disk_cache(self, device: Device) -> None:
        """Сохраняет распарсенную модель на диск."""
        self._memory_cache[device.model_id] = device
        file_path = self.cache_dir / f"{device.model_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(device.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("cache_write_error operation=save_device model_id=%s error_type=%s", device.model_id, type(exc).__name__)

    def get_device(self, model_id: str) -> Device:
        dev = self._memory_cache.get(model_id)
        if dev:
            return dev
        # An exact identifier lookup must never resolve to a different model.
        if self.global_db_file and self.global_db_file.exists():
            try:
                conn = sqlite3.connect(self.global_db_file)
                cur = conn.cursor()
                cur.execute("SELECT brand, name, raw_specs FROM phones WHERE id = ? LIMIT 1", (model_id,))
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
            except (sqlite3.DatabaseError, json.JSONDecodeError) as exc:
                raise CatalogDataError(f"Invalid device database: {self.global_db_file}") from exc
        raise DeviceNotFoundError(model_id)

    async def get_market_stats(self, device: Device, refresh: bool = False):
        """Получает статистику рынка из Avito с многоуровневым кешированием."""
        from deprecio.harvester import MarketAggregator, SnapshotGenerator
        from deprecio.harvester.source_state import (
            EMPTY_RESULT_TTL_SEC,
            UNAVAILABLE_TTL_SEC,
            cache_market_status,
            cached_market_status,
            clear_market_status,
        )
        from deprecio.price_history.repository import SQLitePriceHistoryRepository

        history = SQLitePriceHistoryRepository()

        def aggregate_and_save(listings):
            stats = MarketAggregator.aggregate_market_data(device, listings)
            if stats.total_raw_listings:
                MarketAggregator.persist_market_data(stats, "avito", history)
            return stats

        ttl = getattr(self, "_config", None)
        ttl_hours = ttl.snapshot_ttl_hours if ttl else 24
        snapshot_is_fresh = not refresh and SnapshotGenerator.is_snapshot_fresh(device.model_id, ttl_hours)
        if snapshot_is_fresh and device.model_id in self._market_stats_cache:
            return self._market_stats_cache[device.model_id]
        self._market_stats_cache.pop(device.model_id, None)

        if snapshot_is_fresh:
            cached = SnapshotGenerator.load_snapshot(device.model_id)
            if cached is not None:
                stats = aggregate_and_save(cached)
                self._market_stats_cache[device.model_id] = stats
                return stats

        if not refresh:
            status = cached_market_status(device.model_id)
            if status == "empty":
                stats = aggregate_and_save([])
                self._market_stats_cache[device.model_id] = stats
                return stats
            if status == "unavailable":
                raise MarketDataUnavailableError("Avito market data is temporarily unavailable")

        from deprecio.harvester.avito_scraper import AvitoScraper

        scraper = AvitoScraper()
        try:
            listings = await scraper.fetch_and_convert(device.name, device.model_id)
        except MarketDataUnavailableError:
            cache_market_status(device.model_id, "unavailable", UNAVAILABLE_TTL_SEC)
            raise
        if listings:
            SnapshotGenerator.save_snapshot(device, listings)
            clear_market_status(device.model_id)
        else:
            cache_market_status(device.model_id, "empty", EMPTY_RESULT_TTL_SEC)
        stats = aggregate_and_save(listings)
        self._market_stats_cache[device.model_id] = stats
        return stats

    async def get_cached_market_stats(self, device: Device):
        """Return only a fresh cached market snapshot without contacting Avito."""
        from deprecio.harvester import MarketAggregator, SnapshotGenerator
        from deprecio.price_history.repository import SQLitePriceHistoryRepository

        ttl = getattr(self, "_config", None)
        ttl_hours = ttl.snapshot_ttl_hours if ttl else 24
        if not SnapshotGenerator.is_snapshot_fresh(device.model_id, ttl_hours):
            return None
        listings = SnapshotGenerator.load_snapshot(device.model_id)
        if not listings:
            return None
        stats = MarketAggregator.aggregate_market_data(device, listings)
        if stats.total_raw_listings:
            MarketAggregator.persist_market_data(
                stats, "avito", SQLitePriceHistoryRepository()
            )
        self._market_stats_cache[device.model_id] = stats
        return stats

    def get_market_stats_sync(self, device: Device, refresh: bool = False):
        """Синхронная обертка для использования вне async-контекста."""
        return asyncio.run(self.get_market_stats(device, refresh=refresh))

    def _search_global_db(self, query: str, limit: int = 10) -> List[Device]:
        """Полнотекстовый поиск по глобальной базе данных SQLite (10 600+ устройств GSMArena)."""
        if not self.global_db_file or not self.global_db_file.exists():
            return []

        clean_q = normalize_search_text(query)
        tokens = clean_q.split()
        if not tokens:
            return []

        results = []
        try:
            conn = sqlite3.connect(self.global_db_file)
            cur = conn.cursor()
            query_fts = " ".join(f'"{t}"' for t in tokens)
            try:
                cur.execute(
                    "SELECT p.brand, p.name, p.raw_specs FROM phones_fts f "
                    "JOIN phones p ON f.id = p.id "
                    "WHERE phones_fts MATCH ? LIMIT 50",
                    (query_fts,),
                )
            except sqlite3.Error:
                clauses = " AND ".join(["clean_name LIKE ?" for _ in tokens])
                params = [f"%{t}%" for t in tokens]
                cur.execute(
                    f"SELECT brand, name, raw_specs FROM phones WHERE {clauses} LIMIT 50",
                    params,
                )
            rows = cur.fetchall()
            conn.close()

            for brand, name, raw_specs in rows:
                try:
                    specs_dict = json.loads(raw_specs) if raw_specs else {}
                except (TypeError, json.JSONDecodeError) as exc:
                    logger.warning("parse_error operation=global_db_specs model_id=%s error_type=%s", name, type(exc).__name__)
                    specs_dict = {}
                specs_dict["name"] = name
                specs_dict["brand"] = brand
                dev = GSMArenaParser.parse_device(specs_dict)
                if dev:
                    score = calculate_match_score(query, dev.name, dev.brand)
                    if score >= 0.50:
                        results.append((dev, score))

            results.sort(key=lambda x: x[1], reverse=True)
            devices = []
            seen = set()
            for dev, _ in results:
                if dev.model_id not in seen:
                    seen.add(dev.model_id)
                    devices.append(dev)
                if len(devices) == limit:
                    break
            for dev in devices:
                self._memory_cache[dev.model_id] = dev
            return devices
        except (sqlite3.DatabaseError, OSError) as e:
            import logging
            logging.exception(f"Error during SQLite search for '{query}': {e}")
            raise CatalogDataError(f"Invalid device database: {self.global_db_file}") from e

    def search_devices(self, query: str) -> List[Device]:
        """Умный поиск: сначала по избранному каталогу, затем по глобальной базе 10 600+ моделей."""
        q = query.strip()
        if not q:
            return list(self._memory_cache.values())

        # 1. Поиск по закэшированным и избранным устройствам
        curated_matches = fuzzy_search_devices(q, list(self._memory_cache.values()), min_score=0.45)
        if curated_matches and curated_matches[0][1] >= 0.85:
            return self._unique_devices(dev for dev, _ in curated_matches)

        # 2. Если уверенного совпадения нет — ищем в глобальной базе GSMArena (10 600+ моделей)
        global_matches = self._search_global_db(q)
        if global_matches:
            seen = set()
            combined = []
            for dev in global_matches + [d for d, _ in curated_matches]:
                if dev.model_id not in seen:
                    seen.add(dev.model_id)
                    combined.append(dev)
            return self._unique_devices(combined)

        return self._unique_devices(dev for dev, _ in curated_matches)

    @staticmethod
    def _unique_devices(devices):
        """Return devices in order while keeping only one instance per model ID."""
        unique = {}
        for device in devices:
            unique.setdefault(device.model_id, device)
        return list(unique.values())

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

            ranked_results = sorted(
                search_results,
                key=lambda result: calculate_match_score(query, result.name, ""),
                reverse=True,
            )
            for result in ranked_results:
                if not result.slug or calculate_match_score(query, result.name, "") < 0.50:
                    continue
                raw_specs = await self.client.get_device_raw_specs(result.slug)
                if not raw_specs:
                    continue

                device = GSMArenaParser.parse_device(raw_specs)
                if device and calculate_match_score(query, device.name, device.brand) >= 0.50:
                    self._save_to_disk_cache(device)
                    return device
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("external_fetch_failed operation=fetch_device model_id=%s error_type=%s", query, type(exc).__name__)
        except (TypeError, ValueError, ValidationError) as exc:
            logger.warning("parse_or_validation_error operation=fetch_device model_id=%s error_type=%s", query, type(exc).__name__)

        return None

    def find_analogs(
        self,
        device: Device,
        price_target_rub: Optional[float] = None,
        tolerance_percent: float = 0.15,
    ) -> List[Device]:
        """Поиск аналогов с общими правилами tier и ценового диапазона."""
        return self.filter_analogs(
            device, self._memory_cache.values(), price_target_rub, tolerance_percent
        )
