"""Format already calculated analytics data without transport dependencies."""

import csv
import io
import json
from datetime import datetime, timezone
from html import escape
from typing import Iterable

from deprecio.api.models import AnalyticsDeviceResponse

FORMAT_VERSION = "1.0"


class ReportService:
    """Serialize public analytics responses into stable report formats."""

    def __init__(self, generated_at: datetime | None = None) -> None:
        self.generated_at = (generated_at or datetime.now(timezone.utc)).isoformat()

    def _payload(self, devices: Iterable[AnalyticsDeviceResponse]) -> dict:
        return {
            "report_type": "device_card" if len(list(devices)) == 1 else "comparison",
            "format_version": FORMAT_VERSION,
            "generated_at": self.generated_at,
            "devices": [device.model_dump(mode="json") for device in devices],
        }

    def render(self, devices: Iterable[AnalyticsDeviceResponse], fmt: str) -> tuple[bytes, str]:
        """Return report bytes and its media type for json, csv, html, or markdown."""
        items = list(devices)
        payload = self._payload(items)
        fmt = fmt.lower()
        if fmt == "json":
            return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json"
        if fmt == "csv":
            output = io.StringIO(newline="")
            fields = ("format_version", "generated_at", "model_id", "name", "brand", "tier", "msrp_rub", "current_price_rub",
                      "residual_value_percent", "depreciation_drop_percent", "listings_count")
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for device in items:
                row = device.model_dump(mode="json")
                row["listings_count"] = (row.get("market_stats") or {}).get("listings_count", 0)
                writer.writerow({field: row.get(field) for field in fields} | {
                    "format_version": FORMAT_VERSION, "generated_at": self.generated_at
                })
            return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
        if fmt in {"md", "markdown"}:
            lines = [f"# Deprecio report ({payload['report_type']})", "",
                     f"Format version: {FORMAT_VERSION}", f"Generated at: {self.generated_at}", "",
                     "| Model | Name | MSRP (RUB) | Current (RUB) | Listings |", "|---|---|---:|---:|---:|"]
            for device in items:
                data = device.model_dump(mode="json")
                market = data.get("market_stats") or {}
                name = data["name"].replace("|", "\\|")
                lines.append(f"| {data['model_id']} | {name} | {data['msrp_rub']} | {data['current_price_rub'] or ''} | {market.get('listings_count', 0)} |")
            return "\n".join(lines).encode("utf-8"), "text/markdown; charset=utf-8"
        if fmt == "html":
            rows = "".join(f"<tr><td>{escape(device.model_id)}</td><td>{escape(device.name)}</td><td>{device.msrp_rub}</td><td>{device.current_price_rub or ''}</td><td>{(device.market_stats.listings_count if device.market_stats else 0)}</td></tr>" for device in items)
            html = f"<!doctype html><meta charset='utf-8'><title>Deprecio report</title><h1>Deprecio report</h1><p>Format version: {FORMAT_VERSION}<br>Generated at: {escape(self.generated_at)}</p><table><tr><th>Model</th><th>Name</th><th>MSRP (RUB)</th><th>Current (RUB)</th><th>Listings</th></tr>{rows}</table>"
            return html.encode("utf-8"), "text/html; charset=utf-8"
        raise ValueError(f"Unsupported report format: {fmt}")
