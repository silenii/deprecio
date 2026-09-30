"""Exceptions raised by device catalog providers."""


class CatalogDataError(RuntimeError):
    """Catalog or cache data cannot be read or validated."""


class DeviceNotFoundError(LookupError):
    """The requested device is not present in the provider."""
