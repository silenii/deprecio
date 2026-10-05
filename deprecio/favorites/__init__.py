"""Persistent user favorites."""

from .repository import Favorite, FavoritesRepository, SQLiteFavoritesRepository

__all__ = ["Favorite", "FavoritesRepository", "SQLiteFavoritesRepository"]
