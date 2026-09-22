"""Providers module for smartphone specifications and analog discovery."""

from .base import BaseSpecsProvider
from .local_catalog import LocalCatalogProvider
from .nanoreview import ExternalSpecsAdapter

__all__ = [
    "BaseSpecsProvider",
    "ExternalSpecsAdapter",
    "LocalCatalogProvider",
]
