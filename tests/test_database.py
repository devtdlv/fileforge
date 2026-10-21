"""Database initialization, schema versioning, and settings tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from fileforge.database.connection import DatabaseError, DatabaseManager
from fileforge.database.schema import CURRENT_SCHEMA_VERSION
from fileforge.database.settings_store import SettingsStore


def test_initialize_creates_database_file(db_path: Path) -> None:
    manager = DatabaseManager(db_path)
    version = manager.initialize()
    try:
        assert db_path.is_file()
        assert version == CURRENT_SCHEMA_VERSION
        assert manager.schema_version() == CURRENT_SCHEMA_VERSION
    finally:
        manager.close()


def test_schema_version_is_idempotent(db_path: Path) -> None:
    first = DatabaseManager(db_path)
    first.initialize()
    first.close()

    second = DatabaseManager(db_path)
    version = second.initialize()
    try:
        assert version == CURRENT_SCHEMA_VERSION
        assert second.schema_version() == CURRENT_SCHEMA_VERSION
    finally:
        second.close()


def test_settings_persistence(database: DatabaseManager) -> None:
    store = SettingsStore(database)
    store.set("theme", "light")
    store.set("theme", "system")
    assert store.get("theme") == "system"
    assert store.get("missing", "fallback") == "fallback"
    assert store.delete("theme") is True
    assert store.get("theme") is None
    assert store.delete("theme") is False


def test_settings_all_returns_sorted_keys(database: DatabaseManager) -> None:
    store = SettingsStore(database)
    store.set("b", "2")
    store.set("a", "1")
    assert store.all() == {"a": "1", "b": "2"}


def test_database_path_isolation(tmp_path: Path) -> None:
    path_a = tmp_path / "a" / "one.db"
    path_b = tmp_path / "b" / "two.db"

    db_a = DatabaseManager(path_a)
    db_b = DatabaseManager(path_b)
    db_a.initialize()
    db_b.initialize()
    try:
        SettingsStore(db_a).set("scope", "a")
        SettingsStore(db_b).set("scope", "b")
        assert SettingsStore(db_a).get("scope") == "a"
        assert SettingsStore(db_b).get("scope") == "b"
        assert path_a != path_b
        assert path_a.is_file()
        assert path_b.is_file()
    finally:
        db_a.close()
        db_b.close()


def test_foreign_keys_enabled(database: DatabaseManager) -> None:
    row = database.connection.execute("PRAGMA foreign_keys").fetchone()
    assert row is not None
    assert int(row[0]) == 1


def test_operation_journal_table_exists(database: DatabaseManager) -> None:
    row = database.connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'operation_journal'
        """
    ).fetchone()
    assert row is not None


def test_connection_before_initialize_raises(db_path: Path) -> None:
    manager = DatabaseManager(db_path)
    with pytest.raises(DatabaseError, match="not initialized"):
        _ = manager.connection


def test_initialize_rejects_file_as_parent_directory(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("blocked", encoding="utf-8")
    bad_path = blocker / "fileforge.db"
    manager = DatabaseManager(bad_path)
    with pytest.raises(DatabaseError):
        manager.initialize()
