"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from deprecio.api.routes.devices import router as devices_router
from deprecio.api.routes.forecast import router as forecast_router

app = FastAPI(title="Deprecio API", version="1.0.0")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v1")


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
def health_check() -> dict[str, str]:
    return {"status": "ok"}
