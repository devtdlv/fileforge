"""Dry-run bulk rename planner (no filesystem mutations)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from fileforge.services.organizer.paths import (
    casefold_path,
    ensure_not_symlink_or_junction,
    is_same_path,
    is_within,
    normalize_path,
    relative_display_path,
)
from fileforge.services.renamer.models import (
    RenameItem,
    RenameItemStatus,
    RenamePlan,
    RenamePlanStatus,
    RenameProgress,
    RenameRules,
)
from fileforge.services.renamer.names import (
    validate_destination_path_length,
    validate_windows_filename,
)
from fileforge.services.renamer.rules import RULE_ORDER_DESCRIPTION, apply_rules_to_name
from fileforge.services.scanner import EntryKind, FolderScanner, ScanProgress

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[RenameProgress], None]


def _fingerprint(path: Path) -> tuple[int, int]:
    st = path.lstat()
    return int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


def _sort_key(path: Path) -> tuple[str, str]:
    """Deterministic ordering for sequential numbering (casefold path, then name)."""
    return (casefold_path(path), path.name.casefold())


class RenamePlanner:
    """Build a preview rename plan for explicitly selected files."""

    def __init__(self, scanner: FolderScanner | None = None) -> None:
        self._scanner = scanner or FolderScanner()

    def inventory(
        self,
        root: Path | str,
        *,
        recursive: bool = True,
        cancel_check: CancelCheck | None = None,
        progress_callback: Callable[[ScanProgress], None] | None = None,
    ) -> list[Path]:
        """Return regular file paths under *root* (no dirs, no symlink files)."""
        root_path = normalize_path(root)
        scan = self._scanner.scan(
            root_path,
            recursive=recursive,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )
        files: list[Path] = []
        seen_identity: set[tuple[int, int]] = set()
        for entry in scan.entries:
            if entry.kind != EntryKind.FILE:
                continue
            path = entry.path
            try:
                if path.is_symlink():
                    continue
                st = path.lstat()
                identity = (int(st.st_dev), int(st.st_ino))
                if identity in seen_identity:
                    continue
                seen_identity.add(identity)
            except OSError:
                continue
            files.append(path)
        files.sort(key=_sort_key)
        return files

    def build_plan(
        self,
        root: Path | str,
        selected: Sequence[Path | str],
        rules: RenameRules,
        *,
        recursive: bool = True,
    ) -> RenamePlan:
        """Create a dry-run rename plan for *selected* files under *root*."""
        root_path = normalize_path(root)
        plan = RenamePlan(root=root_path, recursive=recursive, rules=rules)
        plan.message = f"Rule order: {RULE_ORDER_DESCRIPTION}"

        try:
            if not root_path.exists() or not root_path.is_dir():
                plan.status = RenamePlanStatus.FAILED
                plan.message = "Selected folder does not exist or is not a directory."
                return plan
            ensure_not_symlink_or_junction(root_path)
        except (OSError, ValueError) as exc:
            plan.status = RenamePlanStatus.FAILED
            plan.message = str(exc)
            return plan

        # Deduplicate selection by casefold path, then by physical identity.
        unique_paths: list[Path] = []
        seen_cf: set[str] = set()
        for raw in selected:
            path = normalize_path(raw)
            key = casefold_path(path)
            if key in seen_cf:
                continue
            seen_cf.add(key)
            unique_paths.append(path)

        if not unique_paths:
            plan.status = RenamePlanStatus.EMPTY
            plan.message = "No files selected for renaming."
            return plan

        ordered = sorted(unique_paths, key=_sort_key)
        items: list[RenameItem] = []
        number = rules.number_start if rules.numbering_enabled else None

        for path in ordered:
            seq = number if rules.numbering_enabled else None
            item = self._plan_one(path, root_path, rules, sequence_number=seq)
            items.append(item)
            if rules.numbering_enabled and number is not None:
                number += 1

        # Detect duplicate proposed targets among READY/UNCHANGED that change names,
        # and collisions with existing files (including case-insensitive).
        self._annotate_collisions(items, root_path)
        plan.items = items

        ready = sum(1 for i in items if i.status == RenameItemStatus.READY)
        conflicts = sum(
            1
            for i in items
            if i.status
            in {
                RenameItemStatus.CONFLICT,
                RenameItemStatus.INVALID,
                RenameItemStatus.MISSING,
            }
        )
        unchanged = sum(1 for i in items if i.status == RenameItemStatus.UNCHANGED)

        if ready == 0 and conflicts == 0:
            plan.status = RenamePlanStatus.EMPTY
            plan.message = (
                f"No renames to apply ({unchanged} unchanged). "
                f"Rule order: {RULE_ORDER_DESCRIPTION}"
            )
        elif conflicts:
            plan.status = RenamePlanStatus.BLOCKED
            plan.message = (
                f"Preview blocked: {conflicts} conflict/invalid item(s), "
                f"{ready} ready, {unchanged} unchanged. "
                f"Rule order: {RULE_ORDER_DESCRIPTION}"
            )
        else:
            plan.status = RenamePlanStatus.READY
            plan.message = (
                f"Preview ready: {ready} rename(s), {unchanged} unchanged. "
                f"Rule order: {RULE_ORDER_DESCRIPTION}"
            )
        return plan

    def _plan_one(
        self,
        path: Path,
        root: Path,
        rules: RenameRules,
        *,
        sequence_number: int | None,
    ) -> RenameItem:
        relative_folder = relative_display_path(path.parent, root)
        if relative_folder in {path.parent.name, "."} and is_same_path(path.parent, root):
            relative_folder = "."
        rule_summary = rules.describe()

        def make(
            *,
            proposed: str,
            destination: Path,
            status: RenameItemStatus,
            reason: str = "",
            size: int = 0,
            mtime: int = 0,
        ) -> RenameItem:
            return RenameItem(
                source=path,
                proposed_name=proposed,
                destination=destination,
                relative_folder=relative_folder,
                rule_summary=rule_summary,
                status=status,
                conflict_reason=reason,
                source_size=size,
                source_mtime_ns=mtime,
                sequence_number=sequence_number,
            )

        try:
            if not is_within(path, root):
                return make(
                    proposed="",
                    destination=path,
                    status=RenameItemStatus.INVALID,
                    reason="File is outside the selected folder.",
                )
            if not path.exists():
                return make(
                    proposed="",
                    destination=path,
                    status=RenameItemStatus.MISSING,
                    reason="File is missing.",
                )
            if path.is_symlink():
                return make(
                    proposed="",
                    destination=path,
                    status=RenameItemStatus.INVALID,
                    reason="Symbolic links are not renamed.",
                )
            if not path.is_file():
                return make(
                    proposed="",
                    destination=path,
                    status=RenameItemStatus.INVALID,
                    reason="Only regular files can be renamed.",
                )
            size, mtime = _fingerprint(path)
        except OSError as exc:
            return make(
                proposed="",
                destination=path,
                status=RenameItemStatus.INVALID,
                reason=f"Unable to inspect file: {exc}",
            )

        proposed = apply_rules_to_name(
            path.name, rules, sequence_number=sequence_number
        )
        destination = path.with_name(proposed)

        name_error = validate_windows_filename(proposed)
        if name_error:
            return make(
                proposed=proposed,
                destination=destination,
                status=RenameItemStatus.INVALID,
                reason=name_error,
                size=size,
                mtime=mtime,
            )

        length_error = validate_destination_path_length(destination)
        if length_error:
            return make(
                proposed=proposed,
                destination=destination,
                status=RenameItemStatus.INVALID,
                reason=length_error,
                size=size,
                mtime=mtime,
            )

        if is_same_path(path, destination) and path.name == proposed:
            return make(
                proposed=proposed,
                destination=destination,
                status=RenameItemStatus.UNCHANGED,
                size=size,
                mtime=mtime,
            )

        # Case-only rename: same casefolded path but different spelling.
        if is_same_path(path, destination) and path.name != proposed:
            return make(
                proposed=proposed,
                destination=destination,
                status=RenameItemStatus.READY,
                size=size,
                mtime=mtime,
            )

        return make(
            proposed=proposed,
            destination=destination,
            status=RenameItemStatus.READY,
            size=size,
            mtime=mtime,
        )

    def _annotate_collisions(self, items: list[RenameItem], root: Path) -> None:
        """Mark conflicts for duplicate targets and occupied destinations."""
        # Group by parent directory (casefold) for collision scope.
        by_parent: dict[str, list[int]] = defaultdict(list)
        for index, item in enumerate(items):
            if item.status not in {
                RenameItemStatus.READY,
                RenameItemStatus.UNCHANGED,
            }:
                continue
            by_parent[casefold_path(item.source.parent)].append(index)

        for indices in by_parent.values():
            # Map proposed casefold name -> list of item indices that want it.
            proposed_map: dict[str, list[int]] = defaultdict(list)
            source_names_cf: set[str] = set()
            for index in indices:
                item = items[index]
                source_names_cf.add(item.source.name.casefold())
                if item.status == RenameItemStatus.READY:
                    proposed_map[item.proposed_name.casefold()].append(index)

            # Duplicate proposed targets among selected files.
            for _name_cf, group in proposed_map.items():
                if len(group) < 2:
                    continue
                for index in group:
                    item = items[index]
                    items[index] = RenameItem(
                        source=item.source,
                        proposed_name=item.proposed_name,
                        destination=item.destination,
                        relative_folder=item.relative_folder,
                        rule_summary=item.rule_summary,
                        status=RenameItemStatus.CONFLICT,
                        conflict_reason=(
                            "Multiple selected files would rename to the same name."
                        ),
                        source_size=item.source_size,
                        source_mtime_ns=item.source_mtime_ns,
                        sequence_number=item.sequence_number,
                    )

            # Existing file conflicts (destination occupied by a file that is not
            # itself being renamed away in this plan).
            for index in indices:
                item = items[index]
                if item.status != RenameItemStatus.READY:
                    continue
                # Case-only: destination is the same path — not an occupancy conflict.
                if is_same_path(item.source, item.destination):
                    continue
                dest = item.destination
                try:
                    exists = dest.exists()
                except OSError:
                    items[index] = RenameItem(
                        source=item.source,
                        proposed_name=item.proposed_name,
                        destination=item.destination,
                        relative_folder=item.relative_folder,
                        rule_summary=item.rule_summary,
                        status=RenameItemStatus.INVALID,
                        conflict_reason="Unable to check destination path.",
                        source_size=item.source_size,
                        source_mtime_ns=item.source_mtime_ns,
                        sequence_number=item.sequence_number,
                    )
                    continue

                if not exists:
                    # Case-insensitive occupancy: another file may exist with
                    # different casing that Path.exists missed on some setups;
                    # scan directory listing as a belt-and-suspenders check.
                    if self._casefold_name_taken(
                        item.source.parent,
                        item.proposed_name,
                        ignore={item.source.name.casefold()},
                        renaming_away=source_names_cf,
                    ):
                        items[index] = RenameItem(
                            source=item.source,
                            proposed_name=item.proposed_name,
                            destination=item.destination,
                            relative_folder=item.relative_folder,
                            rule_summary=item.rule_summary,
                            status=RenameItemStatus.CONFLICT,
                            conflict_reason=(
                                "A file with this name already exists "
                                "(case-insensitive match)."
                            ),
                            source_size=item.source_size,
                            source_mtime_ns=item.source_mtime_ns,
                            sequence_number=item.sequence_number,
                        )
                    continue

                # Destination exists. Allowed only if that path is a selected source
                # that is itself renaming away (chain/swap).
                dest_cf = casefold_path(dest)
                moving_away = False
                for other_index in indices:
                    other = items[other_index]
                    if other_index == index:
                        continue
                    if other.status not in {
                        RenameItemStatus.READY,
                        RenameItemStatus.UNCHANGED,
                    }:
                        continue
                    if casefold_path(other.source) != dest_cf:
                        continue
                    # The occupant is in the selection. If it is UNCHANGED and same
                    # name, it's a real conflict. If READY and leaving, chain is OK.
                    if other.status == RenameItemStatus.UNCHANGED:
                        moving_away = False
                        break
                    if not is_same_path(other.source, other.destination):
                        moving_away = True
                        break
                if moving_away:
                    continue

                items[index] = RenameItem(
                    source=item.source,
                    proposed_name=item.proposed_name,
                    destination=item.destination,
                    relative_folder=item.relative_folder,
                    rule_summary=item.rule_summary,
                    status=RenameItemStatus.CONFLICT,
                    conflict_reason=(
                        "Destination already exists; refusing to overwrite."
                    ),
                    source_size=item.source_size,
                    source_mtime_ns=item.source_mtime_ns,
                    sequence_number=item.sequence_number,
                )

    def _casefold_name_taken(
        self,
        directory: Path,
        proposed_name: str,
        *,
        ignore: set[str],
        renaming_away: set[str],
    ) -> bool:
        target = proposed_name.casefold()
        try:
            for child in directory.iterdir():
                name_cf = child.name.casefold()
                if name_cf != target:
                    continue
                if name_cf in ignore:
                    continue
                if name_cf in renaming_away:
                    continue
                return True
        except OSError:
            return False
        return False
