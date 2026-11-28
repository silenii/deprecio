"""Current offers from stores, kept separate from private resale listings."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from deprecio.paths import state_database_path


class StoreOffer(BaseModel):
    model_id: str
    source: str = "podlovi"
    product_name: str
    price_rub: float = Field(gt=0)
    condition: str
    merchant: str
    product_url: str
    seller_url: str
    memory_configuration: str | None = None
    observed_at: datetime


class SQLiteStoreOfferRepository:
    """Persist the latest observed used-store offers without mixing market stats."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path else state_database_path("price_history.db")
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            columns = connection.execute("PRAGMA table_info(store_offers)").fetchall()
            primary_key = tuple(row[1] for row in sorted((row for row in columns if row[5]), key=lambda row: row[5]))
            if columns and "seller_url" not in primary_key:
                connection.execute("ALTER TABLE store_offers RENAME TO store_offers_legacy")
            connection.execute("""CREATE TABLE IF NOT EXISTS store_offers (
                model_id TEXT NOT NULL, source TEXT NOT NULL, product_name TEXT NOT NULL,
                price_rub REAL NOT NULL, condition TEXT NOT NULL, merchant TEXT NOT NULL,
                product_url TEXT NOT NULL, seller_url TEXT NOT NULL,
                memory_configuration TEXT, observed_at TEXT NOT NULL,
                PRIMARY KEY (model_id, source, product_url, merchant, seller_url, memory_configuration))""")
            if columns and "seller_url" not in primary_key:
                connection.execute("""INSERT OR IGNORE INTO store_offers
                    SELECT model_id, source, product_name, price_rub, condition, merchant,
                           product_url, seller_url, memory_configuration, observed_at
                    FROM store_offers_legacy""")
                connection.execute("DROP TABLE store_offers_legacy")

    def replace_source_offers(self, model_id: str, source: str, offers: list[StoreOffer]) -> None:
        """Replace one model's snapshot atomically after a successful source read."""
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("DELETE FROM store_offers WHERE model_id = ? AND source = ?", (model_id, source))
            connection.executemany(
                "INSERT INTO store_offers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(offer.model_id, offer.source, offer.product_name, offer.price_rub, offer.condition,
                  offer.merchant, offer.product_url, offer.seller_url, offer.memory_configuration,
                  offer.observed_at.astimezone(timezone.utc).isoformat()) for offer in offers],
            )

    def list(self, model_id: str, max_age_days: int = 7) -> list[StoreOffer]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT model_id, source, product_name, price_rub, condition, merchant, product_url, "
                "seller_url, memory_configuration, observed_at FROM store_offers "
                "WHERE model_id = ? AND observed_at >= ? ORDER BY price_rub ASC",
                (model_id, cutoff),
            ).fetchall()
        return [StoreOffer(**dict(zip(StoreOffer.model_fields, row))) for row in rows]
