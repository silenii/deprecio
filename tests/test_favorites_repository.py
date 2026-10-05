from deprecio.favorites import SQLiteFavoritesRepository


def test_favorites_are_unique_and_paginated(tmp_path):
    repository = SQLiteFavoritesRepository(tmp_path / "favorites.db")
    assert repository.add(7, "a")
    assert not repository.add(7, "a")
    for index in range(11):
        repository.add(7, f"m{index}")
    assert len(repository.list(7, limit=10)) == 10
    assert len(repository.list(7, page=1, limit=10)) == 2
    assert repository.remove(7, "a")
    assert not repository.remove(7, "a")
