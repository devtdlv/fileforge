"""Read-only folder scanning engine (no PySide6 dependency)."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fileforge.services.scanner.models import (
    EntryKind,
    ScanEntry,
    ScanError,
    ScanProgress,
    ScanResult,
    ScanStatus,
)

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[ScanProgress], None]


def _is_junction(path: Path) -> bool:
    """Return True when *path* is a Windows directory junction."""
    isjunction = getattr(os.path, "isjunction", None)
    if callable(isjunction):
        try:
            return bool(isjunction(path))
        except OSError:
            return False
    return False


def _extension_of(path: Path, kind: EntryKind) -> str:
    if kind != EntryKind.FILE:
        return ""
    suffix = path.suffix
    if not suffix:
        return ""
    return suffix.lstrip(".").lower()


def _modified_at(st: os.stat_result) -> datetime | None:
    try:
        return datetime.fromtimestamp(st.st_mtime, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


class FolderScanner:
    """Walk a user-selected directory and collect metadata only.

    The scanner never follows symbolic links or directory junctions by default,
    never reads file contents, and never modifies the filesystem.
    """

    def scan(
        self,
        root: Path | str,
        *,
        recursive: bool = True,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
        progress_every: int = 25,
    ) -> ScanResult:
        """Scan *root* and return a structured result.

        Args:
            root: Explicitly selected directory to inventory.
            recursive: When False, only the immediate children of *root* are listed.
            cancel_check: Optional cooperative cancellation predicate.
            progress_callback: Optional progress notifier (counts only).
            progress_every: Emit progress after this many newly recorded entries.
        """
        started = datetime.now(tz=UTC)
        root_path = Path(root)
        result = ScanResult(
            root=root_path,
            recursive=recursive,
            status=ScanStatus.FAILED,
            started_at=started,
        )

        def cancelled() -> bool:
            return cancel_check is not None and cancel_check()

        try:
            if not root_path.exists():
                result.message = f"The selected path does not exist: {root_path}"
                result.finished_at = datetime.now(tz=UTC)
                return result
            if not root_path.is_dir():
                result.message = f"The selected path is not a directory: {root_path}"
                result.finished_at = datetime.now(tz=UTC)
                return result
        except OSError as exc:
            result.message = f"Unable to access the selected path: {exc}"
            result.finished_at = datetime.now(tz=UTC)
            return result

        entries: list[ScanEntry] = []
        errors: list[ScanError] = []
        files_seen = 0
        dirs_seen = 0
        visited_dirs: set[str] = set()

        def emit_progress(current: str = "") -> None:
            if progress_callback is None:
                return
            progress_callback(
                ScanProgress(
                    files_seen=files_seen,
                    directories_seen=dirs_seen,
                    errors_seen=len(errors),
                    current_path=current,
                )
            )

        def record_error(path: Path | str, message: str) -> None:
            errors.append(ScanError(path=str(path), message=message))

        def add_entry(entry: ScanEntry) -> None:
            nonlocal files_seen, dirs_seen
            entries.append(entry)
            if entry.kind == EntryKind.FILE:
                files_seen += 1
            elif entry.kind == EntryKind.DIRECTORY:
                dirs_seen += 1
            if progress_every > 0 and len(entries) % progress_every == 0:
                emit_progress(str(entry.path))

        def classify_and_stat(path: Path) -> tuple[EntryKind, os.stat_result | None]:
            try:
                if path.is_symlink():
                    return EntryKind.SYMLINK, None
                if _is_junction(path):
                    return EntryKind.JUNCTION, None
                st = path.lstat()
            except FileNotFoundError:
                raise
            except OSError as exc:
                record_error(path, f"Unable to inspect entry: {exc}")
                return EntryKind.OTHER, None

            mode = st.st_mode
            if stat.S_ISDIR(mode):
                return EntryKind.DIRECTORY, st
            if stat.S_ISREG(mode):
                return EntryKind.FILE, st
            return EntryKind.OTHER, st

        def make_entry(path: Path, kind: EntryKind, st: os.stat_result | None) -> ScanEntry:
            try:
                relative = path.relative_to(root_path).as_posix()
            except ValueError:
                relative = path.name
            parent = str(path.parent)
            size = int(st.st_size) if st is not None and kind == EntryKind.FILE else 0
            modified = _modified_at(st) if st is not None else None
            return ScanEntry(
                name=path.name or str(path),
                path=path,
                relative_path=relative,
                extension=_extension_of(path, kind),
                size_bytes=size,
                modified_at=modified,
                parent_directory=parent,
                kind=kind,
            )

        def identity_key(path: Path) -> str:
            try:
                return str(path.resolve())
            except OSError:
                return os.path.normcase(os.path.abspath(str(path)))

        def walk_directory(directory: Path, *, descend: bool) -> None:
            if cancelled():
                return

            key = identity_key(directory)
            if key in visited_dirs:
                record_error(directory, "Skipped potential traversal loop.")
                return
            visited_dirs.add(key)

            try:
                with os.scandir(directory) as iterator:
                    children = list(iterator)
            except FileNotFoundError:
                record_error(directory, "Directory disappeared during scan.")
                return
            except PermissionError as exc:
                record_error(directory, f"Permission denied: {exc}")
                return
            except OSError as exc:
                record_error(directory, f"Unable to list directory: {exc}")
                return

            for child in children:
                if cancelled():
                    return

                child_path = Path(child.path)
                try:
                    kind, st = classify_and_stat(child_path)
                except FileNotFoundError:
                    record_error(child_path, "Entry disappeared during scan.")
                    continue

                if kind == EntryKind.SYMLINK:
                    add_entry(make_entry(child_path, kind, None))
                    continue
                if kind == EntryKind.JUNCTION:
                    add_entry(make_entry(child_path, kind, None))
                    continue
                if kind == EntryKind.OTHER:
                    add_entry(make_entry(child_path, kind, st))
                    continue
                if kind == EntryKind.FILE:
                    # Re-stat via DirEntry when possible for efficiency.
                    if st is None:
                        try:
                            st = child.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            record_error(child_path, "File disappeared during scan.")
                            continue
                        except OSError as exc:
                            record_error(child_path, f"Unable to read file metadata: {exc}")
                            continue
                    add_entry(make_entry(child_path, kind, st))
                    continue

                # Directory
                if st is None:
                    try:
                        st = child.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        record_error(child_path, "Directory disappeared during scan.")
                        continue
                    except OSError as exc:
                        record_error(child_path, f"Unable to read directory metadata: {exc}")
                        continue
                add_entry(make_entry(child_path, kind, st))
                if descend and recursive:
                    walk_directory(child_path, descend=True)

        emit_progress(str(root_path))
        walk_directory(root_path, descend=True)

        finished = datetime.now(tz=UTC)
        result.entries = entries
        result.errors = errors
        result.finished_at = finished

        if cancelled():
            result.status = ScanStatus.CANCELLED
            result.message = "Scan cancelled."
        elif errors and not entries:
            result.status = ScanStatus.FAILED
            result.message = "Scan failed before any entries could be collected."
        elif errors:
            result.status = ScanStatus.PARTIAL
            result.message = (
                f"Scan finished with {len(errors)} issue(s); "
                f"{files_seen} file(s) and {dirs_seen} folder(s) listed."
            )
        else:
            result.status = ScanStatus.COMPLETED
            result.message = (
                f"Scan completed: {files_seen} file(s), {dirs_seen} folder(s)."
            )

        emit_progress(str(root_path))
        return result
