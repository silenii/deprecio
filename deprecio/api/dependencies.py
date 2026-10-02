"""FastAPI dependencies for API providers."""

from deprecio.providers.cached_provider import CachedSpecsProvider


def get_specs_provider() -> CachedSpecsProvider:
    """Create the API catalog provider from the current local data sources."""
    return CachedSpecsProvider()
