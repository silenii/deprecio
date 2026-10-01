"""FastAPI dependencies for API providers."""

from functools import lru_cache

from deprecio.providers.local_catalog import LocalCatalogProvider


@lru_cache
def get_specs_provider() -> LocalCatalogProvider:
    """Return the application-wide catalog provider."""
    return LocalCatalogProvider()
