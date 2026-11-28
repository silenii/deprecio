"""HTTP scraper for real Avito smartphone listings."""

import logging
import asyncio
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from deprecio.bot.config import ScraperSettings
from deprecio.cleaner.rules import detect_edition_from_text
from deprecio.core.fuzzy_search import calculate_match_score
from deprecio.models.listing import ItemCondition, MarketPlatform, SecondaryListing
from deprecio.providers.exceptions import MarketDataUnavailableError
from deprecio.harvester.source_state import reserve_request_slot

logger = logging.getLogger(__name__)


class AvitoScraper:
    """Fetches smartphone listings from Avito's internal search endpoint."""

    BASE_URL = "https://www.avito.ru"
    SEARCH_URL = "https://www.avito.ru/js/1/search"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.avito.ru/",
        "X-Requested-With": "XMLHttpRequest",
    }

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        return str(value)

    @staticmethod
    def _price(value: Any) -> int:
        if isinstance(value, dict):
            value = value.get("value", value.get("amount", 0))
        if isinstance(value, (int, float)):
            return int(value)
        digits = "".join(char for char in str(value) if char.isdigit())
        return int(digits) if digits else 0

    @classmethod
    def _normalise_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        title = cls._text(item.get("title", ""))
        description = cls._text(item.get("description", item.get("description_text", "")))
        url = str(item.get("url", ""))
        return {
            "id": str(item.get("id", item.get("itemId", ""))),
            "title": title,
            "price": cls._price(item.get("price", item.get("priceDetailed", 0))),
            "url": url,
            "description": description,
            "location": cls._text(item.get("location", item.get("address", "Россия"))),
            "parameters": item.get("parameters", item.get("params", [])),
        }

    @staticmethod
    def _parameter_text(parameters: Any) -> str:
        if not isinstance(parameters, list):
            return ""
        return " ".join(
            str(parameter.get(key, ""))
            for parameter in parameters if isinstance(parameter, dict)
            for key in ("name", "title", "value")
        )

    @staticmethod
    def _memory(text: str) -> tuple[int | None, int | None]:
        normalized = text.lower().replace("тб", "tb").replace("гб", "gb")
        slash = re.search(r"\b(\d{1,2})\s*/\s*(\d{2,4})\b", normalized)
        if slash:
            return int(slash.group(1)), int(slash.group(2))
        ram = re.search(r"\b(\d{1,2})\s*(?:gb\s*)?(?:ram|озу)\b", normalized)
        capacities = [
            int(match.group(1)) * (1024 if match.group(2) == "tb" else 1)
            for match in re.finditer(r"\b(\d{1,4})\s*(gb|tb)\b", normalized)
        ]
        storage_gb = max(capacities, default=None)
        return (int(ram.group(1)) if ram else None), storage_gb

    @staticmethod
    def _condition(text: str) -> ItemCondition:
        value = text.lower()
        if any(word in value for word in ("на запчасти", "не работает", "разбит", "трещин", "дефект", "утоплен")):
            return ItemCondition.DEFECTIVE
        if any(word in value for word in ("запечатан", "новый", "новая", "новое", "не вскрыт")):
            return ItemCondition.NEW_SEALED
        if any(word in value for word in ("как новый", "идеальное состояние", "без следов")):
            return ItemCondition.LIKE_NEW
        if any(word in value for word in ("отличное состояние", "отличном состоянии")):
            return ItemCondition.EXCELLENT
        if any(word in value for word in ("хорошее состояние", "есть следы", "потертост")):
            return ItemCondition.GOOD
        return ItemCondition.UNKNOWN

    async def fetch_listings(
        self,
        model_name: str,
        max_pages: int = 3,
        timeout_sec: float = 12.0,
    ) -> list[dict]:
        """Return raw listings; raise explicitly when Avito cannot be read."""
        if max_pages < 1:
            return []

        params = {"query": model_name, "category_id": 17, "localPriority": 0}
        listings: list[dict] = []
        requests_per_minute = ScraperSettings().avito_rate_limit_rpm
        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, timeout=timeout_sec, follow_redirects=True
            ) as client:
                for page in range(1, max_pages + 1):
                    delay = await asyncio.to_thread(reserve_request_slot, requests_per_minute)
                    if delay:
                        await asyncio.sleep(delay)
                    response = await client.get(self.SEARCH_URL, params={**params, "page": page})
                    if response.status_code != 200:
                        raise MarketDataUnavailableError(f"Avito search returned HTTP {response.status_code}")
                    payload = response.json()
                    items = payload.get("items")
                    if items is None:
                        items = payload.get("result", {}).get("items")
                    if not isinstance(items, list):
                        raise MarketDataUnavailableError("Unexpected Avito search response structure")
                    listings.extend(
                        self._normalise_item(item) for item in items if isinstance(item, dict)
                    )
        except MarketDataUnavailableError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("external_timeout operation=avito_listings model_id=%s", model_name)
            raise MarketDataUnavailableError("Avito search timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning("external_http_error operation=avito_listings model_id=%s error_type=%s", model_name, type(exc).__name__)
            raise MarketDataUnavailableError("Avito search request failed") from exc
        except (ValueError, TypeError, AttributeError) as exc:
            logger.warning("parse_error operation=avito_listings model_id=%s error_type=%s", model_name, type(exc).__name__)
            raise MarketDataUnavailableError("Avito search response could not be parsed") from exc
        return listings

    async def fetch_and_convert(
        self,
        model_name: str,
        model_id: str,
        max_pages: int = 3,
    ) -> list[SecondaryListing]:
        """Fetch listings and convert them to the project's market model."""
        raw_listings = await self.fetch_listings(model_name, max_pages=max_pages)
        converted: list[SecondaryListing] = []
        for item in raw_listings:
            text = f"{item['title']} {item['description']}"
            if calculate_match_score(model_name, item["title"], "") < 0.85:
                continue
            memory_text = f"{text} {self._parameter_text(item.get('parameters'))}"
            ram_gb, storage_gb = self._memory(memory_text)
            relative_url = item["url"]
            url = relative_url if relative_url.startswith("http") else self.BASE_URL + relative_url
            converted.append(
                SecondaryListing(
                    listing_id=item["id"],
                    platform=MarketPlatform.AVITO,
                    url=url,
                    title=item["title"],
                    description_text=item["description"],
                    price_rub=item["price"],
                    city=item["location"] or "Россия",
                    model_id=model_id,
                    detected_edition=detect_edition_from_text(text),
                    ram_gb=ram_gb,
                    storage_gb=storage_gb,
                    condition=self._condition(text),
                )
            )
        return converted
