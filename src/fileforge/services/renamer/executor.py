"""Safe execution of approved bulk rename plans."""

from __future__ import annotations

import contextlib
import os
import uuid
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from fileforge.database.journal import OperationJournal
from fileforge.services.organizer.paths import (
    casefold_path,
    ensure_not_symlink_or_junction,
    is_same_path,
    is_within,
    normalize_path,
)
from fileforge.services.renamer.models import (
    RenameExecutionResult,
    RenameItem,
    RenameItemStatus,
    RenamePlan,
    RenamePlanStatus,
    RenameProgress,
)
from fileforge.services.renamer.names import validate_windows_filename

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[RenameProgress], None]


def _fingerprint(path: Path) -> tuple[int, int]:
    st = path.lstat()
    return int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


def _needs_staging(items: list[RenameItem]) -> bool:
    """Return True when any destination is another source (chain/swap/case-only)."""
    sources_cf = {casefold_path(item.source) for item in items}
    for item in items:
        if (
            is_same_path(item.source, item.destination)
            and item.source.name != item.proposed_name
        ):
            return True
        if casefold_path(item.destination) in sources_cf and not is_same_path(
            item.source, item.destination
        ):
            return True
    return False


def _unique_temp_name(directory: Path, original_name: str) -> Path:
    """Create a unique temporary basename in *directory* (same filesystem)."""
    for _ in range(50):
        token = uuid.uuid4().hex[:12]
        candidate = directory / f".fileforge_rename_tmp_{token}_{original_name}"
        if len(candidate.name) > 255:
            candidate = directory / f".fileforge_rename_tmp_{token}"
        if validate_windows_filename(candidate.name):
            candidate = directory / f".fileforge_rename_tmp_{token}"
        try:
            if not candidate.exists():
                return candidate
        except OSError:
            return candidate
    raise RuntimeError(f"Unable to allocate a temporary filename in {directory}")


class RenameExecutor:
    """Apply a previewed rename plan with fail-closed validation and journaling."""

    def __init__(self, journal: OperationJournal | None = None) -> None:
        self._journal = journal

    def execute(
        self,
        plan: RenamePlan,
        *,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RenameExecutionResult:
        if not plan.can_apply:
            return RenameExecutionResult(
                plan=plan,
                batch_id="",
                status=RenamePlanStatus.BLOCKED,
                items=list(plan.items),
                message=plan.message or "Plan is not applyable.",
                journaled=False,
            )

        ready = list(plan.ready_items)
        batch_id = ""
        journaled = True
        if self._journal is not None:
            try:
                batch_id = self._journal.begin_batch(
                    operation_type="bulk_rename",
                    summary=f"Bulk rename {len(ready)} file(s)",
                    source_root=str(plan.root),
                    destination_root=str(plan.root),
                    mode=plan.rules.describe(),
                    details={
                        "recursive": plan.recursive,
                        "planned": len(ready),
                        "rule_order": "search/replace, prefix, suffix, numbering, case",
                    },
                )
            except RuntimeError as exc:
                return RenameExecutionResult(
                    plan=plan,
                    batch_id="",
                    status=RenamePlanStatus.FAILED,
                    items=list(plan.items),
                    message=(
                        "Refusing to rename files because the operation journal "
                        f"could not be initialized: {exc}"
                    ),
                    journaled=False,
                )
        else:
            journaled = False

        results: list[RenameItem] = [
            item for item in plan.items if item.status != RenameItemStatus.READY
        ]
        succeeded = 0
        failed = 0
        cancelled = False
        stop = False

        by_parent: dict[str, list[RenameItem]] = defaultdict(list)
        for item in ready:
            by_parent[casefold_path(item.source.parent)].append(item)

        total = len(ready)
        completed = 0
        pending_groups = list(by_parent.values())

        for group_index, group in enumerate(pending_groups):
            if stop:
                break
            if cancel_check is not None and cancel_check():
                cancelled = True
                stop = True
                for remaining in group:
                    results.append(self._cancelled_item(remaining))
                for later in pending_groups[group_index + 1 :]:
                    for remaining in later:
                        results.append(self._cancelled_item(remaining))
                break

            if _needs_staging(group):
                # No cancel mid-stage once this directory group starts.
                outcomes = self._execute_staged_group(
                    group,
                    plan,
                    batch_id=batch_id,
                    progress_callback=progress_callback,
                    completed_base=completed,
                    total=total,
                    succeeded_base=succeeded,
                    failed_base=failed,
                )
                for outcome in outcomes:
                    results.append(outcome)
                    completed += 1
                    if outcome.status == RenameItemStatus.SUCCESS:
                        succeeded += 1
                    elif outcome.status == RenameItemStatus.CANCELLED:
                        cancelled = True
                    else:
                        failed += 1
                continue

            for item_index, item in enumerate(group):
                if cancel_check is not None and cancel_check():
                    cancelled = True
                    stop = True
                    for remaining in group[item_index:]:
                        results.append(self._cancelled_item(remaining))
                    for later in pending_groups[group_index + 1 :]:
                        for remaining in later:
                            results.append(self._cancelled_item(remaining))
                    break

                if progress_callback is not None:
                    progress_callback(
                        RenameProgress(
                            phase="renaming",
                            completed=completed,
                            total=total,
                            succeeded=succeeded,
                            failed=failed,
                            current_path=str(item.source),
                        )
                    )

                entry_id = self._journal_pending(batch_id, item)
                if entry_id is False:
                    failed += 1
                    results.append(
                        self._failed_item(
                            item,
                            "Journal write failed; remaining renames were not attempted.",
                        )
                    )
                    cancelled = True
                    stop = True
                    for remaining in group[item_index + 1 :]:
                        results.append(
                            self._cancelled_item(
                                remaining, "Skipped after journal failure."
                            )
                        )
                    for later in pending_groups[group_index + 1 :]:
                        for remaining in later:
                            results.append(
                                self._cancelled_item(
                                    remaining, "Skipped after journal failure."
                                )
                            )
                    break

                outcome = self._rename_direct(item, plan)
                results.append(outcome)
                completed += 1
                if outcome.status == RenameItemStatus.SUCCESS:
                    succeeded += 1
                    self._journal_complete(entry_id, "success")
                else:
                    failed += 1
                    self._journal_complete(
                        entry_id, "failed", outcome.error_message
                    )

        if progress_callback is not None:
            progress_callback(
                RenameProgress(
                    phase="done",
                    completed=succeeded + failed,
                    total=total,
                    succeeded=succeeded,
                    failed=failed,
                )
            )

        if cancelled and succeeded == 0 and failed == 0:
            status = RenamePlanStatus.CANCELLED
            message = "Bulk rename cancelled before any files were renamed."
        elif cancelled:
            status = RenamePlanStatus.PARTIAL
            message = (
                f"Bulk rename cancelled after {succeeded} success(es) "
                f"and {failed} failure(s)."
            )
        elif failed and succeeded:
            status = RenamePlanStatus.PARTIAL
            message = (
                f"Bulk rename finished with partial success: "
                f"{succeeded} renamed, {failed} failed."
            )
        elif failed:
            status = RenamePlanStatus.FAILED
            message = f"Bulk rename failed: {failed} file(s) could not be renamed."
        else:
            status = RenamePlanStatus.COMPLETED
            message = f"Bulk rename completed: {succeeded} file(s) renamed."

        if self._journal is not None and batch_id:
            batch_status = {
                RenamePlanStatus.COMPLETED: "completed",
                RenamePlanStatus.PARTIAL: "partial",
                RenamePlanStatus.CANCELLED: "cancelled",
                RenamePlanStatus.FAILED: "failed",
            }.get(status, "failed")
            try:
                self._journal.complete_batch(
                    batch_id, status=batch_status, summary=message
                )
            except RuntimeError:
                journaled = False
                message += " Journal finalization failed."

        if not journaled and status == RenamePlanStatus.COMPLETED:
            message += " Warning: journaling was incomplete."

        return RenameExecutionResult(
            plan=plan,
            batch_id=batch_id,
            status=status,
            items=results,
            message=message,
            journaled=journaled,
        )

    def _journal_pending(self, batch_id: str, item: RenameItem) -> int | None | bool:
        if self._journal is None or not batch_id:
            return None
        try:
            return self._journal.add_entry(
                batch_id,
                source_path=str(item.source),
                destination_path=str(item.destination),
                operation_type="rename",
                status="pending",
            )
        except RuntimeError:
            return False

    def _journal_complete(
        self, entry_id: int | None | bool, status: str, error: str = ""
    ) -> None:
        if self._journal is None or entry_id is None or entry_id is False:
            return
        with contextlib.suppress(RuntimeError):
            self._journal.complete_entry(
                int(entry_id), status=status, error_details=error
            )

    def _cancelled_item(
        self, item: RenameItem, message: str = "Cancelled before execution."
    ) -> RenameItem:
        return RenameItem(
            source=item.source,
            proposed_name=item.proposed_name,
            destination=item.destination,
            relative_folder=item.relative_folder,
            rule_summary=item.rule_summary,
            status=RenameItemStatus.CANCELLED,
            conflict_reason=item.conflict_reason,
            source_size=item.source_size,
            source_mtime_ns=item.source_mtime_ns,
            error_message=message,
            sequence_number=item.sequence_number,
        )

    def _failed_item(self, item: RenameItem, message: str) -> RenameItem:
        return RenameItem(
            source=item.source,
            proposed_name=item.proposed_name,
            destination=item.destination,
            relative_folder=item.relative_folder,
            rule_summary=item.rule_summary,
            status=RenameItemStatus.FAILED,
            conflict_reason=item.conflict_reason,
            source_size=item.source_size,
            source_mtime_ns=item.source_mtime_ns,
            error_message=message,
            sequence_number=item.sequence_number,
        )

    def _success_item(self, item: RenameItem) -> RenameItem:
        return RenameItem(
            source=item.source,
            proposed_name=item.proposed_name,
            destination=item.destination,
            relative_folder=item.relative_folder,
            rule_summary=item.rule_summary,
            status=RenameItemStatus.SUCCESS,
            source_size=item.source_size,
            source_mtime_ns=item.source_mtime_ns,
            sequence_number=item.sequence_number,
        )

    def _rename_direct(self, item: RenameItem, plan: RenamePlan) -> RenameItem:
        source = normalize_path(item.source)
        destination = normalize_path(item.destination)

        stale = self._revalidate(item, plan, source, destination)
        if stale is not None:
            return stale

        try:
            os.rename(source, destination)
        except OSError as exc:
            return self._failed_item(item, f"Rename failed: {exc}")

        if not destination.exists():
            return self._failed_item(
                item, "Rename could not be verified at the destination."
            )
        if not is_same_path(source, destination) and source.exists():
            return self._failed_item(
                item,
                "Source still exists after rename; outcome is ambiguous.",
            )
        return self._success_item(item)

    def _execute_staged_group(
        self,
        group: list[RenameItem],
        plan: RenamePlan,
        *,
        batch_id: str,
        progress_callback: ProgressCallback | None,
        completed_base: int,
        total: int,
        succeeded_base: int,
        failed_base: int,
    ) -> list[RenameItem]:
        """Two-phase rename for chains, swaps, and case-only renames.

        Phase 1: each source → unique temp in the same directory.
        Phase 2: each temp → final destination.
        On failure, restore remaining temps to their original names.
        Cancellation is not honored mid-group once staging has started.
        """
        staged: list[tuple[RenameItem, Path, int | None]] = []

        for offset, item in enumerate(group):
            if progress_callback is not None:
                progress_callback(
                    RenameProgress(
                        phase="staging",
                        completed=completed_base + offset,
                        total=total,
                        succeeded=succeeded_base,
                        failed=failed_base,
                        current_path=str(item.source),
                    )
                )

            entry_id = self._journal_pending(batch_id, item)
            if entry_id is False:
                self._rollback_temps(staged)
                outcomes: list[RenameItem] = [
                    self._failed_item(
                        item, "Journal write failed; staged rename aborted."
                    )
                ]
                for remaining in group[offset + 1 :]:
                    outcomes.append(
                        self._cancelled_item(
                            remaining, "Skipped after journal failure."
                        )
                    )
                return outcomes

            source = normalize_path(item.source)
            destination = normalize_path(item.destination)
            stale = self._revalidate(
                item,
                plan,
                source,
                destination,
                allow_peer_destination=True,
            )
            if stale is not None:
                self._journal_complete(
                    entry_id, "failed", stale.error_message or stale.conflict_reason
                )
                self._rollback_temps(staged)
                outcomes = [stale]
                for remaining in group[offset + 1 :]:
                    outcomes.append(
                        self._cancelled_item(
                            remaining, "Skipped after staged rename failure."
                        )
                    )
                return outcomes

            try:
                temp = _unique_temp_name(source.parent, source.name)
                os.rename(source, temp)
            except OSError as exc:
                failed = self._failed_item(item, f"Staging rename failed: {exc}")
                self._journal_complete(entry_id, "failed", failed.error_message)
                self._rollback_temps(staged)
                outcomes = [failed]
                for remaining in group[offset + 1 :]:
                    outcomes.append(
                        self._cancelled_item(
                            remaining, "Skipped after staged rename failure."
                        )
                    )
                return outcomes

            eid = entry_id if isinstance(entry_id, int) else None
            staged.append((item, temp, eid))

        outcomes = []
        finalized_sources: set[str] = set()
        for item, temp, entry_id in staged:
            destination = normalize_path(item.destination)
            try:
                if destination.exists() and not is_same_path(temp, destination):
                    raise OSError("Destination exists; refusing to overwrite.")
                os.rename(temp, destination)
            except OSError as exc:
                try:
                    if temp.exists():
                        os.rename(temp, normalize_path(item.source))
                except OSError:
                    pass
                failed = self._failed_item(
                    item,
                    f"Final rename failed after staging: {exc}. "
                    "Attempted to restore the original name.",
                )
                self._journal_complete(entry_id, "failed", failed.error_message)
                outcomes.append(failed)

                pending = [
                    (it, tp, eid)
                    for it, tp, eid in staged
                    if casefold_path(it.source) not in finalized_sources
                    and casefold_path(it.source) != casefold_path(item.source)
                    and tp.exists()
                ]
                self._rollback_temps(pending)
                for it, _tp, eid in pending:
                    cancelled = self._cancelled_item(
                        it, "Restored after another staged rename failed."
                    )
                    self._journal_complete(eid, "failed", cancelled.error_message)
                    outcomes.append(cancelled)
                return outcomes

            finalized_sources.add(casefold_path(item.source))
            success = self._success_item(item)
            self._journal_complete(entry_id, "success")
            outcomes.append(success)

        return outcomes

    def _rollback_temps(
        self, temps: list[tuple[RenameItem, Path, int | None]]
    ) -> None:
        for item, temp, _entry_id in reversed(temps):
            try:
                if not temp.exists():
                    continue
                original = normalize_path(item.source)
                if not original.exists():
                    os.rename(temp, original)
            except OSError:
                continue

    def _revalidate(
        self,
        item: RenameItem,
        plan: RenamePlan,
        source: Path,
        destination: Path,
        *,
        allow_peer_destination: bool = False,
    ) -> RenameItem | None:
        try:
            if not source.exists():
                return self._failed_item(item, "Source file disappeared after preview.")
            if source.is_symlink():
                return self._failed_item(
                    item, "Source became a symbolic link after preview."
                )
            ensure_not_symlink_or_junction(source)
            if not source.is_file():
                return self._failed_item(item, "Source is no longer a regular file.")
            if not is_within(source, plan.root):
                return self._failed_item(
                    item, "Source file is outside the selected folder."
                )
            if not is_within(destination, plan.root):
                return self._failed_item(
                    item, "Destination escapes the selected folder."
                )
            if not is_same_path(destination.parent, source.parent):
                return self._failed_item(
                    item, "Bulk renamer only renames within the same directory."
                )

            size, mtime_ns = _fingerprint(source)
            if size != item.source_size or mtime_ns != item.source_mtime_ns:
                return RenameItem(
                    source=item.source,
                    proposed_name=item.proposed_name,
                    destination=item.destination,
                    relative_folder=item.relative_folder,
                    rule_summary=item.rule_summary,
                    status=RenameItemStatus.STALE,
                    conflict_reason="Source file changed after preview.",
                    source_size=item.source_size,
                    source_mtime_ns=item.source_mtime_ns,
                    error_message=(
                        "Source file changed after preview; rename rejected."
                    ),
                    sequence_number=item.sequence_number,
                )

            if is_same_path(source, destination) and source.name == item.proposed_name:
                return self._failed_item(item, "Source and destination are identical.")

            if (
                not is_same_path(source, destination)
                and destination.exists()
                and not allow_peer_destination
            ):
                return self._failed_item(
                    item, "Destination already exists; refusing to overwrite."
                )
        except Exception as exc:  # noqa: BLE001
            return self._failed_item(item, f"Unexpected validation error: {exc}")
        return None
