"""FastAPI dependencies for API providers."""

from deprecio.providers.cached_provider import CachedSpecsProvider
from deprecio.price_history.repository import SQLitePriceHistoryRepository
from deprecio.store_offers import SQLiteStoreOfferRepository


def get_specs_provider() -> CachedSpecsProvider:
    """Create the API catalog provider from the current local data sources."""
    return CachedSpecsProvider()


def get_price_history_repository() -> SQLitePriceHistoryRepository:
    return SQLitePriceHistoryRepository()


def get_store_offer_repository() -> SQLiteStoreOfferRepository:
    return SQLiteStoreOfferRepository()
