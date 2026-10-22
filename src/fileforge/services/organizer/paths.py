"""Path safety helpers for organization planning and execution."""

from __future__ import annotations

import os
from pathlib import Path


def normalize_path(path: Path | str) -> Path:
    """Return an absolute normalized path without resolving symlinks."""
    return Path(os.path.abspath(os.path.normpath(str(path))))


def casefold_path(path: Path | str) -> str:
    """Case-folded string form for Windows-insensitive comparisons."""
    return os.path.normcase(str(normalize_path(path))).casefold()


def is_same_path(left: Path | str, right: Path | str) -> bool:
    """Return True when two paths refer to the same location on Windows."""
    return casefold_path(left) == casefold_path(right)


def is_within(path: Path | str, root: Path | str) -> bool:
    """Return True when *path* is *root* or a descendant of *root*."""
    candidate = normalize_path(path)
    base = normalize_path(root)
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        # Case-insensitive fallback for Windows path quirks.
        cand = casefold_path(candidate)
        base_cf = casefold_path(base)
        return cand == base_cf or cand.startswith(base_cf + os.sep.casefold())


def relative_display_path(path: Path | str, root: Path | str | None) -> str:
    """Return a POSIX-style path relative to *root* for UI display.

    Absolute paths remain the source of truth for execution. When *path* is not
    under *root*, fall back to the file name so the table stays readable.
    """
    path_n = normalize_path(path)
    if root is None:
        return path_n.name or str(path_n)
    root_n = normalize_path(root)
    try:
        return path_n.relative_to(root_n).as_posix()
    except ValueError:
        # Case-insensitive membership for Windows, then build a relative string.
        if is_within(path_n, root_n):
            try:
                return Path(os.path.relpath(str(path_n), str(root_n))).as_posix()
            except ValueError:
                pass
        return path_n.name or str(path_n)


def ensure_not_symlink_or_junction(path: Path) -> None:
    """Raise ValueError when *path* is a symlink or Windows junction."""
    if path.is_symlink():
        raise ValueError(f"Refusing to use symbolic link: {path}")
    isjunction = getattr(os.path, "isjunction", None)
    if callable(isjunction):
        try:
            if isjunction(path):
                raise ValueError(f"Refusing to use directory junction: {path}")
        except OSError as exc:
            raise ValueError(f"Unable to inspect path: {path}: {exc}") from exc
