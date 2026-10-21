"""Per-user application data paths for FileForge."""

from __future__ import annotations

import os
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return the per-user local application-data directory for FileForge.

    On Windows this resolves under ``%LOCALAPPDATA%\\FileForge``.
    The directory is created if it does not already exist.
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    app_dir = base / "FileForge"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_default_database_path() -> Path:
    """Return the default SQLite database path under the app-data directory."""
    return get_app_data_dir() / "fileforge.db"
