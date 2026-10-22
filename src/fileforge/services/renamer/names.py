"""Filename stem/extension policy and Windows validation."""

from __future__ import annotations

import re
from pathlib import Path

# Windows reserved device names (case-insensitive), with or without extension.
_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# Characters illegal in Windows file names (not including path separators —
# proposed names are basename-only).
_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Practical MAX_PATH-style limit for a full path on modern Windows with long
# paths disabled. We warn/reject when the absolute destination would exceed this.
MAX_PATH_CHARS = 260


def split_filename(name: str) -> tuple[str, str]:
    """Split a basename into (stem, extension) with a documented policy.

    Policy (Python ``Path`` conventions, applied to the basename only):

    - The extension is the final ``.suffix`` including the leading dot.
    - Multi-dot names keep earlier dots in the stem
      (``archive.tar.gz`` → stem ``archive.tar``, ext ``.gz``).
    - Extensionless names use an empty extension (``README`` → ``README``, ````).
    - Dotfiles without a further suffix keep the whole name as the stem
      (``.gitignore`` → stem ``.gitignore``, ext ````).
    - ``.env.local`` → stem ``.env``, ext ``.local``.

    The extension's original casing is preserved by callers; case transforms
    apply to the stem only by default.
    """
    if not name or name in {".", ".."}:
        return name, ""
    path = Path(name)
    # Path('file').suffix is ''; Path('file.txt').suffix is '.txt'
    suffix = path.suffix
    if not suffix:
        return name, ""
    stem = name[: -len(suffix)]
    return stem, suffix


def join_filename(stem: str, extension: str) -> str:
    """Recombine stem and extension. *extension* should include the leading dot."""
    if not extension:
        return stem
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"{stem}{extension}"


def validate_windows_filename(name: str) -> str | None:
    """Return an error message when *name* is not a valid Windows basename.

    Does not silently sanitize. Returns ``None`` when the name is acceptable.
    """
    if name is None:
        return "Filename is missing."
    if name == "":
        return "Filename is empty."
    if name in {".", ".."}:
        return "Filename cannot be '.' or '..'."
    if "/" in name or "\\" in name:
        return "Filename must not contain path separators."
    if _INVALID_CHARS_RE.search(name):
        return "Filename contains characters that are illegal on Windows."
    if name.endswith(" ") or name.endswith("."):
        return "Filename must not end with a space or period."
    if name.startswith(" ") or name.startswith("\t"):
        return "Filename must not start with whitespace."

    stem, _ext = split_filename(name)
    # Reserved names apply to the stem (NUL.txt is reserved).
    reserved_token = stem.upper() if stem else name.upper()
    if reserved_token in _RESERVED_NAMES:
        return f"Filename uses a reserved Windows device name ({reserved_token})."

    if len(name) > 255:
        return "Filename exceeds 255 characters."
    return None


def validate_destination_path_length(destination: Path) -> str | None:
    """Reject destinations that would exceed a conservative path-length limit."""
    text = str(destination)
    if len(text) >= MAX_PATH_CHARS:
        return (
            f"Destination path would exceed {MAX_PATH_CHARS} characters "
            f"({len(text)} characters)."
        )
    return None
