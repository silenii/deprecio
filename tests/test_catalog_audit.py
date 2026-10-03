import json
import sqlite3

from deprecio.catalog_audit import audit_catalog, has_failures


def test_audit_reports_duplicate_and_incomplete_records(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([
        {"model_id": "same-model", "name": "Phone", "brand": "Brand", "lineage": {"series": "X"}, "editions": []},
        {"model_id": "same-model", "name": "", "brand": "", "lineage": {}, "editions": []},
    ]), encoding="utf-8")
    database = tmp_path / "devices.db"
    with sqlite3.connect(database) as db:
        db.execute("create table phones (id text primary key)")
        db.commit()
    report = audit_catalog(catalog, database)
    assert report["duplicates"] == ["same-model"]
    assert any("empty name" in item for item in report["incomplete"])
    assert has_failures(report)


def test_audit_rejects_corrupt_variant_values(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([{
        "model_id": "valid-model", "name": "Phone", "brand": "Brand",
        "lineage": {"series": "X"}, "editions": [{"edition_type": "BAD", "release_date": "2024-99-01",
        "memory_variants": [{"msrp_local": 0, "currency": "XXX"}]}],
    }]), encoding="utf-8")
    database = tmp_path / "devices.db"
    with sqlite3.connect(database) as db:
        db.execute("create table phones (id text primary key)")
    report = audit_catalog(catalog, database)
    assert len(report["errors"]) == 4