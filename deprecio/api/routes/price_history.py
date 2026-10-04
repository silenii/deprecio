"""Historical market price endpoint."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from deprecio.api.dependencies import get_price_history_repository
from deprecio.price_history.repository import PriceHistoryRepository

router = APIRouter(prefix="/devices", tags=["price-history"])


@router.get("/{model_id}/price-history")
def get_price_history(
    model_id: str,
    repository: Annotated[PriceHistoryRepository, Depends(get_price_history_repository)],
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    source: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    if start and end and start > end:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="start must not be after end")
    points = repository.list(model_id, start, end, source, limit)
    serialized = [point.model_dump(mode="json") for point in points]
    change = None
    if len(points) >= 2 and points[0].median_price_rub:
        change = round((points[-1].median_price_rub - points[0].median_price_rub) / points[0].median_price_rub * 100, 2)
    return {"model_id": model_id, "source": source, "points": serialized,
            "price_change_percent": change, "chart": [{"timestamp": p["timestamp"], "price_rub": p["median_price_rub"]} for p in serialized]}
