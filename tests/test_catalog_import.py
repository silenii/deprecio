import json

from typer.testing import CliRunner

from deprecio.catalog_import import import_catalog
from deprecio.cli.main import app


def test_preview_does_not_modify_catalog(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    original = [sample_device.model_dump(mode="json")]
    catalog.write_text(json.dumps(original), encoding="utf-8")
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps([sample_device.model_dump(mode="json")]), encoding="utf-8")
    result = CliRunner().invoke(app, ["catalog-import-preview", str(incoming), "--catalog", str(catalog)])
    assert result.exit_code == 0
    assert json.loads(catalog.read_text(encoding="utf-8")) == original


def test_import_new_device_rebuilds_database(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps([sample_device.model_dump(mode="json")]), encoding="utf-8")
    report = import_catalog(incoming, catalog, tmp_path / "report.json", tmp_path / "devices.db")
    assert report["added"] == [sample_device.model_id]
    assert (tmp_path / "devices.db").exists()


def test_conflicting_model_ids_fail_without_changes(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    incoming = tmp_path / "incoming.json"
    data = sample_device.model_dump(mode="json")
    incoming.write_text(json.dumps([data, data]), encoding="utf-8")
    report = import_catalog(incoming, catalog, tmp_path / "report.json", tmp_path / "devices.db", dry_run=True)
    assert report["status"] == "error"
    assert report["conflicts"]
    assert catalog.read_text(encoding="utf-8") == "[]"


def test_corrupt_input_returns_error_report(tmp_path):
    incoming = tmp_path / "broken.json"
    incoming.write_text("{", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    report = import_catalog(incoming, catalog, tmp_path / "report.json", tmp_path / "devices.db", dry_run=True)
    assert report["status"] == "error"
    assert report["errors"]
