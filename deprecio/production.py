"""Production support: metrics, rate limiting, SQLite backups and checks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import statistics
import time
from collections import OrderedDict, deque
from deprecio.paths import backup_directory, state_directory
from pathlib import Path
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

logger = logging.getLogger("deprecio.production")
STATE_DATABASE_NAMES = ("price_history.db", "favorites.db", "price_alerts.db")


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.requests: dict[str, int] = {}
        self.latencies: dict[str, deque[float]] = {}
        self.alerts_triggered = 0

    def observe(self, route: str, elapsed: float) -> None:
        with self._lock:
            if route not in self.requests and len(self.requests) >= 31:
                route = "other"
            self.requests[route] = self.requests.get(route, 0) + 1
            self.latencies.setdefault(route, deque(maxlen=1024)).append(elapsed)

    def render(self, catalog_path: Path = Path("data/catalog.json")) -> str:
        with self._lock:
            requests = dict(self.requests)
            latencies = {key: tuple(value) for key, value in self.latencies.items()}
            alerts = self.alerts_triggered
        lines = [
            "# HELP deprecio_http_requests_total Total HTTP requests by route",
            "# TYPE deprecio_http_requests_total counter",
        ]
        for route, count in sorted(requests.items()):
            lines.append(f'deprecio_http_requests_total{{route="{route}"}} {count}')
        lines.append("# TYPE deprecio_http_request_latency_seconds summary")
        for route, values in sorted(latencies.items()):
            for quantile in (0.5, 0.95):
                percentile = statistics.quantiles(values, n=100)[int(quantile * 100) - 1] if len(values) > 1 else values[0]
                lines.append(f'deprecio_http_request_latency_seconds{{route="{route}",quantile="{quantile}"}} {percentile:.9f}')
        lines.append(f"deprecio_alerts_triggered_total {alerts}")
        catalog_size = catalog_path.stat().st_size if catalog_path.exists() else 0
        lines.append(f"deprecio_catalog_size_bytes {catalog_size}")
        return "\n".join(lines) + "\n"


metrics = Metrics()


class ProductionMiddleware(BaseHTTPMiddleware):
    """Collect request metrics and apply a fixed in-memory per-IP limit."""

    def __init__(self, app, limit: int | None = None, window: int = 60) -> None:
        super().__init__(app)
        self.limit = limit if limit is not None else int(os.getenv("DEPRECIO_RATE_LIMIT", "60"))
        self.window = window
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        now = time.monotonic()
        address = request.client.host if request.client else "unknown"
        with self._lock:
            bucket = self._requests.get(address)
            if bucket is None:
                if len(self._requests) >= 10_000:
                    self._requests.popitem(last=False)
                bucket = deque()
                self._requests[address] = bucket
            else:
                self._requests.move_to_end(address)
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            limited = self.limit > 0 and len(bucket) >= self.limit
            if self.limit > 0 and not limited:
                bucket.append(now)
        if limited:
            return PlainTextResponse("Too Many Requests\n", status_code=429, headers={"Retry-After": str(self.window)})
        started = time.perf_counter()
        response = await call_next(request)
        metrics.observe(request.method, time.perf_counter() - started)
        return response


def database_paths(data_dir: Path = Path("data"), state_dir: Path | None = None) -> list[Path]:
    state_dir = state_dir or state_directory()
    return [data_dir / "global_devices.db", *(state_dir / name for name in STATE_DATABASE_NAMES)]


def check_database_integrity(paths: list[Path] | None = None) -> None:
    for path in paths or database_paths():
        if not path.exists():
            continue
        try:
            with sqlite3.connect(path, timeout=2) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError(str(result[0] if result else "no result"))
        except (sqlite3.Error, OSError) as exc:
            logger.critical("startup_failed %s", json.dumps({"event": "database_integrity_failed", "database": path.name, "error": str(exc)}))
            raise SystemExit(1) from exc


def backup_databases(
    data_dir: Path = Path("data"), backup_dir: Path | None = None, keep: int | None = None
) -> list[Path]:
    keep = keep if keep is not None else int(os.getenv("DEPRECIO_BACKUP_KEEP", "5"))
    if keep < 1:
        raise ValueError("DEPRECIO_BACKUP_KEEP must be positive")
    backup_dir = backup_dir or backup_directory()
    backup_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000_000:09d}"
    for source in database_paths(data_dir):
        if not source.exists():
            continue
        target = backup_dir / f"{source.stem}-{stamp}.db"
        temporary = target.with_suffix(".tmp")
        source_connection = sqlite3.connect(source)
        target_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        temporary.replace(target)
        created.append(target)
        snapshots = sorted(backup_dir.glob(f"{source.stem}-*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for old in snapshots[keep:]:
            old.unlink()
    return created


async def backup_loop(interval: int = 3600) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            backup_databases()
        except Exception:
            logger.exception("periodic_backup_failed")
