"""Process-shared rate slots and short-lived Avito result cache."""

from __future__ import annotations

import sqlite3
import time

from deprecio.paths import state_database_path

STATE_DATABASE = "market_source_state.db"
EMPTY_RESULT_TTL_SEC = 15 * 60
UNAVAILABLE_TTL_SEC = 60


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(state_database_path(STATE_DATABASE), timeout=30)
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS request_slots (source TEXT PRIMARY KEY, next_at REAL NOT NULL)"
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS market_results (
            model_id TEXT PRIMARY KEY, status TEXT NOT NULL, expires_at REAL NOT NULL
        )"""
    )
    return connection


def reserve_request_slot(requests_per_minute: int) -> float:
    """Reserve a source request slot shared by all processes using the state volume."""
    if requests_per_minute < 0:
        raise ValueError("AVITO_RATE_LIMIT_RPM must be zero or greater")
    if requests_per_minute == 0:
        return 0.0

    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        now = time.time()
        row = connection.execute(
            "SELECT next_at FROM request_slots WHERE source = 'avito'"
        ).fetchone()
        slot = max(now, row[0]) if row else now
        connection.execute(
            "INSERT INTO request_slots(source, next_at) VALUES ('avito', ?) "
            "ON CONFLICT(source) DO UPDATE SET next_at = excluded.next_at",
            (slot + 60 / requests_per_minute,),
        )
        return max(0.0, slot - now)


def cached_market_status(model_id: str) -> str | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT status, expires_at FROM market_results WHERE model_id = ?", (model_id,)
        ).fetchone()
        if row is None:
            return None
        if row[1] <= time.time():
            connection.execute("DELETE FROM market_results WHERE model_id = ?", (model_id,))
            return None
        return str(row[0])


def cache_market_status(model_id: str, status: str, ttl_sec: int) -> None:
    if status not in {"empty", "unavailable"}:
        raise ValueError("market status must be empty or unavailable")
    with _connect() as connection:
        connection.execute(
            "INSERT INTO market_results(model_id, status, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(model_id) DO UPDATE SET status = excluded.status, expires_at = excluded.expires_at",
            (model_id, status, time.time() + ttl_sec),
        )


def clear_market_status(model_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM market_results WHERE model_id = ?", (model_id,))
