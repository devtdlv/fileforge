"""Key/value settings persistence backed by SQLite."""

from __future__ import annotations

import sqlite3

from fileforge.database.connection import DatabaseManager


class SettingsStore:
    """Read and write application settings using parameterized SQL."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _connection(self) -> sqlite3.Connection:
        return self._database.connection

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return a setting value, or ``default`` when the key is absent."""
        row = self._connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value"])

    def set(self, key: str, value: str) -> None:
        """Insert or update a setting value."""
        self._connection.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value),
        )
        self._connection.commit()

    def delete(self, key: str) -> bool:
        """Delete a setting. Returns True if a row was removed."""
        cursor = self._connection.execute(
            "DELETE FROM settings WHERE key = ?",
            (key,),
        )
        self._connection.commit()
        return cursor.rowcount > 0

    def all(self) -> dict[str, str]:
        """Return all settings as a dictionary."""
        rows = self._connection.execute(
            "SELECT key, value FROM settings ORDER BY key"
        ).fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}
