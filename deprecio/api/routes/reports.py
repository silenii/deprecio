"""Downloadable analytics reports."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.routes.analytics import _device_response, _get_device
from deprecio.providers.base import BaseSpecsProvider
from deprecio.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])
Provider = Annotated[BaseSpecsProvider, Depends(get_specs_provider)]
FORMATS = {"json", "csv", "html", "md", "markdown"}


def _filename(value: str, fmt: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")[:80] or "report"
    suffix = "md" if fmt == "markdown" else fmt
    return f"{safe}.{suffix}"


async def _render(model_ids: list[str], fmt: str, provider: BaseSpecsProvider) -> Response:
    if fmt not in FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported report format")
    if not 1 <= len(model_ids) <= 5:
        raise HTTPException(status_code=422, detail="1-5 model IDs are supported")
    devices = [await _device_response(provider, _get_device(provider, model_id)) for model_id in model_ids]
    content, media_type = ReportService().render(devices, fmt)
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{_filename(model_ids[0], fmt)}"'})


@router.get("/{model_id}")
async def device_report(model_id: str, provider: Provider, format: str = Query("json")) -> Response:
    return await _render([model_id], format, provider)


@router.get("/compare/download")
async def comparison_report(model_ids: Annotated[list[str], Query(min_length=2, max_length=5)], provider: Provider, format: str = Query("json")) -> Response:
    return await _render(model_ids, format, provider)
