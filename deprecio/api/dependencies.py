"""FastAPI dependencies for API providers."""

from deprecio.providers.cached_provider import CachedSpecsProvider
from deprecio.price_history.repository import SQLitePriceHistoryRepository


def get_specs_provider() -> CachedSpecsProvider:
    """Create the API catalog provider from the current local data sources."""
    return CachedSpecsProvider()


def get_price_history_repository() -> SQLitePriceHistoryRepository:
    return SQLitePriceHistoryRepository()
