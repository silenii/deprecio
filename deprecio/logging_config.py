"""Centralized logging configuration for Deprecio.

Supports two formats controlled by LOG_FORMAT env var:
  plain  - human-readable (default for development)
  json   - structured JSON lines (recommended for production / log aggregators)

Usage:
    from deprecio.logging_config import setup_logging
    setup_logging()
"""

import logging
import logging.handlers
import os
import json as _json
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Forward any extra fields attached via LogRecord.__dict__
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message", "module",
                "msecs", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName",
            ):
                try:
                    _json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        return _json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """Configure root logger from environment variables.

    Environment variables:
        LOG_LEVEL   - DEBUG / INFO / WARNING / ERROR / CRITICAL  (default: INFO)
        LOG_FORMAT  - plain / json                                (default: plain)
        LOG_FILE    - path to log file; rotation at 10 MB, 5 backups (optional)
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = os.environ.get("LOG_FORMAT", "plain").lower()

    if fmt == "json":
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handlers: list[logging.Handler] = []

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    handlers.append(console)

    # Optional rotating file handler
    log_file = os.environ.get("LOG_FILE", "")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "aiogram.event"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
