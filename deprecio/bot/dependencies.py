"""Dependencies shared by Telegram handlers."""

from deprecio.harvester import MarketAggregator
from deprecio.providers import CachedSpecsProvider
from deprecio.favorites import SQLiteFavoritesRepository


def build_dependencies() -> tuple[CachedSpecsProvider, MarketAggregator, SQLiteFavoritesRepository]:
    """Create one provider pair for the lifetime of the bot process."""
    return CachedSpecsProvider(), MarketAggregator(), SQLiteFavoritesRepository()
