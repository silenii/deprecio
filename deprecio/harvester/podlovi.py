"""Collect used smartphone offers from Podlovi's public, robots-allowed pages."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from deprecio.models.device import Device
from deprecio.store_offers import SQLiteStoreOfferRepository, StoreOffer

logger = logging.getLogger(__name__)
BASE_URL = "https://podlovi.ru"
LIST_URL = f"{BASE_URL}/moscow/catalog/phones/ucenka/"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USED_CONDITION = "https://schema.org/UsedCondition"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
MAX_PRODUCT_PAGES_PER_MODEL = 2


def _normalise(value: str) -> str:
    value = value.casefold().replace("ё", "е").replace("+", " plus ")
    return " ".join(re.findall(r"[a-zа-я0-9]+", value))


def _matches_device(product_name: str, device: Device) -> bool:
    title, model = _normalise(product_name), _normalise(device.name)
    if not model or not re.search(rf"(?:^| ){re.escape(model)}(?:$| )", title):
        return False
    # Don't map a base model to its Pro/Ultra/Plus sibling (or vice versa).
    model_tokens = model.split()
    title_tokens = title.split()
    index = title_tokens.index(model_tokens[-1]) + 1
    qualifiers = {"pro", "plus", "ultra", "max", "mini", "fe", "edge", "lite"}
    return not (index < len(title_tokens) and title_tokens[index] in qualifiers)


def _memory_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path).lower()
    pair = re.search(r"(?:^|/)(\d{1,2})[-+](\d{2,4})(?:-?gb|[-/])", path)
    if pair:
        return f"{pair.group(1)}/{pair.group(2)} ГБ"
    storage = re.search(r"(?:^|[-/])(\d{2,4})-?gb(?:[-/]|$)", path)
    return f"{storage.group(1)} ГБ" if storage else None


def _add_product(pages: dict, model_id: str, product_name: str, product_url: str,
                 memory: str | None = None) -> None:
    if all(existing[1] != product_url for existing in pages.get(model_id, [])):
        pages.setdefault(model_id, []).append((product_name, product_url, memory or _memory_from_url(product_url)))


def _product_pages(html: str, devices: list[Device]) -> dict[str, list[tuple[str, str, str | None]]]:
    soup = BeautifulSoup(html, "html.parser")
    pages: dict[str, list[tuple[str, str, str | None]]] = {}
    for card in soup.select("article.shelf-tile"):
        name = card.select_one("a.shelf-name")
        if not name or not name.get("href"):
            continue
        product_name = name.get_text(" ", strip=True)
        matched = [device for device in devices if _matches_device(product_name, device)]
        if len(matched) != 1:
            continue
        memory = card.select_one(".shelf-specs")
        _add_product(pages, matched[0].model_id, product_name, urljoin(BASE_URL, name["href"]),
                     memory.get_text(" ", strip=True) if memory else None)
    return pages


def _sitemap_pages(documents: list[bytes], devices: list[Device]) -> dict[str, list[tuple[str, str, str | None]]]:
    pages: dict[str, list[tuple[str, str, str | None]]] = {}
    for document in documents:
        root = ET.fromstring(document)
        for location in root.iter(f"{SITEMAP_NS}loc"):
            url = location.text or ""
            parsed = urlparse(url)
            if parsed.netloc != urlparse(BASE_URL).netloc or not parsed.path.startswith("/m/"):
                continue
            title = unquote(parsed.path).replace("-", " ").replace("/", " ")
            matched = [device for device in devices if _matches_device(title, device)]
            if len(matched) == 1:
                _add_product(pages, matched[0].model_id, title, url)
    return pages


def _used_offers(html: str, model_id: str, product_name: str, product_url: str,
                 memory: str | None) -> list[StoreOffer]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc)
    offers: list[StoreOffer] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("@type") != "Product":
            continue
        aggregate = data.get("offers", {})
        entries = aggregate.get("offers", []) if isinstance(aggregate, dict) else []
        for entry in entries:
            condition = entry.get("itemCondition")
            if isinstance(condition, dict):
                condition = condition.get("@id", condition.get("url"))
            if condition != USED_CONDITION or entry.get("priceCurrency") != "RUB":
                continue
            availability = entry.get("availability", "")
            if availability and not availability.endswith("InStock"):
                continue
            try:
                price = float(entry["price"])
            except (KeyError, TypeError, ValueError):
                continue
            merchant = entry.get("seller", {}).get("name", "Магазин")
            seller_url = entry.get("url", product_url)
            if urlparse(seller_url).scheme != "https":
                continue
            offers.append(StoreOffer(
                model_id=model_id, product_name=product_name, price_rub=price,
                condition="Подержанный товар (по данным источника)", merchant=merchant,
                product_url=product_url, seller_url=seller_url,
                memory_configuration=memory, observed_at=now,
            ))
    return offers


async def harvest_podlovi(devices: list[Device], repository: SQLiteStoreOfferRepository | None = None) -> dict:
    """Read robots-listed sitemaps and at most two details per model at a gentle pace."""
    repository = repository or SQLiteStoreOfferRepository()
    headers = {
        "User-Agent": "Deprecio/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        response = await client.get(LIST_URL)
        response.raise_for_status()
        pages = _product_pages(response.text, devices)
        index = await client.get(SITEMAP_URL)
        index.raise_for_status()
        sitemap_root = ET.fromstring(index.content)
        sitemap_urls = [location.text for location in sitemap_root.iter(f"{SITEMAP_NS}loc") if location.text]
        documents = []
        for sitemap_url in sitemap_urls:
            parsed = urlparse(sitemap_url)
            if parsed.netloc != urlparse(BASE_URL).netloc or not parsed.path.startswith("/sitemap-"):
                continue
            sitemap = await client.get(sitemap_url)
            sitemap.raise_for_status()
            documents.append(sitemap.content)
        for model_id, products in _sitemap_pages(documents, devices).items():
            for product_name, product_url, memory in products:
                _add_product(pages, model_id, product_name, product_url, memory)
    result = {"matched_models": 0, "offers": 0, "errors": 0}
    for model_id, products in pages.items():
        model_offers: list[StoreOffer] = []
        model_ok = True
        for product_name, product_url, memory in products[:MAX_PRODUCT_PAGES_PER_MODEL]:
            await asyncio.sleep(1)
            try:
                # The listing sets a location cookie that makes product requests hang;
                # each public detail page is fetched in a fresh, independent session.
                async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
                    detail = await client.get(product_url)
                    detail.raise_for_status()
                model_offers.extend(_used_offers(detail.text, model_id, product_name, product_url, memory))
            except (httpx.HTTPError, ValueError) as exc:
                model_ok = False
                result["errors"] += 1
                logger.warning("store_offer_fetch_failed source=podlovi model_id=%s error_type=%s",
                               model_id, type(exc).__name__)
        if model_ok:
            repository.replace_source_offers(model_id, "podlovi", model_offers)
            result["matched_models"] += 1
            result["offers"] += len(model_offers)
    return result
