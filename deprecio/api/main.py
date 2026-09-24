from fastapi import FastAPI
from deprecio.api.routes import devices

app = FastAPI(
    title="Deprecio API",
    description="API for fetching and searching smartphone MSRP and analytics data.",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

app.include_router(devices.router, prefix="/api/v1/devices", tags=["devices"])
