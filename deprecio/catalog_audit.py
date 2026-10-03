"""Validation and reproducible checks for the local device catalog."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

VALID_CURRENCIES = {"CNY", "USD", "EUR", "RUB"}
VALID_EDITIONS = {"CN", "EAC_ROSTEST", "GLOBAL_EU", "US", "IN", "OTHER"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def audit_catalog(catalog_path: Path, database_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"errors": [], "duplicates": [], "incomplete": [], "database_mismatches": []}
    try:
        records = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report["errors"].append(f"catalog: {exc}")
        return report
    if not isinstance(records, list):
        report["errors"].append("catalog: root must be a list")
        return report

    ids = [item.get("model_id") for item in records if isinstance(item, dict)]
    report["duplicates"] = sorted(k for k, v in Counter(ids).items() if k and v > 1)
    for index, item in enumerate(records):
        prefix = f"record {index}"
        if not isinstance(item, dict):
            report["incomplete"].append(f"{prefix}: object expected")
            continue
        for field in ("model_id", "name", "brand"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                report["incomplete"].append(f"{prefix}: empty {field}")
        model_id = item.get("model_id")
        if isinstance(model_id, str) and not ID_RE.fullmatch(model_id):
            report["errors"].append(f"{prefix}: invalid model_id {model_id!r}")
        lineage = item.get("lineage")
        if not isinstance(lineage, dict) or not str(lineage.get("series", "")).strip():
            report["incomplete"].append(f"{prefix}: empty lineage.series")
        editions = item.get("editions")
        if not isinstance(editions, list) or not editions:
            report["incomplete"].append(f"{prefix}: no editions")
            continue
        for edition_index, edition in enumerate(editions):
            ep = f"{prefix} edition {edition_index}"
            if edition.get("edition_type") not in VALID_EDITIONS:
                report["errors"].append(f"{ep}: invalid edition_type")
            release = edition.get("release_date")
            if release is not None:
                try:
                    date.fromisoformat(release)
                except (TypeError, ValueError):
                    report["errors"].append(f"{ep}: invalid release_date {release!r}")
            for variant_index, variant in enumerate(edition.get("memory_variants", [])):
                vp = f"{ep} variant {variant_index}"
                if variant.get("currency") not in VALID_CURRENCIES:
                    report["errors"].append(f"{vp}: invalid currency")
                price = variant.get("msrp_local")
                if not isinstance(price, (int, float)) or price <= 0:
                    report["errors"].append(f"{vp}: MSRP must be positive")

    try:
        with sqlite3.connect(database_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(phones)")}
            if "id" not in columns:
                report["errors"].append("database: phones.id is missing")
            else:
                db_ids = {row[0] for row in connection.execute("SELECT id FROM phones")}
                report["database_mismatches"] = sorted(set(ids) - db_ids)
    except (OSError, sqlite3.Error) as exc:
        report["errors"].append(f"database: {exc}")
    return report


def has_failures(report: dict[str, Any]) -> bool:
    return any(report[key] for key in ("errors", "duplicates", "incomplete", "database_mismatches"))