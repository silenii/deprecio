"""Telegram Bot Handlers module."""

from .base import router as base_router
from .compare import router as compare_router
from .device import router as device_router
from .inline import router as inline_router
from .new_releases import router as new_releases_router
from .favorites import router as favorites_router
from .price_alerts import router as price_alerts_router

__all__ = ["base_router", "compare_router", "device_router", "inline_router", "new_releases_router", "favorites_router", "price_alerts_router"]
