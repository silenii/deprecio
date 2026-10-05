"""SQLite persistence for price alerts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import PriceAlert


class PriceAlertLimitError(ValueError):
    """Raised when a user reaches the configured active-alert limit."""


class SQLitePriceAlertRepository:
    def __init__(self, database_path: str | Path = "data/price_alerts.db", max_per_user: int = 20) -> None:
        if max_per_user < 1:
            raise ValueError("max_per_user must be positive")
        self.database_path = Path(database_path)
        self.max_per_user = max_per_user
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS price_alerts (
                user_id INTEGER NOT NULL, model_id TEXT NOT NULL, target_price_rub REAL NOT NULL,
                enabled INTEGER NOT NULL, created_at TEXT NOT NULL,
                last_notified_price_rub REAL, last_checked_at TEXT,
                PRIMARY KEY (user_id, model_id)
            )""")

    def upsert(self, user_id: int, model_id: str, target_price_rub: float) -> PriceAlert:
        if target_price_rub <= 0:
            raise ValueError("target_price_rub must be positive")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            existing = connection.execute(
                "SELECT 1 FROM price_alerts WHERE user_id = ? AND model_id = ?", (user_id, model_id)
            ).fetchone()
            if existing is None:
                count = connection.execute(
                    "SELECT COUNT(*) FROM price_alerts WHERE user_id = ? AND enabled = 1", (user_id,)
                ).fetchone()[0]
                if count >= self.max_per_user:
                    raise PriceAlertLimitError("subscription limit reached")
                connection.execute(
                    "INSERT INTO price_alerts VALUES (?, ?, ?, 1, ?, NULL, NULL)",
                    (user_id, model_id, target_price_rub, now),
                )
            else:
                connection.execute(
                    "UPDATE price_alerts SET target_price_rub = ?, enabled = 1 WHERE user_id = ? AND model_id = ?",
                    (target_price_rub, user_id, model_id),
                )
        return self.get(user_id, model_id)

    def get(self, user_id: int, model_id: str) -> PriceAlert:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM price_alerts WHERE user_id = ? AND model_id = ?", (user_id, model_id)).fetchone()
        if row is None:
            raise KeyError(model_id)
        return self._model(row)

    def list(self, user_id: int) -> list[PriceAlert]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM price_alerts WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [self._model(row) for row in rows]

    def set_enabled(self, user_id: int, model_id: str, enabled: bool) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute("UPDATE price_alerts SET enabled = ? WHERE user_id = ? AND model_id = ?", (int(enabled), user_id, model_id))
        return cursor.rowcount == 1

    def delete(self, user_id: int, model_id: str) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute("DELETE FROM price_alerts WHERE user_id = ? AND model_id = ?", (user_id, model_id))
        return cursor.rowcount == 1

    def due(self) -> list[PriceAlert]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT * FROM price_alerts WHERE enabled = 1").fetchall()
        return [self._model(row) for row in rows]

    def mark_checked(self, alert: PriceAlert, price: float, notified: bool) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "UPDATE price_alerts SET last_checked_at = ?, last_notified_price_rub = COALESCE(?, last_notified_price_rub) WHERE user_id = ? AND model_id = ?",
                (datetime.now(timezone.utc).isoformat(), price if notified else None, alert.user_id, alert.model_id),
            )

    @staticmethod
    def _model(row: tuple) -> PriceAlert:
        return PriceAlert(row[0], row[1], row[2], bool(row[3]), datetime.fromisoformat(row[4]), row[5], datetime.fromisoformat(row[6]) if row[6] else None)
