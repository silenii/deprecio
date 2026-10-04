from datetime import datetime, timezone

from fastapi.testclient import TestClient

from deprecio.api.dependencies import get_price_history_repository
from deprecio.api.main import app
from deprecio.harvester.models import MarketStats
from deprecio.harvester.aggregator import MarketAggregator
from deprecio.price_history.models import PriceHistoryPoint
from deprecio.price_history.repository import SQLitePriceHistoryRepository


def point(model_id: str, source: str, timestamp: str, price: float) -> PriceHistoryPoint:
    return PriceHistoryPoint(model_id=model_id, source=source, timestamp=datetime.fromisoformat(timestamp),
                             sample_size=4, median_price_rub=price, min_price_rub=price - 100,
                             max_price_rub=price + 100, p25_price_rub=price - 50, p75_price_rub=price + 50)


def test_sqlite_history_is_idempotent_and_sorted(tmp_path):
    repository = SQLitePriceHistoryRepository(tmp_path / "history.db")
    repository.save(point("x", "avito", "2026-01-02T00:00:00+00:00", 120))
    repository.save(point("x", "avito", "2026-01-01T00:00:00+00:00", 100))
    repository.save(point("x", "avito", "2026-01-01T00:00:00+00:00", 110))
    rows = repository.list("x")
    assert [row.median_price_rub for row in rows] == [110, 120]


def test_aggregator_persists_market_stats(tmp_path):
    repository = SQLitePriceHistoryRepository(tmp_path / "history.db")
    stats = MarketStats(model_id="x", model_name="X", clean_listings_count=3,
                        median_price_rub=100, min_price_rub=80, max_price_rub=120)
    saved = MarketAggregator.persist_market_data(stats, "source", repository,
                                                  datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert repository.list("x")[0].model_id == saved.model_id


def test_price_history_api_filters_and_calculates_change(tmp_path):
    repository = SQLitePriceHistoryRepository(tmp_path / "history.db")
    repository.save(point("x", "a", "2026-01-01T00:00:00+00:00", 100))
    repository.save(point("x", "a", "2026-01-02T00:00:00+00:00", 120))
    repository.save(point("x", "b", "2026-01-02T00:00:00+00:00", 200))
    app.dependency_overrides[get_price_history_repository] = lambda: repository
    try:
        response = TestClient(app).get("/api/v1/devices/x/price-history", params={"source": "a"})
        assert response.status_code == 200
        assert response.json()["price_change_percent"] == 20
        assert len(response.json()["chart"]) == 2
    finally:
        app.dependency_overrides.clear()


def test_price_history_empty_and_invalid_period(tmp_path):
    repository = SQLitePriceHistoryRepository(tmp_path / "history.db")
    app.dependency_overrides[get_price_history_repository] = lambda: repository
    try:
        client = TestClient(app)
        assert client.get("/api/v1/devices/missing/price-history").json()["points"] == []
        assert client.get("/api/v1/devices/x/price-history", params={"start": "2026-02-01", "end": "2026-01-01"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
