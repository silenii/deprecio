"""SQLite storage for Telegram user favorites."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Favorite:
    user_id: int
    model_id: str
    created_at: datetime


class FavoritesRepository(Protocol):
    def add(self, user_id: int, model_id: str) -> bool: ...
    def remove(self, user_id: int, model_id: str) -> bool: ...
    def contains(self, user_id: int, model_id: str) -> bool: ...
    def list(self, user_id: int, page: int = 0, limit: int = 10) -> list[Favorite]: ...


class SQLiteFavoritesRepository:
    def __init__(self, database_path: str | Path = "data/favorites.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER NOT NULL, model_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (user_id, model_id))"
            )

    def add(self, user_id: int, model_id: str) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO favorites VALUES (?, ?, ?)",
                (user_id, model_id, datetime.now(timezone.utc).isoformat()),
            )
        return cursor.rowcount == 1

    def remove(self, user_id: int, model_id: str) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM favorites WHERE user_id = ? AND model_id = ?", (user_id, model_id)
            )
        return cursor.rowcount == 1

    def contains(self, user_id: int, model_id: str) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM favorites WHERE user_id = ? AND model_id = ?",
                    (user_id, model_id),
                ).fetchone()
                is not None
            )

    def list(self, user_id: int, page: int = 0, limit: int = 10) -> list[Favorite]:
        limit = max(1, min(limit, 50))
        page = max(0, page)
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT user_id, model_id, created_at FROM favorites WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, page * limit),
            ).fetchall()
        return [Favorite(row[0], row[1], datetime.fromisoformat(row[2])) for row in rows]
