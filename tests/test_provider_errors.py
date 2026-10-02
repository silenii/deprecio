"""Failure handling tests for external providers."""

import json
from pathlib import Path

import httpx
import pytest

from deprecio.harvester.avito_scraper import AvitoScraper
from deprecio.providers.cached_provider import CachedSpecsProvider
from deprecio.providers.exceptions import CatalogDataError
from deprecio.providers.gsmarena_client import GSMArenaClient
from deprecio.providers.price_lookup import MsrpLookup


@pytest.mark.asyncio
async def test_gsmarena_timeout_returns_fallback(monkeypatch):
    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", timeout)
    assert await GSMArenaClient().search("Pixel 9") == []


@pytest.mark.asyncio
async def test_price_lookup_invalid_json_returns_none(monkeypatch):
    response = httpx.Response(200, text='<script id="__NEXT_DATA__" type="application/json">{</script>')

    async def invalid_json(*args, **kwargs):
        return response

    monkeypatch.setattr(httpx.AsyncClient, "get", invalid_json)
    assert await MsrpLookup().fetch_msrp_rub("Pixel 9") is None


@pytest.mark.asyncio
async def test_avito_invalid_payload_returns_empty_list(monkeypatch):
    response = httpx.Response(200, text=json.dumps({"items": "invalid"}))

    async def invalid_payload(*args, **kwargs):
        return response

    monkeypatch.setattr(httpx.AsyncClient, "get", invalid_payload)
    assert await AvitoScraper().fetch_listings("Pixel 9") == []


def test_corrupted_cache_is_reported_before_external_fallback(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "broken.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(CatalogDataError):
        CachedSpecsProvider(cache_dir=cache, catalog_file=tmp_path / "missing.json")
