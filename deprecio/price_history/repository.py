"""Storage contract and SQLite implementation for price history."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import PriceHistoryPoint


class PriceHistoryRepository(Protocol):
    def save(self, point: PriceHistoryPoint) -> None: ...

    def list(self, model_id: str, start: datetime | None = None, end: datetime | None = None,
             source: str | None = None, limit: int = 100) -> list[PriceHistoryPoint]: ...


class SQLitePriceHistoryRepository:
    def __init__(self, database_path: str | Path = "data/price_history.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS price_history (
                model_id TEXT NOT NULL, timestamp TEXT NOT NULL, source TEXT NOT NULL,
                currency TEXT NOT NULL, sample_size INTEGER NOT NULL,
                median_price_rub REAL NOT NULL, min_price_rub REAL NOT NULL,
                max_price_rub REAL NOT NULL, p25_price_rub REAL NOT NULL,
                p75_price_rub REAL NOT NULL, defective_count INTEGER NOT NULL,
                outliers_count INTEGER NOT NULL, condition_medians TEXT NOT NULL,
                PRIMARY KEY (model_id, source, timestamp))""")

    def save(self, point: PriceHistoryPoint) -> None:
        values = point.model_dump()
        values["timestamp"] = point.timestamp.isoformat()
        values["condition_medians"] = json.dumps(point.condition_medians, sort_keys=True)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO price_history ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )

    def list(self, model_id: str, start: datetime | None = None, end: datetime | None = None,
             source: str | None = None, limit: int = 100) -> list[PriceHistoryPoint]:
        clauses = ["model_id = ?"]
        params: list[object] = [model_id]
        if start:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("timestamp <= ?")
            params.append(end.isoformat())
        if source:
            clauses.append("source = ?")
            params.append(source)
        params.append(limit)
        query = "SELECT * FROM price_history WHERE " + " AND ".join(clauses) + " ORDER BY timestamp ASC LIMIT ?"
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [PriceHistoryPoint(
            model_id=row[0], timestamp=datetime.fromisoformat(row[1]), source=row[2], currency=row[3],
            sample_size=row[4], median_price_rub=row[5], min_price_rub=row[6], max_price_rub=row[7],
            p25_price_rub=row[8], p75_price_rub=row[9], defective_count=row[10], outliers_count=row[11],
            condition_medians=json.loads(row[12]),
        ) for row in rows]
