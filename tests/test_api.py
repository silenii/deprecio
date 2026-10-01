"""HTTP API tests."""

from fastapi.testclient import TestClient

from deprecio.api.dependencies import get_specs_provider
from deprecio.api.main import app


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
    finally:
        app.dependency_overrides.clear()


def test_missing_device_returns_404(sample_device):
    app.dependency_overrides[get_specs_provider] = lambda: FakeProvider(sample_device)
    try:
        response = TestClient(app).get("/api/v1/devices/missing")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
