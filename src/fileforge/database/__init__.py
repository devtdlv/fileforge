"""SQLite persistence layer for FileForge."""

from fileforge.database.connection import DatabaseError, DatabaseManager
from fileforge.database.settings_store import SettingsStore

__all__ = [
    "DatabaseError",
    "DatabaseManager",
    "SettingsStore",
]
