import asyncio
import json

from typer.testing import CliRunner

from deprecio.cli.main import app
from deprecio.price_alerts.models import PriceAlertEvent


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
    result = runner.invoke(app, ["check-alerts", "--database", str(tmp_path / "alerts.db")])

    assert result.exit_code == 1
    assert "price_alert_check_failed" in result.stdout



def test_check_alerts_returns_error_on_timeout(monkeypatch, tmp_path):
    async def check(*args, **kwargs):
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr("deprecio.cli.main.PriceAlertService.check", check)
    monkeypatch.setenv("DEPRECIO_ALERT_CHECK_TIMEOUT_SEC", "0.001")
    result = runner.invoke(app, ["check-alerts", "--database", str(tmp_path / "alerts.db")])

    assert result.exit_code == 1
    assert "price_alert_check_failed" in result.stdout
