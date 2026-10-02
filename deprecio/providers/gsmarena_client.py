"""Asynchronous HTTP Client for GSMArena API and Data Scraping."""

from dataclasses import dataclass
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class GSMArenaSearchResult:
    """Краткая запись из результатов поиска GSMArena."""
    name: str
    slug: str
    image_url: Optional[str] = None
    description: Optional[str] = None


class GSMArenaClient:
    """Клиент для поиска и выгрузки детальных спецификаций с GSMArena."""

    BASE_URL = "https://www.gsmarena.com"
    API_MIRRORS = [
        "https://api-mobilespecs.azharimm.dev/v2",
    ]

    def __init__(self, timeout_sec: float = 10.0):
        self.timeout = timeout_sec
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def search(self, query: str) -> List[GSMArenaSearchResult]:
        """Поиск смартфонов по ключевому слову через API-зеркало или прямую страницу поиска."""
        results: List[GSMArenaSearchResult] = []
        clean_query = query.strip()
        if not clean_query:
            return results

        # 1. Попытка через публичное REST API зеркало
        for mirror in self.API_MIRRORS:
            try:
                resp = await self._get(f"{mirror}/search", params={"q": clean_query})
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("phones", [])
                    for item in items:
                        results.append(
                            GSMArenaSearchResult(
                                name=item.get("phone_name", clean_query),
                                slug=item.get("slug", ""),
                                image_url=item.get("image"),
                                description=item.get("detail"),
                            )
                        )
                    if results:
                        return results
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError, json.JSONDecodeError) as exc:
                logger.warning("external_search_failed operation=gsmarena_search model_id=%s error_type=%s", clean_query, type(exc).__name__)
                continue

        # 2. Fallback: прямой поиск через quick search GSMArena
        try:
            resp = await self._get(
                f"{self.BASE_URL}/results.php3",
                params={"sQuickSearch": "yes", "sName": clean_query},
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                makers_div = soup.find("div", class_="makers")
                if makers_div:
                    for li in makers_div.find_all("li"):
                        a_tag = li.find("a")
                        if a_tag and a_tag.get("href"):
                            href = a_tag["href"]
                            slug = href.replace(".php", "")
                            img = a_tag.find("img")
                            name = a_tag.text.strip()
                            img_url = img.get("src") if img else None
                            desc = img.get("title") if img else None
                            results.append(
                                GSMArenaSearchResult(
                                    name=name,
                                    slug=slug,
                                    image_url=img_url,
                                    description=desc,
                                )
                            )
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as exc:
            logger.warning("external_search_failed operation=gsmarena_html_search model_id=%s error_type=%s", clean_query, type(exc).__name__)

        return results

    async def get_device_raw_specs(self, slug: str) -> Optional[Dict[str, Any]]:
        """Получает полный словарь сырых спецификаций устройства."""
        # 1. Попытка через API-зеркало
        for mirror in self.API_MIRRORS:
            try:
                resp = await self._get(f"{mirror}/{slug}")
                if resp.status_code == 200:
                    data = resp.json()
                    phone_data = data.get("data", {})
                    if phone_data:
                        return phone_data
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError, json.JSONDecodeError) as exc:
                logger.warning("external_specs_failed operation=gsmarena_specs model_id=%s error_type=%s", slug, type(exc).__name__)
                continue

        # 2. Fallback: прямой парсинг страницы смартфона с GSMArena
        try:
            url = f"{self.BASE_URL}/{slug}.php" if not slug.endswith(".php") else f"{self.BASE_URL}/{slug}"
            resp = await self._get(url)
            if resp.status_code == 200:
                return self._parse_html_specs(resp.text, slug)
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as exc:
            logger.warning("external_specs_failed operation=gsmarena_html_specs model_id=%s error_type=%s", slug, type(exc).__name__)

        return None

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Perform one request plus one retry for transient network failures."""
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, **kwargs)
                if response.status_code >= 500 and attempt == 0:
                    await asyncio.sleep(0)
                    continue
                if response.status_code >= 400:
                    logger.warning("external_http_error operation=gsmarena_request model_id=%s status=%s", kwargs.get("params", {}).get("q", url), response.status_code)
                return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 1:
                    raise
                await asyncio.sleep(0)
        raise RuntimeError("unreachable")

    def _parse_html_specs(self, html: str, slug: str) -> Dict[str, Any]:
        """Парсинг HTML таблицы спецификаций GSMArena в структурированный словарь."""
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.find("h1", class_="specs-phone-name-title")
        phone_name = title_el.text.strip() if title_el else slug

        specs: Dict[str, Dict[str, str]] = {}
        for table in soup.find_all("table"):
            header = table.find("th")
            category_name = header.text.strip().lower() if header else "general"
            specs[category_name] = {}
            for row in table.find_all("tr"):
                ttl = row.find("td", class_="ttl")
                nfo = row.find("td", class_="nfo")
                if ttl and nfo:
                    k = ttl.text.strip().lower().replace(" ", "_")
                    v = nfo.text.strip()
                    if k and v:
                        specs[category_name][k] = v

        return {
            "phone_name": phone_name,
            "slug": slug,
            "specifications_table": specs,
        }
