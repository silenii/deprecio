"""Device search and card endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from deprecio.api.dependencies import get_specs_provider
from deprecio.core.fuzzy_search import fuzzy_search_devices
from deprecio.models.device import Device
from deprecio.providers.base import BaseSpecsProvider
from deprecio.providers.exceptions import DeviceNotFoundError

router = APIRouter(prefix="/devices", tags=["devices"])
Provider = Annotated[BaseSpecsProvider, Depends(get_specs_provider)]


@router.get("/search", response_model=list[Device])
def search_devices(
    query: Annotated[str, Query(min_length=1)],
    provider: Provider,
) -> list[Device]:
    """Search the catalog using the provider and shared fuzzy matching logic."""
    devices = provider.search_devices(query)
    return [device for device, _score in fuzzy_search_devices(query, devices)] or devices


@router.get("/{model_id}", response_model=Device)
def get_device(model_id: str, provider: Provider) -> Device:
    """Return a complete device card."""
    try:
        return provider.get_device(model_id)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Device not found") from exc
