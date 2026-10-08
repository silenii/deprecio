"""Additional boundary coverage for external providers."""

import json
import sqlite3

import httpx
import pytest

from deprecio.models.device import Device
from deprecio.providers.cached_provider import CachedSpecsProvider
from deprecio.providers.gsmarena_client import GSMArenaClient, GSMArenaSearchResult
from deprecio.providers.nanoreview import ExternalSpecsAdapter
from deprecio.providers.price_lookup import MsrpLookup
from deprecio.harvester.avito_scraper import AvitoScraper
from deprecio.recommendations.service import RecommendationService


class _Response:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _AsyncSession:
    response = _Response()

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_gsmarena_search_api_success(monkeypatch):
    _AsyncSession.response = _Response(
        payload={"data": {"phones": [{"phone_name": "Pixel 9", "slug": "pixel-9", "image": "x", "detail": "d"}]}}
    )
    monkeypatch.setattr("deprecio.providers.gsmarena_client.httpx.AsyncClient", _AsyncSession)

    result = await GSMArenaClient(timeout_sec=3).search(" Pixel 9 ")

    assert result == [GSMArenaSearchResult("Pixel 9", "pixel-9", "x", "d")]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_gsmarena_http_error_falls_back_to_empty(monkeypatch, status):
    _AsyncSession.response = _Response(status_code=status)
    monkeypatch.setattr("deprecio.providers.gsmarena_client.httpx.AsyncClient", _AsyncSession)

    assert await GSMArenaClient().get_device_raw_specs("missing") is None


@pytest.mark.asyncio
async def test_gsmarena_invalid_json_and_timeout_are_handled(monkeypatch):
    _AsyncSession.response = _Response(payload=json.JSONDecodeError("bad", "", 0))
    monkeypatch.setattr("deprecio.providers.gsmarena_client.httpx.AsyncClient", _AsyncSession)
    assert await GSMArenaClient().search("phone") == []

    async def timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(_AsyncSession, "get", timeout)
    assert await GSMArenaClient().search("phone") == []


@pytest.mark.asyncio
async def test_gsmarena_html_device_is_parsed(monkeypatch):
    html = """
    <h1 class='specs-phone-name-title'>Test Phone</h1>
    <table><tr><th>Network</th></tr><tr><td class='ttl'>4G Bands</td><td class='nfo'>1, 3, 7</td></tr></table>
    """
    responses = [_Response(status_code=404), _Response(text=html)]

    async def get(self, *args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(_AsyncSession, "get", get)
    monkeypatch.setattr("deprecio.providers.gsmarena_client.httpx.AsyncClient", _AsyncSession)

    result = await GSMArenaClient().get_device_raw_specs("test-phone")
    assert result["phone_name"] == "Test Phone"
    assert result["specifications_table"]["network"]["4g_bands"] == "1, 3, 7"


def test_nanoreview_payload_and_invalid_rating_like_value(caplog):
    device = ExternalSpecsAdapter.parse_nanoreview_payload(
        {"name": "Phone", "brand": "Brand", "processor": "SoC", "variants": [{"price": "1234.5"}]}
    )
    assert device is not None
    assert device.editions[0].memory_variants[0].msrp_local == 1234.5

    assert ExternalSpecsAdapter.parse_nanoreview_payload({"name": "", "variants": [{"price": "bad"}]}) is None
    assert ExternalSpecsAdapter.parse_nanoreview_payload({}) is not None
    assert caplog.records


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 503])
async def test_price_lookup_non_success_returns_none(monkeypatch, status):
    _AsyncSession.response = _Response(status_code=status)
    monkeypatch.setattr("deprecio.providers.price_lookup.httpx.AsyncClient", _AsyncSession)
    assert await MsrpLookup().fetch_msrp_rub("Phone") is None


@pytest.mark.asyncio
async def test_price_lookup_empty_html_and_timeout(monkeypatch):
    _AsyncSession.response = _Response(text="<html></html>")
    monkeypatch.setattr("deprecio.providers.price_lookup.httpx.AsyncClient", _AsyncSession)
    lookup = MsrpLookup()
    assert await lookup.fetch_msrp_rub("Phone") is None
    assert await lookup.fetch_msrp_rub("   ") is None

    async def timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(_AsyncSession, "get", timeout)
    assert await lookup.fetch_msrp_rub("Phone") is None


def test_price_formats_and_fallback():
    assert MsrpLookup._as_price("12 345,67") == 12345.67
    assert MsrpLookup._as_price("12\u00a0345") == 12345
    assert MsrpLookup._as_price(0) is None
    assert MsrpLookup._as_price("bad") is None
    assert MsrpLookup._find_smartphone_price({"type": "smartphone", "price": {"value": "99,5"}}) == 99.5


@pytest.mark.asyncio
async def test_price_lookup_fallback_default(monkeypatch):
    async def no_price(self, model_name):
        return None

    monkeypatch.setattr(MsrpLookup, "fetch_msrp_rub", no_price)
    assert await MsrpLookup().get_msrp_with_fallback("Phone", tier="Budget", brand="Brand") > 0


class _ExternalClient:
    def __init__(self, raw):
        self.raw = raw
        self.search_calls = 0

    async def search(self, query):
        self.search_calls += 1
        return [GSMArenaSearchResult("Fetched Phone", "fetched-phone")]

    async def get_device_raw_specs(self, slug):
        return self.raw


@pytest.mark.asyncio
async def test_cached_provider_miss_fetches_and_saves(tmp_path):
    raw = {"phone_name": "Fetched Phone", "slug": "fetched-phone", "brand": "Brand", "specifications_table": {}}
    client = _ExternalClient(raw)
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=catalog, global_db_file=tmp_path / "missing.db", client=client)

    device = await provider.get_or_fetch_device("Fetched Phone")

    assert isinstance(device, Device)
    assert client.search_calls == 1
    assert (tmp_path / "cache" / "fetched-phone.json").exists()


@pytest.mark.asyncio
async def test_cached_provider_hit_skips_external(tmp_path, sample_device):
    client = _ExternalClient({})
    provider = CachedSpecsProvider(cache_dir=tmp_path, catalog_file=tmp_path / "missing", global_db_file=tmp_path / "missing.db", client=client)
    provider._memory_cache[sample_device.model_id] = sample_device

    result = await provider.get_or_fetch_device("Xiaomi 14")

    assert result is sample_device
    assert client.search_calls == 0


@pytest.mark.asyncio
async def test_cached_provider_external_empty_and_invalid_result(tmp_path):
    class EmptyClient:
        async def search(self, query):
            return []

    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=catalog, client=EmptyClient())
    assert await provider.get_or_fetch_device("Unknown") is None

    class InvalidClient:
        async def search(self, query):
            return [GSMArenaSearchResult("Phone", "phone")]

        async def get_device_raw_specs(self, slug):
            return None

    provider.client = InvalidClient()
    assert await provider.get_or_fetch_device("Unknown") is None


def test_price_recursive_search_and_parser_helpers():
    payload = {"items": [{"categoryName": "Смартфон", "price": {"value": "1 234"}}]}
    assert MsrpLookup._find_smartphone_price(payload) == 1234
    assert MsrpLookup._find_smartphone_price({"type": "tablet", "price": {"value": 12}}) is None


@pytest.mark.asyncio
async def test_gsmarena_html_search_fallback(monkeypatch):
    html = "<div class='makers'><ul><li><a href='phone.php'><img src='img.jpg'>Phone</a></li></ul></div>"
    responses = [_Response(status_code=200, payload={"data": {"phones": []}}), _Response(text=html)]

    async def get(self, *args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(_AsyncSession, "get", get)
    monkeypatch.setattr("deprecio.providers.gsmarena_client.httpx.AsyncClient", _AsyncSession)
    result = await GSMArenaClient().search("Phone")
    assert result[0].slug == "phone"


def test_cached_provider_direct_database_lookup(tmp_path):
    database = tmp_path / "devices.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE phones (id TEXT, clean_name TEXT, brand TEXT, name TEXT, raw_specs TEXT)")
    connection.execute(
        "INSERT INTO phones VALUES (?, ?, ?, ?, ?)",
        ("db-phone", "db phone", "Brand", "DB Phone", json.dumps({"phone_name": "DB Phone", "slug": "db-phone"})),
    )
    connection.commit()
    connection.close()
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "catalog.json", global_db_file=database)
    assert provider.get_device("db-phone").name == "DB Phone"


@pytest.mark.asyncio
async def test_cached_provider_market_stats_falls_back_to_snapshot(monkeypatch, tmp_path, sample_device):
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "catalog.json")
    provider._market_stats_cache[sample_device.model_id] = {"cached": True}
    assert await provider.get_market_stats(sample_device) == {"cached": True}

    provider._market_stats_cache.clear()
    class Snapshot:
        @staticmethod
        def is_snapshot_fresh(*args):
            return False

        @staticmethod
        def generate_listings(*args, **kwargs):
            return []

        @staticmethod
        def save_snapshot(*args):
            return None

    class Scraper:
        async def fetch_and_convert(self, *args):
            return []

    monkeypatch.setattr("deprecio.harvester.generator.SnapshotGenerator", Snapshot)
    monkeypatch.setattr("deprecio.harvester.avito_scraper.AvitoScraper", Scraper)
    assert await provider.get_market_stats(sample_device) is not None


@pytest.mark.asyncio
async def test_cached_provider_market_stats_uses_external_listings(monkeypatch, tmp_path, sample_device):
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "catalog.json")

    class Scraper:
        async def fetch_and_convert(self, *args):
            return []

    monkeypatch.setattr("deprecio.harvester.avito_scraper.AvitoScraper", Scraper)
    stats = await provider.get_market_stats(sample_device, refresh=True)
    assert stats is not None
    assert sample_device.model_id in provider._market_stats_cache


def test_cached_provider_global_db_fallback_search(tmp_path):
    database = tmp_path / "devices.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE phones (id TEXT, clean_name TEXT, brand TEXT, name TEXT, raw_specs TEXT)")
    connection.execute("CREATE TABLE phones_fts (id TEXT, clean_name TEXT)")
    connection.execute("INSERT INTO phones_fts VALUES ('id', 'Phone')")
    connection.execute("INSERT INTO phones VALUES ('id', 'Phone', 'Brand', 'Phone', '{}')")
    connection.commit()
    connection.close()
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "catalog.json", global_db_file=database)
    assert provider.search_devices("Phone")


@pytest.mark.asyncio
async def test_avito_success_and_empty_pages(monkeypatch):
    _AsyncSession.response = _Response(payload={"items": [{"id": 1, "title": "Phone", "price": "12 000", "url": "/item", "location": "Moscow"}]})
    monkeypatch.setattr("deprecio.harvester.avito_scraper.httpx.AsyncClient", _AsyncSession)
    scraper = AvitoScraper()
    listings = await scraper.fetch_listings("Phone", max_pages=1)
    assert listings[0]["price"] == 12000
    converted = await scraper.fetch_and_convert("Phone", "phone", max_pages=1)
    assert converted[0].url.endswith("/item")
    assert await scraper.fetch_listings("Phone", max_pages=0) == []


@pytest.mark.asyncio
async def test_avito_http_and_timeout_fallbacks(monkeypatch):
    _AsyncSession.response = _Response(status_code=500)
    monkeypatch.setattr("deprecio.harvester.avito_scraper.httpx.AsyncClient", _AsyncSession)
    scraper = AvitoScraper()
    assert await scraper.fetch_listings("Phone") == []

    async def timeout(self, *args, **kwargs):
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(_AsyncSession, "get", timeout)
    assert await scraper.fetch_listings("Phone") == []


def test_avito_parsing_helpers():
    assert AvitoScraper._text("<b>Phone</b>") == "Phone"
    assert AvitoScraper._price({"amount": "1 234"}) == 1234
    normalised = AvitoScraper._normalise_item({"itemId": 3, "description_text": "desc", "address": "Kazan"})
    assert normalised["id"] == "3"


def test_cached_provider_empty_and_missing_paths(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=catalog, global_db_file=tmp_path / "missing.db")
    assert provider.search_devices("   ") == []
    assert provider._search_global_db("   ") == []
    assert provider._unique_devices([]) == []
    with pytest.raises(Exception):
        provider.get_device("missing")


def test_cached_provider_save_error_is_non_fatal(tmp_path, sample_device, monkeypatch):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=catalog)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read-only")))
    provider._save_to_disk_cache(sample_device)
    assert provider.get_device(sample_device.model_id) is sample_device


@pytest.mark.asyncio
async def test_recommendation_filters_and_insufficient_data(sample_device):
    class Provider:
        def search_devices(self, query):
            return [sample_device]

        async def get_market_stats(self, device):
            return type("Stats", (), {"median_price_rub": 0, "clean_listings_count": 0})()

    result = await RecommendationService(Provider()).recommend(
        tier="Flagship", brand="Xiaomi", min_storage_gb=128, preferred_specs={"brand": "Xiaomi"}
    )
    assert result["results"]
    assert result["results"][0]["price_source"] == "msrp_fallback"
    assert await RecommendationService(Provider()).recommend(brand="Apple") == {"results": [], "insufficient_data": [], "total": 0}
