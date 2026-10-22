"""Shared pytest fixtures for Junction."""

from __future__ import annotations

from pathlib import Path

import pytest

from fileforge.database.connection import DatabaseManager
from fileforge.database.settings_store import SettingsStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Isolated SQLite path under pytest's temporary directory."""
    return tmp_path / "test_fileforge.db"


@pytest.fixture
def database(db_path: Path) -> DatabaseManager:
    """Initialized database manager that is closed after the test."""
    manager = DatabaseManager(db_path)
    manager.initialize()
    yield manager
    manager.close()


@pytest.fixture
def settings(database: DatabaseManager) -> SettingsStore:
    return SettingsStore(database)
