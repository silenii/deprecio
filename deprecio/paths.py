"""Paths for writable runtime state and its one-time migration."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path


def state_directory() -> Path:
    return Path(os.getenv("DEPRECIO_STATE_DIR", ".state"))


def backup_directory() -> Path:
    return Path(os.getenv("DEPRECIO_BACKUP_DIR", "backups"))


def state_database_path(name: str) -> Path:
    if Path(name).name != name:
        raise ValueError("database name must be a filename")
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    legacy = Path("data") / name
    if target.exists() or directory.resolve() == legacy.parent.resolve() or not legacy.exists():
        return target

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        source = sqlite3.connect(f"{legacy.resolve().as_uri()}?mode=ro", uri=True)
        destination = sqlite3.connect(temporary)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
    return target
