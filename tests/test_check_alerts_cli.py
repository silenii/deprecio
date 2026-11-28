import asyncio
import json

import pytest
from typer.testing import CliRunner

from deprecio.cli.main import app
from deprecio.price_alerts.models import PriceAlertEvent
from deprecio.price_alerts.repository import SQLitePriceAlertRepository


runner = CliRunner()


def _event():
    return PriceAlertEvent(42, "phone", 90, 100)


def test_check_alerts_logs_triggered_event(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        return [_event()]

    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.delenv("DEPRECIO_BOT_TOKEN", raising=False)
    result = runner.invoke(app, ["check-alerts", "--database", str(tmp_path / "alerts.db")])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["event"] == "price_alert_triggered"


def test_check_alerts_dry_run_does_not_send(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        return [_event()]

    async def send(*args, **kwargs):
        raise AssertionError("Telegram must not be called in dry-run")

    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.setattr("deprecio.cli.main._send_telegram_event", send)
    monkeypatch.setenv("DEPRECIO_BOT_TOKEN", "token")
    result = runner.invoke(app, ["check-alerts", "--dry-run", "--database", str(tmp_path / "alerts.db")])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["dry_run"] is True


def test_check_alerts_returns_error_when_telegram_is_unavailable(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        return [_event()]

    async def send(*args, **kwargs):
        raise OSError("network is unavailable")

    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.setattr("deprecio.cli.main._send_telegram_event", send)
    monkeypatch.setenv("DEPRECIO_BOT_TOKEN", "token")
    database = tmp_path / "alerts.db"
    repository = SQLitePriceAlertRepository(database)
    repository.upsert(42, "phone", 100)
    result = runner.invoke(app, ["check-alerts", "--database", str(database)])

    assert result.exit_code == 1
    assert "price_alert_check_failed" in result.stdout
    assert repository.get(42, "phone").last_notified_price_rub is None


def test_check_alerts_acknowledges_only_after_telegram_delivery(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        return [_event()]

    async def send(*args, **kwargs):
        return None

    database = tmp_path / "alerts.db"
    repository = SQLitePriceAlertRepository(database)
    repository.upsert(42, "phone", 100)
    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.setattr("deprecio.cli.main._send_telegram_event", send)
    monkeypatch.setenv("DEPRECIO_BOT_TOKEN", "token")

    result = runner.invoke(app, ["check-alerts", "--database", str(database)])

    assert result.exit_code == 0
    assert repository.get(42, "phone").last_notified_price_rub == 90



def test_check_alerts_returns_error_on_timeout(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.setenv("DEPRECIO_ALERT_CHECK_TIMEOUT_SEC", "0.001")
    result = runner.invoke(app, ["check-alerts", "--database", str(tmp_path / "alerts.db")])

    assert result.exit_code == 1
    assert "price_alert_check_failed" in result.stdout


def test_alert_worker_retries_after_a_transient_failure(monkeypatch):
    from deprecio.cli.main import _run_alert_worker

    calls = 0
    sleeps = 0

    async def check(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary source failure")

    async def sleep(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr("deprecio.cli.main._check_alerts", check)
    monkeypatch.setattr("deprecio.cli.main.asyncio.sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run_alert_worker(10, 5))

    assert calls == 2


def test_alert_worker_command_uses_configured_interval(monkeypatch):
    settings = {}

    async def run(interval, timeout):
        settings.update(interval=interval, timeout=timeout)

    monkeypatch.setenv("DEPRECIO_BOT_TOKEN", "token")
    monkeypatch.setenv("PRICE_ALERT_CHECK_INTERVAL_SEC", "42")
    monkeypatch.setenv("DEPRECIO_ALERT_CHECK_TIMEOUT_SEC", "17")
    monkeypatch.setattr("deprecio.cli.main._run_alert_worker", run)

    result = runner.invoke(app, ["price-alert-worker"])

    assert result.exit_code == 0
    assert settings == {"interval": 42, "timeout": 17.0}
