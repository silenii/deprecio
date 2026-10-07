"""Deprecio command-line entry point."""

import json
import asyncio
from pathlib import Path

import typer
from deprecio.price_alerts import PriceAlertService, SQLitePriceAlertRepository
from deprecio.providers import CachedSpecsProvider

from deprecio.catalog_audit import audit_catalog, has_failures
from deprecio.api.routes.analytics import _device_response
from deprecio.reports import ReportService


app = typer.Typer(help="Deprecio smartphone depreciation analytics.")


@app.callback()
def main() -> None:
    """Run Deprecio commands."""


@app.command("catalog-diagnose")
def catalog_diagnose(
    catalog: Path = typer.Option(Path("data/catalog.json"), exists=False),
    database: Path = typer.Option(Path("data/global_devices.db"), exists=False),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Validate catalog records and their SQLite representation."""
    report = audit_catalog(catalog, database)
    if json_output:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"errors={len(report['errors'])} duplicates={len(report['duplicates'])} "
                   f"incomplete={len(report['incomplete'])} db_mismatches={len(report['database_mismatches'])}")
        for category in ("errors", "duplicates", "incomplete", "database_mismatches"):
            for item in report[category]:
                typer.echo(f"{category}: {item}")
    if has_failures(report):
        raise typer.Exit(code=1)


@app.command("price-alerts-check")
def price_alerts_check(database: Path = typer.Option(Path("data/price_alerts.db"))) -> None:
    """Check active price subscriptions once and print notification events."""
    service = PriceAlertService(SQLitePriceAlertRepository(database), CachedSpecsProvider())
    for event in asyncio.run(service.check()):
        typer.echo(f"{event.user_id} {event.model_id} {event.current_price_rub:g} руб.")


@app.command("report-export")
def report_export(
    model_id: list[str] = typer.Option(..., "--model-id", min=1, max=5),
    format: str = typer.Option("json", "--format"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Export a device card or comparison using local catalog data."""
    provider = CachedSpecsProvider()
    devices = [asyncio.run(_device_response(provider, provider.get_device(item))) for item in model_id]
    content, _media_type = ReportService().render(devices, format)
    if output:
        output.write_bytes(content)
    else:
        typer.echo(content.decode("utf-8-sig"))


if __name__ == "__main__":
    app()
