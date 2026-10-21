"""Application data path helpers."""

from __future__ import annotations

from pathlib import Path

from fileforge.core.paths import get_app_data_dir, get_default_database_path


def test_app_data_dir_is_under_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app_dir = get_app_data_dir()
    assert app_dir == tmp_path / "FileForge"
    assert app_dir.is_dir()
    assert get_default_database_path() == app_dir / "fileforge.db"
