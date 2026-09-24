from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from deprecio.providers.cached_provider import CachedSpecsProvider

router = APIRouter()
provider = CachedSpecsProvider()

@router.get("/search")
def search_devices(query: str = Query(..., min_length=2)):
    """Search for smartphones by name."""
    devices = provider.search_devices(query)
    if not devices:
        return {"results": []}
    
    # Using Pydantic models' dict method or model_dump
    return {"results": [d.model_dump() if hasattr(d, "model_dump") else d.dict() for d in devices]}

@router.get("/{device_id}")
def get_device(device_id: str):
    """Get a specific smartphone by its slug ID."""
    device = provider.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device.model_dump() if hasattr(device, "model_dump") else device.dict()
