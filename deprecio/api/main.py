"""FastAPI application entry point."""

import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from deprecio.api.routes.devices import router as devices_router
from deprecio.api.routes.forecast import router as forecast_router
from deprecio.api.routes.price_history import router as price_history_router
from deprecio.api.routes.recommendations import router as recommendations_router
from deprecio.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("deprecio.api")

app = FastAPI(title="Deprecio API", version="1.0.0")
app.include_router(price_history_router, prefix="/api/v1")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    status_code = exc.status_code
    code = "not_found" if status_code == 404 else "http_error"
    payload = {"code": code, "message": str(exc.detail)}
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "validation_error", "message": "Invalid request", "details": exc.errors()},
    )


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Health check — проверяет доступность ключевых зависимостей без раскрытия секретов."""
    checks: dict[str, str] = {}

    # Проверка основного каталога устройств
    catalog_file = Path("data/catalog.json")
    checks["catalog_json"] = "ok" if catalog_file.exists() else "missing"

    # Проверка SQLite базы устройств
    db_file = Path("data/global_devices.db")
    if db_file.exists():
        try:
            with sqlite3.connect(db_file, timeout=2) as conn:
                conn.execute("SELECT count(*) FROM phones LIMIT 1")
            checks["global_db"] = "ok"
        except (sqlite3.Error, OSError):
            checks["global_db"] = "error"
    else:
        checks["global_db"] = "missing"

    # Проверка прав записи кэша
    cache_dir = Path(".cache/devices")
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_file = cache_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        checks["cache_write"] = "ok"
    except OSError:
        checks["cache_write"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "ok" else 207

    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )
