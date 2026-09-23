"""Providers module for smartphone specifications and analog discovery."""

from .base import BaseSpecsProvider
from .cached_provider import CachedSpecsProvider
from .gsmarena_client import GSMArenaClient, GSMArenaSearchResult
from .gsmarena_parser import GSMArenaParser
from .local_catalog import LocalCatalogProvider
from .nanoreview import ExternalSpecsAdapter

__all__ = [
    "BaseSpecsProvider",
    "CachedSpecsProvider",
    "ExternalSpecsAdapter",
    "GSMArenaClient",
    "GSMArenaParser",
    "GSMArenaSearchResult",
    "LocalCatalogProvider",
]
