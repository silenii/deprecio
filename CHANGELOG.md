# Changelog

## [1.0.0] - 2026-10-10

First stable release of the Deprecio analytics platform.

- Priorities 1-10: established the domain model, catalog, cleaning rules, analytics core, FastAPI API, Telegram bot, web client, Android client skeleton, CI, Docker packaging, and technical-quality baseline.
- Priority 11: added market-price history, SQLite storage, idempotent snapshots, and filtered time-series API access.
- Priority 19: expanded coverage for external providers and fallback behavior.
- Priority 20: removed the Starlette/httpx compatibility warning from the test client path.
- Priority 21: added market snapshot harvesting and CLI commands.
- Priority 22: added scheduled price-alert checks with dry-run support.
- Priority 23: improved the vanilla analytics web client and its loading, empty, error, recommendation, and comparison flows.
- Priority 24: added the React Native + Expo Android client skeleton with REST access, local favorites, navigation, and themes.
- Priority 25: added production health checks, metrics, backups, structured logging, non-root Docker execution, and CI validation.
- Priority 26: promoted the package and API metadata to stable version 1.0.0, raised CI coverage enforcement to 80%, and documented release/security checks.
