"""Deprecio command-line entry point."""

import json
from pathlib import Path

import typer

from deprecio.catalog_audit import audit_catalog, has_failures


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


if __name__ == "__main__":
    app()
