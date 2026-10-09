from typer.testing import CliRunner

from deprecio.cli.main import app


def test_harvest_snapshot_persists_with_mocked_harvester(monkeypatch, tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        def get_device(self, model_id):
            return sample_device

    class Repository:
        def __init__(self, path):
            pass

    async def harvest(provider, device, source, repository):
        calls.append((device.model_id, source, repository is not None))

    monkeypatch.setattr("deprecio.cli.main.CachedSpecsProvider", Provider)
    monkeypatch.setattr("deprecio.cli.main.SQLitePriceHistoryRepository", Repository)
    monkeypatch.setattr("deprecio.cli.main._harvest_device", harvest)
    result = CliRunner().invoke(app, ["harvest-snapshot", "--model-id", sample_device.model_id,
                                      "--source", "test", "--catalog", str(catalog)])
    assert result.exit_code == 0
    assert calls == [(sample_device.model_id, "test", True)]


def test_harvest_all_dry_run_does_not_create_repository(monkeypatch, tmp_path, sample_device):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]", encoding="utf-8")
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        def search_devices(self, query):
            return [sample_device]

    def repository(*args, **kwargs):
        raise AssertionError("repository must not be created in dry-run")

    async def harvest(provider, device, source, history):
        calls.append((device.model_id, history))

    monkeypatch.setattr("deprecio.cli.main.CachedSpecsProvider", Provider)
    monkeypatch.setattr("deprecio.cli.main.SQLitePriceHistoryRepository", repository)
    monkeypatch.setattr("deprecio.cli.main._harvest_device", harvest)
    result = CliRunner().invoke(app, ["harvest-all", "--dry-run", "--catalog", str(catalog)])
    assert result.exit_code == 0
    assert calls == [(sample_device.model_id, None)]
