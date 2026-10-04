"""Contract and API tests for budget recommendations."""

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.main import app
from deprecio.api.routes.recommendations import RecommendationRequest
from deprecio.harvester.models import MarketStats
from deprecio.recommendations.service import RecommendationService


class RecommendationProvider:
    def __init__(self, device):
        self.device = device

    def search_devices(self, query):
        return [self.device]

    async def get_market_stats(self, device):
        return MarketStats(model_id=device.model_id, model_name=device.name, clean_listings_count=2, median_price_rub=60000)


@pytest.mark.asyncio
async def test_recommendation_contract_uses_market_price_and_exposes_components(sample_device):
    result = await RecommendationService(RecommendationProvider(sample_device)).recommend(
        budget_max_rub=70000, limit=1
    )
    item = result["results"][0]
    assert item["price_source"] == "market_median"
    assert set(item["score_components"]) == {"budget", "freshness", "residual_value", "specifications"}


def test_recommendation_request_rejects_reversed_budget():
    with pytest.raises(ValidationError):
        RecommendationRequest(budget_min_rub=70000, budget_max_rub=60000)


def test_recommendations_api_uses_isolated_provider(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: RecommendationProvider(sample_device)
    try:
        response = TestClient(app).post(
            "/api/v1/recommendations",
            json={"budget_max_rub": 70000, "limit": 1},
        )
        assert response.status_code == 200
        assert response.json()["results"][0]["price_source"] == "market_median"
    finally:
        app.dependency_overrides.clear()
