"""Schema definitions and versioned migrations for Junction."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence

# Current schema version applied by the migrator.
CURRENT_SCHEMA_VERSION = 2

Migration = Callable[[sqlite3.Connection], None]


def _migration_001(connection: sqlite3.Connection) -> None:
    """Create the initial settings and operation journal tables."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS operation_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_operation_journal_created_at
            ON operation_journal (created_at DESC);
        """
    )


def _migration_002(connection: sqlite3.Connection) -> None:
    """Add batch/entry tables for detailed organization journaling."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS operation_batches (
            id TEXT PRIMARY KEY NOT NULL,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            source_root TEXT NOT NULL DEFAULT '',
            destination_root TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            details_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS operation_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            operation_type TEXT NOT NULL DEFAULT 'move',
            source_path TEXT NOT NULL,
            destination_path TEXT NOT NULL,
            status TEXT NOT NULL,
            error_details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (batch_id) REFERENCES operation_batches(id)
        );

        CREATE INDEX IF NOT EXISTS idx_operation_entries_batch_id
            ON operation_entries (batch_id);

        CREATE INDEX IF NOT EXISTS idx_operation_batches_created_at
            ON operation_batches (created_at DESC);
        """
    )


MIGRATIONS: Sequence[tuple[int, Migration]] = (
    (1, _migration_001),
    (2, _migration_002),
)


def get_schema_version(connection: sqlite3.Connection) -> int:
    """Return the recorded schema version, or 0 if uninitialized."""
    row = connection.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    ).fetchone()
    if row is None:
        return 0
    return int(row[0])


def ensure_schema_version_table(connection: sqlite3.Connection) -> None:
    """Create the schema_version bookkeeping table if needed."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_version (id, version)
        VALUES (1, 0)
        """
    )


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Apply pending migrations and return the resulting schema version."""
    ensure_schema_version_table(connection)
    current = get_schema_version(connection)

    for version, migration in MIGRATIONS:
        if version <= current:
            continue
        migration(connection)
        connection.execute(
            "UPDATE schema_version SET version = ? WHERE id = 1",
            (version,),
        )
        current = version

    connection.commit()
    return current
