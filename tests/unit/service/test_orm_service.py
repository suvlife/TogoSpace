from __future__ import annotations

import os
import re
import sqlite3

import pytest

import appPaths
from service import ormService


def test_backup_database_creates_timestamped_copy_under_backups_dir(tmp_path, monkeypatch) -> None:
    source_db_path = tmp_path / "runtime.db"
    with sqlite3.connect(source_db_path) as conn:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT INTO demo (name) VALUES (?)", ("alice",))
        conn.commit()

    data_dir = tmp_path / "data"
    monkeypatch.setattr(appPaths, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(ormService, "_db_path", str(source_db_path))

    backup_path = ormService.backup_database()

    assert os.path.isfile(backup_path)
    assert os.path.dirname(backup_path) == os.path.join(str(data_dir), "backups")
    assert re.fullmatch(r"runtime_\d{8}_\d{6}_\d{6}\.db", os.path.basename(backup_path))

    with sqlite3.connect(backup_path) as conn:
        rows = conn.execute("SELECT id, name FROM demo").fetchall()
    assert rows == [(1, "alice")]


def test_backup_database_requires_started_orm(monkeypatch) -> None:
    monkeypatch.setattr(ormService, "_db_path", None)

    with pytest.raises(RuntimeError, match="ormService not started"):
        ormService.backup_database()
