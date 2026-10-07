"""Validated, report-producing catalog imports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from deprecio.models.device import Device


def _legacy_device(item: dict[str, Any], index: int) -> dict[str, Any]:
    required = ("brand_name", "model", "processor_brand", "ram_capacity", "internal_memory")
    missing = [key for key in required if not str(item.get(key, "")).strip()]
    if missing:
        raise ValueError(f"legacy record {index}: missing {', '.join(missing)}")
    model = str(item["model"]).strip()
    brand = str(item["brand_name"]).strip()
    raw_id = item.get("model_id") or f"{brand}-{model}"
    model_id = "-".join("".join(ch.lower() if ch.isalnum() else "-" for ch in str(raw_id)).split("-"))
    price = item.get("msrp_local")
    if price is None:
        raise ValueError(f"legacy record {index}: msrp_local is required")
    return {
        "model_id": model_id.strip("-"), "name": model, "brand": brand,
        "chipset": str(item["processor_brand"]),
        "lineage": {"series": model.split()[0], "tier": "Mid-range"},
        "editions": [{"edition_type": "OTHER", "release_date": item.get("release_date"),
                      "memory_variants": [{"ram_gb": int(item["ram_capacity"]),
                                           "storage_gb": int(item["internal_memory"]),
                                           "msrp_local": float(price),
                                           "currency": item.get("currency", "RUB")}]}],
        "forecast_profile": item.get("forecast_profile", {}),
    }


def load_input(path: Path) -> list[Device]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"input: {exc}") from exc
    if isinstance(raw, dict):
        raw = raw.get("devices")
    if not isinstance(raw, list):
        raise ValueError("input: root must be a list or an object with devices")
    devices: list[Device] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"record {index}: object expected")
        if "lineage" not in item or "editions" not in item:
            item = _legacy_device(item, index)
        try:
            devices.append(Device.model_validate(item))
        except ValidationError as exc:
            raise ValueError(f"record {index}: {exc}") from exc
    duplicate_ids = sorted(model_id for model_id, count in Counter(d.model_id for d in devices).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"duplicate model_id in input: {', '.join(duplicate_ids)}")
    return devices


def import_catalog(input_path: Path, catalog_path: Path, report_path: Path,
                   database_path: Path, dry_run: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "error", "added": [], "updated": [],
                              "skipped": [], "conflicts": [], "errors": [], "dry_run": dry_run}
    try:
        incoming = load_input(input_path)
        existing_raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(existing_raw, list):
            raise ValueError("catalog: root must be a list")
        existing = {item["model_id"]: item for item in existing_raw}
        merged = list(existing_raw)
        positions = {item["model_id"]: index for index, item in enumerate(merged)}
        for device in incoming:
            data = device.model_dump(mode="json")
            if device.model_id in positions:
                if existing[device.model_id] == data:
                    report["skipped"].append(device.model_id)
                else:
                    merged[positions[device.model_id]] = data
                    report["updated"].append(device.model_id)
            else:
                positions[device.model_id] = len(merged)
                merged.append(data)
                report["added"].append(device.model_id)
        if not dry_run:
            temp_catalog = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
            temp_catalog.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            builder = Path(__file__).resolve().parents[1] / "scripts" / "build_global_db.py"
            subprocess.run([sys.executable, str(builder), "--catalog", str(temp_catalog), "--output", str(database_path)], check=True)
            os.replace(temp_catalog, catalog_path)
        report["status"] = "ok"
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        report["errors"].append(str(exc))
        report["conflicts"].append(str(exc)) if "duplicate model_id" in str(exc) else None
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
