"""FastAPI application entry point."""

from fastapi import FastAPI

from deprecio.api.routes.devices import router as devices_router
from deprecio.api.routes.forecast import router as forecast_router

app = FastAPI(title="Deprecio API", version="1.0.0")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v1")
