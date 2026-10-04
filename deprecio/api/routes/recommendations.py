"""Recommendation endpoint."""

from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from deprecio.api.dependencies import get_specs_provider
from deprecio.models.device import Device
from deprecio.providers.base import BaseSpecsProvider
from deprecio.recommendations.service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    budget_min_rub: float | None = Field(None, ge=0)
    budget_max_rub: float | None = Field(None, ge=0)
    tier: str | None = None
    brand: str | None = None
    release_year: int | None = Field(None, ge=1970, le=2100)
    min_storage_gb: int | None = Field(None, ge=1)
    required_specs: dict[str, Any] = Field(default_factory=dict)
    preferred_specs: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.budget_min_rub is not None and self.budget_max_rub is not None and self.budget_min_rub > self.budget_max_rub:
            raise ValueError("budget_min_rub не может быть больше budget_max_rub")
        return self


class RecommendationItem(BaseModel):
    device: Device
    price_rub: float
    price_source: str
    score: float
    score_components: dict[str, float]


class RecommendationResponse(BaseModel):
    results: list[RecommendationItem]
    insufficient_data: list[dict[str, Any]]
    total: int


@router.post("", response_model=RecommendationResponse)
async def recommend(request: RecommendationRequest, provider: Annotated[BaseSpecsProvider, Depends(get_specs_provider)]):
    try:
        return await RecommendationService(provider).recommend(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
