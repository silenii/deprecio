import json
import sqlite3
import pytest

from typer.testing import CliRunner

from deprecio.catalog_import import import_catalog
from deprecio.cli.main import app
from scripts.build_global_db import build_catalog_db, merge_catalog_db


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


def test_catalog_database_build_preserves_exact_ids_and_full_records(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([sample_device.model_dump(mode="json")]), encoding="utf-8")
    database = tmp_path / "devices.db"

    build_catalog_db(catalog, database)

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT brand, name, raw_specs FROM phones WHERE id = ?", (sample_device.model_id,)
        ).fetchone()
        assert row is not None
        assert row[0:2] == (sample_device.brand, sample_device.name)
        assert json.loads(row[2])["model_id"] == sample_device.model_id
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_catalog_database_build_rejects_duplicate_ids_without_replacing_existing_db(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    record = sample_device.model_dump(mode="json")
    catalog.write_text(json.dumps([record, record]), encoding="utf-8")
    database = tmp_path / "devices.db"
    database.write_bytes(b"existing database")

    with pytest.raises(ValueError, match="duplicate model_id"):
        build_catalog_db(catalog, database)

    assert database.read_bytes() == b"existing database"


def test_merge_catalog_preserves_global_rows_and_rebuilds_search_index(tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([sample_device.model_dump(mode="json")]), encoding="utf-8")
    database = tmp_path / "devices.db"
    build_catalog_db(catalog, database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO phones VALUES ('global-phone', 'Brand', 'Global Phone', 'brand global phone', '', '', '{}')"
        )
        connection.execute("INSERT INTO phones_fts(phones_fts) VALUES('rebuild')")
        connection.commit()
    finally:
        connection.close()
    merge_catalog_db(catalog, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM phones").fetchone()[0] == 2
        assert connection.execute("SELECT id FROM phones WHERE id = 'global-phone'").fetchone()[0] == "global-phone"
        assert connection.execute(
            "SELECT id FROM phones_fts WHERE phones_fts MATCH 'xiaomi 14'"
        ).fetchone()[0] == sample_device.model_id
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_cached_provider_exact_id_does_not_fuzzy_match_another_device(tmp_path):
    database = tmp_path / "devices.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE phones (id TEXT, brand TEXT, name TEXT, raw_specs TEXT, clean_name TEXT)")
        connection.execute("INSERT INTO phones VALUES ('mod-xiaomi-14', 'Xiaomi', 'Xiaomi 14', '{}', 'xiaomi 14')")

    from deprecio.providers.cached_provider import CachedSpecsProvider
    from deprecio.providers.exceptions import DeviceNotFoundError
    provider = CachedSpecsProvider(cache_dir=tmp_path / "cache", catalog_file=tmp_path / "missing.json", global_db_file=database)

    with pytest.raises(DeviceNotFoundError):
        provider.get_device("xiaomi-14-probe")


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
