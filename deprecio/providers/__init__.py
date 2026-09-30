"""Providers module for smartphone specifications and analog discovery."""

from .base import BaseSpecsProvider
from .exceptions import CatalogDataError, DeviceNotFoundError
from .cached_provider import CachedSpecsProvider
from .gsmarena_client import GSMArenaClient, GSMArenaSearchResult
from .gsmarena_parser import GSMArenaParser
from .local_catalog import LocalCatalogProvider
from .nanoreview import ExternalSpecsAdapter
from .price_lookup import MsrpLookup

__all__ = [
    "BaseSpecsProvider",
    "CatalogDataError",
    "CachedSpecsProvider",
    "ExternalSpecsAdapter",
    "GSMArenaClient",
    "GSMArenaParser",
    "GSMArenaSearchResult",
    "LocalCatalogProvider",
    "DeviceNotFoundError",
    "MsrpLookup",
]
