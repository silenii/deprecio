from datetime import datetime, timezone

from deprecio.api.models import AnalyticsDeviceResponse
from deprecio.reports import ReportService
from deprecio.api.dependencies import get_specs_provider
from deprecio.api.main import app
from fastapi.testclient import TestClient


def device(name="Phone | Pro", model_id="phone-1"):
    return AnalyticsDeviceResponse(model_id=model_id, name=name, brand="Brand", tier="Flagship",
        characteristics={}, msrp_rub=100, current_price_rub=None,
        residual_value_percent=None, depreciation_drop_percent=None, forecast_summary=None,
        market_stats=None)


def test_all_formats_include_version_date_and_safe_public_data():
    service = ReportService(datetime(2026, 1, 2, tzinfo=timezone.utc))
    for fmt in ("json", "csv", "html", "md"):
        content, media_type = service.render([device()], fmt)
        text = content.decode("utf-8-sig")
        assert "1.0" in text
        assert "2026-01-02" in text
        assert "Phone" in text
        assert "internal" not in text
        assert media_type


def test_multiple_devices_and_empty_market_stats():
    content, _ = ReportService().render([device(model_id="a"), device(model_id="b")], "csv")
    text = content.decode("utf-8-sig")
    assert "a" in text and "b" in text
    assert text.count("\n") == 3


def test_report_endpoint_supports_download_formats(sample_device):
    class Provider:
        def get_device(self, model_id):
            return sample_device

    app.dependency_overrides[get_specs_provider] = Provider
    try:
        response = TestClient(app).get("/api/v1/reports/xiaomi-14", params={"format": "csv"})
        assert response.status_code == 200
        assert response.headers["content-disposition"].endswith('xiaomi-14.csv"')
    finally:
        app.dependency_overrides.clear()
