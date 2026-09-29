"""Deprecio command-line entry point."""

import typer


app = typer.Typer(help="Deprecio smartphone depreciation analytics.")


@app.callback()
def main() -> None:
    """Run Deprecio commands."""
