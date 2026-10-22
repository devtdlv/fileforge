"""SQLite connection management for Junction."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Self

from fileforge.core.paths import get_default_database_path
from fileforge.database.schema import CURRENT_SCHEMA_VERSION, apply_migrations, get_schema_version


class DatabaseError(Exception):
    """Raised when the application database cannot be initialized or used."""


class DatabaseManager:
    """Owns a SQLite connection with foreign keys and schema migrations."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self._path = Path(database_path) if database_path is not None else get_default_database_path()
        self._connection: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Filesystem path of the SQLite database file."""
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the open connection, or raise if not initialized."""
        if self._connection is None:
            raise DatabaseError("Database is not initialized.")
        return self._connection

    def initialize(self) -> int:
        """Create directories, open the database, enable foreign keys, and migrate.

        Returns:
            The schema version after migrations.

        Raises:
            DatabaseError: If the database cannot be opened or migrated.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            version = apply_migrations(connection)
            self._connection = connection
            return version
        except DatabaseError:
            raise
        except OSError as exc:
            raise DatabaseError(
                f"Unable to create or access the database directory for '{self._path}': {exc}"
            ) from exc
        except sqlite3.Error as exc:
            raise DatabaseError(
                f"Unable to initialize the Junction database at '{self._path}': {exc}"
            ) from exc

    def schema_version(self) -> int:
        """Return the current schema version from an initialized database."""
        return get_schema_version(self.connection)

    def expected_schema_version(self) -> int:
        """Return the schema version this build expects."""
        return CURRENT_SCHEMA_VERSION

    def close(self) -> None:
        """Close the database connection if open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
