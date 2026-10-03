"""HTTP API tests."""

from fastapi.testclient import TestClient

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.main import app


def test_fastapi_application_starts():
    """The application imports and exposes its health endpoint."""
    routes = {path for route in app.routes if (path := getattr(route, "path", None))}

    assert app.title == "Deprecio API"
    assert "/health" in routes


class FakeProvider:
    def __init__(self, device):
        self.device = device

    def get_device(self, model_id):
        if model_id != self.device.model_id:
            from deprecio.providers.exceptions import DeviceNotFoundError

            raise DeviceNotFoundError(model_id)
        return self.device

    def search_devices(self, query):
        return [self.device] if query.lower() in self.device.name.lower() else []


def test_device_search_and_card(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        client = TestClient(app)
        search = client.get("/api/v1/devices/search", params={"query": "Xiaomi 14"})
        card = client.get("/api/v1/devices/xiaomi-14")
        assert search.status_code == 200
        assert search.json()[0]["model_id"] == "xiaomi-14"
        assert card.status_code == 200
        assert card.json()["name"] == "Xiaomi 14"
    finally:
        app.dependency_overrides.clear()


def test_forecast_endpoint(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get(
            "/api/v1/forecast/xiaomi-14",
            params={"current_price_rub": 70000, "months_horizon": 2},
        )
        assert response.status_code == 200
        assert len(response.json()["points"]) == 2
        assert response.json()["points"][0]["predicted_rv_percent"] < 100
    finally:
        app.dependency_overrides.clear()


def test_missing_device_returns_404(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get("/api/v1/devices/missing")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_default_provider_searches_existing_catalog_without_override():
    response = TestClient(app).get("/api/v1/devices/search", params={"query": "Xiaomi 14"})

    assert response.status_code == 200
    assert any(device["model_id"] == "xiaomi-14" for device in response.json())


def test_default_provider_returns_device_card_without_override():
    response = TestClient(app).get("/api/v1/devices/xiaomi-14")

    assert response.status_code == 200
    assert response.json()["model_id"] == "xiaomi-14"


def test_default_provider_returns_404_for_unknown_device_without_override():
    response = TestClient(app).get("/api/v1/devices/not-in-catalog")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Device not found"}


def test_health_check():
    response = TestClient(app).get("/health")

    assert response.status_code in (200, 207)
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "checks" in data
    assert "cache_write" in data["checks"]


def test_empty_search_is_rejected():
    response = TestClient(app).get("/api/v1/devices/search", params={"query": ""})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_search_query_length_is_limited():
    response = TestClient(app).get("/api/v1/devices/search", params={"query": "x" * 101})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_forecast_negative_price_returns_bad_request(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get(
            "/api/v1/forecast/xiaomi-14", params={"current_price_rub": -1}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "http_error"
    finally:
        app.dependency_overrides.clear()


def test_forecast_too_large_horizon_returns_bad_request(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get(
            "/api/v1/forecast/xiaomi-14",
            params={"current_price_rub": 70000, "months_horizon": 121},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "http_error"
    finally:
        app.dependency_overrides.clear()


def test_unknown_forecast_device_returns_not_found(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get(
            "/api/v1/forecast/missing", params={"current_price_rub": 70000}
        )
        assert response.status_code == 404
        assert response.json() == {"code": "not_found", "message": "Device not found"}
    finally:
        app.dependency_overrides.clear()
