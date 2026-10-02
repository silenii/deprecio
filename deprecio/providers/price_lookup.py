"""Lookup of Russian smartphone retail prices on Yandex.Market."""

import json
import logging
from html.parser import HTMLParser
from typing import Any, Optional
import httpx
from deprecio.core.analytics_defaults import default_parameters

logger = logging.getLogger(__name__)


class _NextDataParser(HTMLParser):
    """Extract the contents of the Next.js data script without a DOM dependency."""

    def __init__(self) -> None:
        super().__init__()
        self._inside = False
        self._parts: list[str] = []
        self.data: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if (
            tag.lower() == "script"
            and attributes.get("id") == "__NEXT_DATA__"
            and attributes.get("type") == "application/json"
        ):
            self._inside = True

    def handle_data(self, data: str) -> None:
        if self._inside:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._inside and tag.lower() == "script":
            self.data = "".join(self._parts)
            self._inside = False


class MsrpLookup:
    """Fetch the starting retail price of a smartphone from Yandex.Market."""

    URL = "https://market.yandex.ru/search"

    def __init__(self, timeout_sec: float = 8.0) -> None:
        self.timeout = timeout_sec
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9",
        }

    async def fetch_msrp_rub(self, model_name: str) -> Optional[float]:
        """Find a smartphone's starting retail price in rubles."""
        try:
            if not model_name.strip():
                return None

            async with httpx.AsyncClient(
                headers=self.headers, timeout=self.timeout, follow_redirects=True
            ) as client:
                response = await client.get(
                    self.URL,
                    params={"text": model_name, "lr": "213"},
                )
            if response.status_code != 200:
                return None

            parser = _NextDataParser()
            parser.feed(response.text)
            if not parser.data:
                return None
            payload = json.loads(parser.data)
            return self._find_smartphone_price(payload)
        except httpx.TimeoutException:
            logger.warning("external_timeout operation=msrp_lookup model_id=%s", model_name)
            return None
        except httpx.HTTPError as exc:
            logger.warning("external_http_error operation=msrp_lookup model_id=%s error_type=%s", model_name, type(exc).__name__)
            return None
        except json.JSONDecodeError:
            logger.warning("parse_error operation=msrp_lookup model_id=%s format=json", model_name)
            return None
        except (TypeError, ValueError) as exc:
            logger.warning("validation_error operation=msrp_lookup model_id=%s error_type=%s", model_name, type(exc).__name__)
            return None

    @classmethod
    def _find_smartphone_price(cls, value: Any) -> Optional[float]:
        if isinstance(value, dict):
            if cls._is_smartphone(value):
                price = value.get("price")
                if isinstance(price, dict) and "value" in price:
                    parsed = cls._as_price(price["value"])
                    if parsed is not None:
                        return parsed
            for child in value.values():
                result = cls._find_smartphone_price(child)
                if result is not None:
                    return result
        elif isinstance(value, list):
            for child in value:
                result = cls._find_smartphone_price(child)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _is_smartphone(item: dict[str, Any]) -> bool:
        fields = (item.get("type"), item.get("category"), item.get("categoryName"))
        return any(
            isinstance(field, str)
            and ("смартфон" in field.lower() or "smartphone" in field.lower())
            for field in fields
        )

    @staticmethod
    def _as_price(value: Any) -> Optional[float]:
        try:
            if isinstance(value, str):
                value = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
            price = float(value)
            return price if price > 0 else None
        except (TypeError, ValueError):
            return None

    async def get_msrp_with_fallback(
        self, model_name: str, tier: str = "Mid-range", brand: str = ""
    ) -> float:
        """Return found MSRP or the shared Tier/brand analytical default."""
        result = await self.fetch_msrp_rub(model_name)
        return result if result and result > 0 else default_parameters(tier, brand)["msrp_rub"]
