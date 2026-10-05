"""Dependencies shared by Telegram handlers."""

from deprecio.harvester import MarketAggregator
from deprecio.providers import CachedSpecsProvider
from deprecio.favorites import SQLiteFavoritesRepository
from deprecio.price_alerts import SQLitePriceAlertRepository


def build_dependencies() -> tuple[CachedSpecsProvider, MarketAggregator, SQLiteFavoritesRepository, SQLitePriceAlertRepository]:
    """Create one provider pair for the lifetime of the bot process."""
    return CachedSpecsProvider(), MarketAggregator(), SQLiteFavoritesRepository(), SQLitePriceAlertRepository()
