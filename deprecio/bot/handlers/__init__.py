"""Telegram Bot Handlers module."""

from .base import router as base_router
from .device import router as device_router

__all__ = ["base_router", "device_router"]
