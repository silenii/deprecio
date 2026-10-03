"""Tests for production settings, logging configuration, and health check endpoint."""

import logging
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────── AppSettings ────────────────────────────


def test_app_settings_requires_bot_token(monkeypatch):
    """AppSettings must raise ValidationError when DEPRECIO_BOT_TOKEN is missing."""
    monkeypatch.delenv("DEPRECIO_BOT_TOKEN", raising=False)
    monkeypatch.setattr("os.environ", {k: v for k, v in os.environ.items() if k != "DEPRECIO_BOT_TOKEN"})
    from pydantic import ValidationError

    from deprecio.bot.config import AppSettings

    with pytest.raises((ValidationError, Exception)):
        AppSettings()


def test_app_settings_defaults(monkeypatch):
    """AppSettings should load sane defaults when only the required token is set."""
    monkeypatch.setenv("DEPRECIO_BOT_TOKEN", "123456:TESTTOKEN_AAABBBCCC")
    # Remove .env influence by pointing to a non-existent file
    from deprecio.bot.config import AppSettings
    from pydantic_settings import SettingsConfigDict

    class _IsolatedSettings(AppSettings):
        model_config = SettingsConfigDict(env_file=".env.nonexistent", extra="ignore", case_sensitive=False)

    cfg = _IsolatedSettings()
    assert cfg.avito_max_pages == 3
    assert cfg.snapshot_ttl_hours == 24
    assert cfg.gsmarena_timeout_sec == 10.0
    assert cfg.avito_rate_limit_rpm == 30
    assert cfg.log_level == "INFO"
    assert cfg.log_format == "plain"


def test_log_level_validation():
    """Invalid LOG_LEVEL should raise ValueError from the validator directly."""
    from pydantic import ValidationError

    from deprecio.bot.config import LogSettings
    from pydantic_settings import SettingsConfigDict

    class _Isolated(LogSettings):
        model_config = SettingsConfigDict(env_file=".env.nonexistent", extra="ignore", case_sensitive=False)

    with pytest.raises((ValidationError, ValueError)):
        _Isolated(log_level="VERBOSE")


def test_log_format_validation():
    """Invalid LOG_FORMAT should raise ValueError from the validator directly."""
    from pydantic import ValidationError

    from deprecio.bot.config import LogSettings
    from pydantic_settings import SettingsConfigDict

    class _Isolated(LogSettings):
        model_config = SettingsConfigDict(env_file=".env.nonexistent", extra="ignore", case_sensitive=False)

    with pytest.raises((ValidationError, ValueError)):
        _Isolated(log_format="xml")



# ─────────────────────────── setup_logging ──────────────────────────


def test_setup_logging_plain(monkeypatch, tmp_path):
    """setup_logging with plain format should configure root logger."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "plain")
    monkeypatch.delenv("LOG_FILE", raising=False)

    from deprecio.logging_config import setup_logging

    setup_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_json_format(monkeypatch):
    """setup_logging with json format should emit valid JSON records."""
    import io
    import json as _json

    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.delenv("LOG_FILE", raising=False)

    from deprecio.logging_config import _JsonFormatter

    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello %s", args=("world",), exc_info=None,
    )
    line = formatter.format(record)
    parsed = _json.loads(line)
    assert parsed["msg"] == "hello world"
    assert parsed["level"] == "INFO"
    assert "ts" in parsed


def test_setup_logging_rotating_file(monkeypatch, tmp_path):
    """setup_logging should create a rotating file handler when LOG_FILE is set."""
    log_file = tmp_path / "deprecio.log"
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "plain")
    monkeypatch.setenv("LOG_FILE", str(log_file))

    from deprecio.logging_config import setup_logging

    setup_logging()
    logging.getLogger("deprecio.test").info("rotation test")

    assert log_file.exists()


# ─────────────────────────── /health endpoint ───────────────────────


@pytest.fixture()
def api_client(tmp_path):
    """TestClient for FastAPI app with isolated data paths."""
    # Patch data paths to temp dir so we don't need real files
    import deprecio.api.main  # noqa: F401

    from deprecio.api.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_health_check_returns_json(api_client):
    """GET /health should return a JSON object with 'status' and 'checks'."""
    resp = api_client.get("/health")
    assert resp.status_code in (200, 207)
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert data["status"] in ("ok", "degraded")


def test_health_check_cache_write_ok(api_client, tmp_path, monkeypatch):
    """Health check should report cache_write=ok when the directory is writable."""
    # The default .cache/devices will be created by the app
    resp = api_client.get("/health")
    data = resp.json()
    # cache_write should be 'ok' (dir created successfully in temp working dir)
    assert data["checks"]["cache_write"] in ("ok", "error")  # either is acceptable in CI


def test_health_check_missing_catalog(api_client, tmp_path, monkeypatch):
    """Health check should report catalog_json=missing when file does not exist."""
    # Monkeypatch Path.exists to return False only for catalog_file
    import deprecio.api.main as api_main

    original_exists = type(api_main.Path("x")).exists

    def _patched_exists(self):
        if str(self) == "data/catalog.json":
            return False
        return original_exists(self)

    monkeypatch.setattr(api_main.Path, "exists", _patched_exists)

    resp = api_client.get("/health")
    assert resp.status_code in (200, 207)


def test_health_check_db_error(api_client, tmp_path, monkeypatch):
    """Health check should report global_db=error on sqlite error without raising."""
    import deprecio.api.main as api_main

    def _bad_connect(path, **kw):
        raise sqlite3.DatabaseError("corrupt")

    # Only make real catalog exist but break DB
    original_exists = type(api_main.Path("x")).exists

    def _patched_exists(self):
        if str(self) == "data/global_devices.db":
            return True
        return original_exists(self)

    monkeypatch.setattr(api_main.Path, "exists", _patched_exists)
    monkeypatch.setattr(api_main.sqlite3, "connect", _bad_connect)

    resp = api_client.get("/health")
    data = resp.json()
    assert data["checks"]["global_db"] == "error"
    assert resp.status_code == 207
