"""Read-only duplicate detection engine (no PySide6 dependency)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from fileforge.services.duplicates.hasher import (
    FileChangedError,
    HashCancelledError,
    sha256_file,
)
from fileforge.services.duplicates.models import (
    DuplicateError,
    DuplicateFile,
    DuplicateGroup,
    DuplicateProgress,
    DuplicateResult,
    DuplicateStatus,
)
from fileforge.services.scanner import EntryKind, FolderScanner, ScanProgress

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[DuplicateProgress], None]


def _identity(path: Path) -> tuple[int, int, int, int]:
    """Return (dev, ino, size, mtime_ns) for a regular file."""
    st = path.lstat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return int(st.st_dev), int(st.st_ino), int(st.st_size), mtime_ns


class DuplicateFinder:
    """Find files with identical content using size filtering then SHA-256."""

    def __init__(self, scanner: FolderScanner | None = None) -> None:
        self._scanner = scanner or FolderScanner()

    def find(
        self,
        root: Path | str,
        *,
        recursive: bool = True,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> DuplicateResult:
        """Scan *root* and return duplicate groups (read-only)."""
        root_path = Path(root)
        result = DuplicateResult(
            root=root_path,
            recursive=recursive,
            status=DuplicateStatus.FAILED,
        )

        def cancelled() -> bool:
            return cancel_check is not None and cancel_check()

        def emit(**kwargs: object) -> None:
            if progress_callback is None:
                return
            progress_callback(DuplicateProgress(**kwargs))  # type: ignore[arg-type]

        try:
            if not root_path.exists() or not root_path.is_dir():
                result.message = "Selected path does not exist or is not a directory."
                return result
        except OSError as exc:
            result.message = f"Unable to access selected path: {exc}"
            return result

        def on_scan_progress(progress: ScanProgress) -> None:
            emit(
                phase="scanning",
                files_seen=progress.files_seen,
                current_path=progress.current_path,
            )

        scan = self._scanner.scan(
            root_path,
            recursive=recursive,
            cancel_check=cancel_check,
            progress_callback=on_scan_progress,
        )
        if cancelled():
            result.status = DuplicateStatus.CANCELLED
            result.message = "Duplicate scan cancelled during directory walk."
            result.errors = [
                DuplicateError(path=error.path, message=error.message)
                for error in scan.errors
            ]
            return result

        errors: list[DuplicateError] = [
            DuplicateError(path=error.path, message=error.message) for error in scan.errors
        ]

        # Collect regular files with identity metadata. Skip symlinks (scanner marks them).
        files_meta: list[tuple[Path, str, int, int, int, int]] = []
        # path, relative, size, dev, ino, mtime_ns
        for entry in scan.entries:
            if entry.kind != EntryKind.FILE:
                continue
            path = entry.path
            try:
                if path.is_symlink():
                    continue
                dev, ino, size, mtime_ns = _identity(path)
            except FileNotFoundError:
                errors.append(
                    DuplicateError(str(path), "File disappeared before hashing.")
                )
                continue
            except OSError as exc:
                errors.append(DuplicateError(str(path), f"Unable to inspect file: {exc}"))
                continue
            files_meta.append(
                (path, entry.relative_path, size, dev, ino, mtime_ns)
            )

        result.files_scanned = len(files_meta)
        if not files_meta:
            result.status = DuplicateStatus.EMPTY
            result.message = "No files found to compare."
            result.errors = errors
            return result

        # Group by size; only sizes with 2+ distinct physical files are candidates.
        by_size: dict[int, list[tuple[Path, str, int, int, int]]] = defaultdict(list)
        for path, relative, size, dev, ino, mtime_ns in files_meta:
            by_size[size].append((path, relative, dev, ino, mtime_ns))

        result.unique_sizes = len(by_size)
        candidates: list[tuple[Path, str, int, int, int, int]] = []
        for size, items in by_size.items():
            unique_ids = {(dev, ino) for _, _, dev, ino, _ in items}
            if len(unique_ids) < 2:
                continue
            for path, relative, dev, ino, mtime_ns in items:
                candidates.append((path, relative, size, dev, ino, mtime_ns))

        emit(
            phase="hashing",
            files_seen=result.files_scanned,
            size_candidates=len(candidates),
            hashed=0,
            groups_found=0,
        )

        # Hash each physical file (dev, ino) once per size bucket.
        # key: (size, sha256) -> list of DuplicateFile
        hash_groups: dict[tuple[int, str], list[DuplicateFile]] = defaultdict(list)
        hashed_identities: dict[tuple[int, int, int], str] = {}
        # (size, dev, ino) -> sha256
        hashed_count = 0

        # Process by size for clearer progress.
        candidates_by_size: dict[int, list[tuple[Path, str, int, int, int]]] = defaultdict(
            list
        )
        for path, relative, size, dev, ino, mtime_ns in candidates:
            candidates_by_size[size].append((path, relative, dev, ino, mtime_ns))

        for size, items in candidates_by_size.items():
            if cancelled():
                result.status = DuplicateStatus.CANCELLED
                result.message = "Duplicate scan cancelled during hashing."
                result.errors = errors
                result.hashed_files = hashed_count
                return result

            # Unique physical files in this size class.
            by_identity: dict[tuple[int, int], list[tuple[Path, str, int]]] = defaultdict(
                list
            )
            for path, relative, dev, ino, mtime_ns in items:
                by_identity[(dev, ino)].append((path, relative, mtime_ns))

            for (dev, ino), paths in by_identity.items():
                if cancelled():
                    result.status = DuplicateStatus.CANCELLED
                    result.message = "Duplicate scan cancelled during hashing."
                    result.errors = errors
                    result.hashed_files = hashed_count
                    return result

                identity_key = (size, dev, ino)
                path, relative, mtime_ns = paths[0]
                emit(
                    phase="hashing",
                    files_seen=result.files_scanned,
                    size_candidates=len(candidates),
                    hashed=hashed_count,
                    groups_found=len(
                        [1 for files in hash_groups.values() if len({f.identity for f in files}) > 1]
                    ),
                    current_path=str(path),
                )
                try:
                    digest = sha256_file(
                        path,
                        expected_size=size,
                        expected_mtime_ns=mtime_ns,
                        cancel_check=cancel_check,
                    )
                except HashCancelledError:
                    result.status = DuplicateStatus.CANCELLED
                    result.message = "Duplicate scan cancelled during hashing."
                    result.errors = errors
                    result.hashed_files = hashed_count
                    return result
                except FileChangedError as exc:
                    errors.append(DuplicateError(str(path), str(exc)))
                    continue
                except OSError as exc:
                    errors.append(DuplicateError(str(path), str(exc)))
                    continue

                hashed_identities[identity_key] = digest
                hashed_count += 1
                for path_i, relative_i, _mtime in paths:
                    hash_groups[(size, digest)].append(
                        DuplicateFile(
                            path=path_i,
                            relative_path=relative_i,
                            size_bytes=size,
                            device=dev,
                            inode=ino,
                        )
                    )

        result.hashed_files = hashed_count
        groups: list[DuplicateGroup] = []
        for (size, digest), files in hash_groups.items():
            unique = {file.identity for file in files}
            if len(unique) < 2:
                continue
            groups.append(
                DuplicateGroup(size_bytes=size, sha256=digest, files=sorted(files, key=lambda f: str(f.path).casefold()))
            )

        groups.sort(key=lambda g: (-g.potential_savings_bytes, -g.size_bytes, g.sha256))
        result.groups = groups
        result.errors = errors

        if cancelled():
            result.status = DuplicateStatus.CANCELLED
            result.message = "Duplicate scan cancelled."
        elif not groups and errors:
            result.status = DuplicateStatus.PARTIAL
            result.message = (
                f"No duplicate groups found. {len(errors)} issue(s) occurred "
                f"while scanning or hashing."
            )
        elif not groups:
            result.status = DuplicateStatus.EMPTY
            result.message = (
                f"No duplicate content found among {result.files_scanned} file(s)."
            )
        elif errors:
            result.status = DuplicateStatus.PARTIAL
            result.message = (
                f"Found {len(groups)} duplicate group(s) with {len(errors)} issue(s)."
            )
        else:
            result.status = DuplicateStatus.COMPLETED
            result.message = (
                f"Found {len(groups)} duplicate group(s) among "
                f"{result.files_scanned} file(s)."
            )
        return result
