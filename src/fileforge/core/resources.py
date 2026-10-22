"""Resolve bundled resource paths for source and frozen (PyInstaller) runs."""

from __future__ import annotations

import sys
from pathlib import Path


def package_root() -> Path:
    """Return the ``fileforge`` package root for resource lookup.

    In a PyInstaller onedir build, package data is collected under
    ``sys._MEIPASS/fileforge``. In source runs, this resolves to the installed
    or editable ``src/fileforge`` directory.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "fileforge"
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    """Join one or more path parts under the package resource root."""
    return package_root().joinpath(*parts)


def application_icon_path() -> Path:
    """Return the preferred application icon path (ICO, then PNG fallback)."""
    ico = resource_path("resources", "icons", "Junction.ico")
    if ico.is_file():
        return ico
    png = resource_path("resources", "icons", "junction-256.png")
    return png
