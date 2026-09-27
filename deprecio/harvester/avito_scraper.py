"""HTTP scraper for real Avito smartphone listings."""

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from deprecio.cleaner.rules import detect_edition_from_text
from deprecio.models.listing import ItemCondition, MarketPlatform, SecondaryListing

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
        }

    async def fetch_listings(
        self,
        model_name: str,
        max_pages: int = 3,
        timeout_sec: float = 12.0,
    ) -> list[dict]:
        """Return raw Avito listings, or an empty list if Avito is unavailable."""
        if max_pages < 1:
            return []

        params = {"query": model_name, "category_id": 17, "localPriority": 0}
        listings: list[dict] = []
        try:
            async with httpx.AsyncClient(
                headers=self.HEADERS, timeout=timeout_sec, follow_redirects=True
            ) as client:
                for page in range(1, max_pages + 1):
                    response = await client.get(self.SEARCH_URL, params={**params, "page": page})
                    if response.status_code != 200:
                        logger.warning("Avito search returned HTTP %s", response.status_code)
                        return []
                    payload = response.json()
                    items = payload.get("items")
                    if items is None:
                        items = payload.get("result", {}).get("items")
                    if not isinstance(items, list):
                        logger.warning("Unexpected Avito search response structure")
                        return []
                    listings.extend(
                        self._normalise_item(item) for item in items if isinstance(item, dict)
                    )
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("Unable to fetch Avito listings: %s", exc)
            return []
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
                    condition=ItemCondition.EXCELLENT,
                )
            )
        return converted
