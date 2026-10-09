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
from deprecio.catalog_import import import_catalog
from deprecio.harvester import MarketAggregator
from deprecio.price_history.repository import SQLitePriceHistoryRepository


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


def _catalog_import_command(input_path: Path, catalog: Path, database: Path, report: Path, dry_run: bool) -> None:
    result = import_catalog(input_path, catalog, report, database, dry_run=dry_run)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "ok":
        raise typer.Exit(code=2)


@app.command("catalog-import-preview")
def catalog_import_preview(
    input_path: Path = typer.Argument(..., exists=True),
    catalog: Path = typer.Option(Path("data/catalog.json")),
    report: Path = typer.Option(Path("data/catalog-import-preview.json")),
) -> None:
    """Validate and preview an import without changing catalog or database."""
    _catalog_import_command(input_path, catalog, Path("data/global_devices.db"), report, True)


@app.command("catalog-import")
def catalog_import(
    input_path: Path = typer.Argument(..., exists=True),
    catalog: Path = typer.Option(Path("data/catalog.json")),
    database: Path = typer.Option(Path("data/global_devices.db")),
    report: Path = typer.Option(Path("data/catalog-import-report.json")),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Import validated devices and rebuild the database atomically."""
    _catalog_import_command(input_path, catalog, database, report, dry_run)


@app.command("price-alerts-check")
def price_alerts_check(database: Path = typer.Option(Path("data/price_alerts.db"))) -> None:
    """Check active price subscriptions once and print notification events."""
    service = PriceAlertService(SQLitePriceAlertRepository(database), CachedSpecsProvider())
    for event in asyncio.run(service.check()):
        typer.echo(f"{event.user_id} {event.model_id} {event.current_price_rub:g} руб.")


async def _harvest_device(provider, device, source: str, repository) -> None:
    """Collect, aggregate and optionally persist one market snapshot."""
    from deprecio.harvester.avito_scraper import AvitoScraper
    from deprecio.harvester import SnapshotGenerator

    listings = await AvitoScraper().fetch_and_convert(device.name, device.model_id)
    if not listings:
        listings = SnapshotGenerator.generate_listings(device, count=35)
    stats = MarketAggregator.aggregate_market_data(device, listings)
    if repository is not None:
        MarketAggregator.persist_market_data(stats, source, repository)


@app.command("harvest-snapshot")
def harvest_snapshot(
    model_id: str = typer.Option(..., "--model-id"),
    source: str = typer.Option("avito", "--source"),
    catalog: Path = typer.Option(Path("data/catalog.json")),
    database: Path = typer.Option(Path("data/price_history.db")),
) -> None:
    """Collect and save one market snapshot."""
    provider = CachedSpecsProvider(catalog_file=catalog)
    try:
        device = provider.get_device(model_id)
        asyncio.run(_harvest_device(provider, device, source, SQLitePriceHistoryRepository(database)))
    except Exception as exc:
        typer.echo(f"Ошибка {model_id}: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"Обработано: 1, пропущено: 0, ошибок: 0 ({model_id})")


@app.command("harvest-all")
def harvest_all(
    source: str = typer.Option("avito", "--source"),
    catalog: Path = typer.Option(Path("data/catalog.json")),
    database: Path = typer.Option(Path("data/price_history.db")),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Collect and save snapshots for every catalog device."""
    provider = CachedSpecsProvider(catalog_file=catalog)
    devices = provider.search_devices("")
    repository = None if dry_run else SQLitePriceHistoryRepository(database)
    processed = skipped = errors = 0
    for device in devices:
        try:
            asyncio.run(_harvest_device(provider, device, source, repository))
            processed += 1
        except Exception as exc:
            errors += 1
            typer.echo(f"Ошибка {device.model_id}: {exc}")
    typer.echo(f"Обработано: {processed}, пропущено: {skipped}, ошибок: {errors}")
    if errors:
        raise typer.Exit(code=1)


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
