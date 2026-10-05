import pytest

from deprecio.harvester.models import MarketStats
from deprecio.price_alerts import PriceAlertService, SQLitePriceAlertRepository


class FakeProvider:
    def __init__(self, price):
        self.price = price

    def get_device(self, model_id):
        return model_id

    async def get_market_stats(self, device):
        return MarketStats(model_id=device, model_name=device, median_price_rub=self.price)


@pytest.mark.asyncio
async def test_price_crossing_threshold_and_repeated_check_is_idempotent(tmp_path):
    repository = SQLitePriceAlertRepository(tmp_path / "alerts.db")
    repository.upsert(1, "phone", 100)
    provider = FakeProvider(120)
    assert await PriceAlertService(repository, provider).check() == []
    provider.price = 100
    events = await PriceAlertService(repository, provider).check()
    assert len(events) == 1
    assert await PriceAlertService(repository, provider).check() == []


@pytest.mark.asyncio
async def test_disabled_alert_is_not_checked(tmp_path):
    repository = SQLitePriceAlertRepository(tmp_path / "alerts.db")
    repository.upsert(1, "phone", 100)
    repository.set_enabled(1, "phone", False)
    assert await PriceAlertService(repository, FakeProvider(50)).check() == []


@pytest.mark.asyncio
async def test_missing_market_result_is_ignored(tmp_path):
    repository = SQLitePriceAlertRepository(tmp_path / "alerts.db")
    repository.upsert(1, "phone", 100)
    assert await PriceAlertService(repository, FakeProvider(0)).check() == []


def test_positive_price_and_subscription_limit(tmp_path):
    repository = SQLitePriceAlertRepository(tmp_path / "alerts.db", max_per_user=1)
    with pytest.raises(ValueError):
        repository.upsert(1, "phone", 0)
    repository.upsert(1, "phone", 100)
    with pytest.raises(ValueError):
        repository.upsert(1, "other", 100)
