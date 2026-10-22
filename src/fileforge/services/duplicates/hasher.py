"""Chunked SHA-256 hashing with change detection."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # 1 MiB


class FileChangedError(RuntimeError):
    """Raised when a file's size or mtime changes during hashing."""


class HashCancelledError(RuntimeError):
    """Raised when hashing is cooperatively cancelled."""


CancelCheck = Callable[[], bool]


def sha256_file(
    path: Path,
    *,
    expected_size: int,
    expected_mtime_ns: int,
    cancel_check: CancelCheck | None = None,
    chunk_size: int = CHUNK_SIZE,
) -> str:
    """Return the hex SHA-256 digest of *path* without loading it entirely.

    Verifies size/mtime before and after reading. Does not follow symlinks
    (opens the path as given; callers should pass regular files only).
    """
    def _stat_matches() -> None:
        st = path.lstat()
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
        if int(st.st_size) != expected_size or mtime_ns != expected_mtime_ns:
            raise FileChangedError(
                f"File changed during hashing (size/mtime mismatch): {path}"
            )

    digest = hashlib.sha256()
    try:
        _stat_matches()
        with path.open("rb", buffering=chunk_size) as handle:
            while True:
                if cancel_check is not None and cancel_check():
                    raise HashCancelledError("Hashing cancelled.")
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        _stat_matches()
    except FileChangedError:
        raise
    except FileNotFoundError as exc:
        raise FileChangedError(f"File disappeared during hashing: {path}") from exc
    except OSError as exc:
        raise OSError(f"Unable to hash file: {path}: {exc}") from exc

    return digest.hexdigest()
