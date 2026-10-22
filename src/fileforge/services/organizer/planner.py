"""Dry-run organization planner (no filesystem mutations)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from fileforge.services.organizer.categories import category_for_extension
from fileforge.services.organizer.models import (
    OrganizeMode,
    OrganizePlan,
    PlanItem,
    PlanItemStatus,
    PlanStatus,
)
from fileforge.services.organizer.paths import (
    casefold_path,
    ensure_not_symlink_or_junction,
    is_same_path,
    is_within,
    normalize_path,
)
from fileforge.services.scanner import EntryKind, FolderScanner, ScanEntry, ScanProgress

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[ScanProgress], None]


def _destination_for(
    entry: ScanEntry,
    *,
    destination_root: Path,
    mode: OrganizeMode,
) -> tuple[Path, str]:
    """Return (destination path, rule label) for a scanned file."""
    name = entry.path.name
    if mode is OrganizeMode.EXTENSION:
        folder = entry.extension or "_no_extension"
        rule = f"Extension: {folder}"
        return destination_root / folder / name, rule
    if mode is OrganizeMode.CATEGORY:
        category = category_for_extension(entry.extension)
        rule = f"Category: {category}"
        return destination_root / category / name, rule
    if mode is OrganizeMode.YEAR_MONTH:
        if entry.modified_at is None:
            folder = Path("UnknownDate")
            rule = "Modified date: unknown"
        else:
            local = entry.modified_at.astimezone()
            folder = Path(f"{local.year:04d}") / f"{local.month:02d}"
            rule = f"Modified date: {local.year:04d}/{local.month:02d}"
        return destination_root / folder / name, rule
    raise ValueError(f"Unsupported organize mode: {mode}")


def _stat_fingerprint(path: Path) -> tuple[int, int]:
    st = path.lstat()
    return int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


class OrganizePlanner:
    """Build a preview organization plan using the read-only scanner."""

    def __init__(self, scanner: FolderScanner | None = None) -> None:
        self._scanner = scanner or FolderScanner()

    def build_plan(
        self,
        source_root: Path | str,
        destination_root: Path | str,
        *,
        mode: OrganizeMode,
        recursive: bool = True,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> OrganizePlan:
        """Scan *source_root* and produce a dry-run move plan into *destination_root*."""
        source = normalize_path(source_root)
        destination = normalize_path(destination_root)
        plan = OrganizePlan(
            source_root=source,
            destination_root=destination,
            mode=mode,
            recursive=recursive,
        )

        try:
            if not source.exists() or not source.is_dir():
                plan.status = PlanStatus.FAILED
                plan.message = "Source folder does not exist or is not a directory."
                return plan
            if not destination.exists() or not destination.is_dir():
                plan.status = PlanStatus.FAILED
                plan.message = "Destination folder does not exist or is not a directory."
                return plan
            ensure_not_symlink_or_junction(source)
            ensure_not_symlink_or_junction(destination)
        except (OSError, ValueError) as exc:
            plan.status = PlanStatus.FAILED
            plan.message = str(exc)
            return plan

        # Refuse organizing into a destination that is a symlink/junction child scope.
        if is_same_path(source, destination):
            # In-place organization is allowed.
            pass
        elif is_within(destination, source) and not is_same_path(destination, source):
            # Destination nested inside source is allowed for in-tree layouts, but
            # refuse when destination equals a path we might later move files through
            # in unsafe ways. File-only moves remain safe; keep a soft warning via message.
            plan.message = (
                "Destination is inside the source folder. "
                "Only files will be moved; directories are never moved."
            )

        scan = self._scanner.scan(
            source,
            recursive=recursive,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )
        if cancel_check is not None and cancel_check():
            plan.status = PlanStatus.CANCELLED
            plan.message = "Preview cancelled."
            return plan

        files = [entry for entry in scan.entries if entry.kind == EntryKind.FILE]
        if not files:
            plan.status = PlanStatus.EMPTY
            plan.message = "No files found to organize."
            return plan

        items: list[PlanItem] = []
        planned_dest_index: dict[str, list[Path]] = defaultdict(list)

        for entry in files:
            src = normalize_path(entry.path)
            try:
                if src.is_symlink():
                    items.append(
                        PlanItem(
                            source=src,
                            destination=src,
                            rule="Skipped symlink",
                            status=PlanItemStatus.SKIPPED,
                            conflict_reason="Symbolic links are not organized.",
                        )
                    )
                    continue
                dest, rule = _destination_for(entry, destination_root=destination, mode=mode)
                dest = normalize_path(dest)
                size, mtime_ns = _stat_fingerprint(src)
            except OSError as exc:
                items.append(
                    PlanItem(
                        source=src,
                        destination=src,
                        rule="Unavailable",
                        status=PlanItemStatus.INVALID,
                        conflict_reason=f"Unable to read source metadata: {exc}",
                    )
                )
                continue

            if is_same_path(src, dest):
                items.append(
                    PlanItem(
                        source=src,
                        destination=dest,
                        rule=rule,
                        status=PlanItemStatus.SKIPPED,
                        conflict_reason="Source and destination are the same path.",
                        source_size=size,
                        source_mtime_ns=mtime_ns,
                    )
                )
                continue

            if is_within(dest, src):
                items.append(
                    PlanItem(
                        source=src,
                        destination=dest,
                        rule=rule,
                        status=PlanItemStatus.INVALID,
                        conflict_reason="Destination resolves inside the source path.",
                        source_size=size,
                        source_mtime_ns=mtime_ns,
                    )
                )
                continue

            if not is_within(src, source):
                items.append(
                    PlanItem(
                        source=src,
                        destination=dest,
                        rule=rule,
                        status=PlanItemStatus.INVALID,
                        conflict_reason="Source file is outside the selected source folder.",
                        source_size=size,
                        source_mtime_ns=mtime_ns,
                    )
                )
                continue

            if not is_within(dest, destination):
                items.append(
                    PlanItem(
                        source=src,
                        destination=dest,
                        rule=rule,
                        status=PlanItemStatus.INVALID,
                        conflict_reason="Destination escapes the selected destination folder.",
                        source_size=size,
                        source_mtime_ns=mtime_ns,
                    )
                )
                continue

            conflict_reason = ""
            status = PlanItemStatus.READY
            if dest.exists():
                status = PlanItemStatus.CONFLICT
                conflict_reason = "A file or folder already exists at the destination."
            else:
                # Case-insensitive collision against another planned destination.
                key = casefold_path(dest)
                if planned_dest_index[key]:
                    status = PlanItemStatus.CONFLICT
                    conflict_reason = (
                        "Multiple files would land on the same destination path "
                        "(Windows case-insensitive collision)."
                    )
                planned_dest_index[key].append(src)

            items.append(
                PlanItem(
                    source=src,
                    destination=dest,
                    rule=rule,
                    status=status,
                    conflict_reason=conflict_reason,
                    source_size=size,
                    source_mtime_ns=mtime_ns,
                )
            )

        # Second pass: mark siblings that share a casefolded destination as conflicts.
        final_items: list[PlanItem] = []
        for item in items:
            if item.status != PlanItemStatus.READY:
                final_items.append(item)
                continue
            key = casefold_path(item.destination)
            if len(planned_dest_index[key]) > 1:
                final_items.append(
                    PlanItem(
                        source=item.source,
                        destination=item.destination,
                        rule=item.rule,
                        status=PlanItemStatus.CONFLICT,
                        conflict_reason=(
                            "Multiple files would land on the same destination path "
                            "(Windows case-insensitive collision)."
                        ),
                        source_size=item.source_size,
                        source_mtime_ns=item.source_mtime_ns,
                    )
                )
            else:
                final_items.append(item)

        plan.items = final_items
        ready = plan.ready_items
        conflicts = plan.conflict_items
        if conflicts:
            plan.status = PlanStatus.BLOCKED
            plan.message = (
                f"Preview found {len(conflicts)} conflict(s) or invalid operation(s). "
                "Resolve them before applying. No silent overwrites are allowed."
            )
        elif not ready:
            plan.status = PlanStatus.EMPTY
            plan.message = "No movable files remain after skipping unchanged paths."
        else:
            plan.status = PlanStatus.READY
            skipped = sum(1 for item in final_items if item.status == PlanItemStatus.SKIPPED)
            plan.message = (
                f"Preview ready: {len(ready)} move(s) planned"
                + (f", {skipped} skipped" if skipped else "")
                + "."
            )
        return plan
