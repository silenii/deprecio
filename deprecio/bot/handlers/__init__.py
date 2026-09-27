"""Telegram Bot Handlers module."""

from .base import router as base_router
from .device import router as device_router
from .new_releases import router as new_releases_router

__all__ = ["base_router", "device_router", "new_releases_router"]
