"""Safe execution of approved organization plans."""

from __future__ import annotations

import errno
from collections.abc import Callable
from pathlib import Path

from fileforge.database.journal import OperationJournal
from fileforge.services.organizer.models import (
    ExecutionProgress,
    ExecutionResult,
    OrganizePlan,
    PlanItem,
    PlanItemStatus,
    PlanStatus,
)
from fileforge.services.organizer.paths import (
    ensure_not_symlink_or_junction,
    is_same_path,
    is_within,
    normalize_path,
)

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[ExecutionProgress], None]


def _fingerprint(path: Path) -> tuple[int, int]:
    st = path.lstat()
    return int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


class OrganizeExecutor:
    """Apply a previewed plan with fail-closed validation and journaling."""

    def __init__(self, journal: OperationJournal | None = None) -> None:
        self._journal = journal

    def execute(
        self,
        plan: OrganizePlan,
        *,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExecutionResult:
        """Execute ready items from *plan*. Never overwrites existing destinations."""
        if not plan.can_apply:
            return ExecutionResult(
                plan=plan,
                batch_id="",
                status=PlanStatus.BLOCKED,
                items=list(plan.items),
                message=plan.message or "Plan is not applyable.",
                journaled=False,
            )

        ready = plan.ready_items
        batch_id = ""
        journaled = True
        if self._journal is not None:
            try:
                batch_id = self._journal.begin_batch(
                    operation_type="organize_move",
                    summary=f"Organize {len(ready)} file(s) by {plan.mode.value}",
                    source_root=str(plan.source_root),
                    destination_root=str(plan.destination_root),
                    mode=plan.mode.value,
                    details={"recursive": plan.recursive, "planned": len(ready)},
                )
            except RuntimeError as exc:
                return ExecutionResult(
                    plan=plan,
                    batch_id="",
                    status=PlanStatus.FAILED,
                    items=list(plan.items),
                    message=(
                        "Refusing to modify files because the operation journal "
                        f"could not be initialized: {exc}"
                    ),
                    journaled=False,
                )
        else:
            journaled = False

        results: list[PlanItem] = [
            item for item in plan.items if item.status != PlanItemStatus.READY
        ]
        succeeded = 0
        failed = 0
        cancelled = False

        total = len(ready)
        for index, item in enumerate(ready, start=1):
            if cancel_check is not None and cancel_check():
                cancelled = True
                for remaining in ready[index - 1 :]:
                    results.append(
                        PlanItem(
                            source=remaining.source,
                            destination=remaining.destination,
                            rule=remaining.rule,
                            status=PlanItemStatus.CANCELLED,
                            conflict_reason=remaining.conflict_reason,
                            source_size=remaining.source_size,
                            source_mtime_ns=remaining.source_mtime_ns,
                            error_message="Cancelled before execution.",
                        )
                    )
                break

            if progress_callback is not None:
                progress_callback(
                    ExecutionProgress(
                        completed=index - 1,
                        total=total,
                        succeeded=succeeded,
                        failed=failed,
                        current_source=str(item.source),
                    )
                )

            entry_id: int | None = None
            if self._journal is not None and batch_id:
                try:
                    entry_id = self._journal.add_entry(
                        batch_id,
                        source_path=str(item.source),
                        destination_path=str(item.destination),
                        status="pending",
                    )
                except RuntimeError:
                    failed += 1
                    results.append(
                        PlanItem(
                            source=item.source,
                            destination=item.destination,
                            rule=item.rule,
                            status=PlanItemStatus.FAILED,
                            source_size=item.source_size,
                            source_mtime_ns=item.source_mtime_ns,
                            error_message=(
                                "Journal write failed; remaining moves were not attempted."
                            ),
                        )
                    )
                    for remaining in ready[index:]:
                        results.append(
                            PlanItem(
                                source=remaining.source,
                                destination=remaining.destination,
                                rule=remaining.rule,
                                status=PlanItemStatus.CANCELLED,
                                source_size=remaining.source_size,
                                source_mtime_ns=remaining.source_mtime_ns,
                                error_message="Skipped after journal failure.",
                            )
                        )
                    cancelled = True
                    break

            outcome = self._move_one(item, plan)
            results.append(outcome)
            if outcome.status == PlanItemStatus.SUCCESS:
                succeeded += 1
                if self._journal is not None and entry_id is not None:
                    try:
                        self._journal.complete_entry(entry_id, status="success")
                    except RuntimeError:
                        journaled = False
            else:
                failed += 1
                if self._journal is not None and entry_id is not None:
                    try:
                        self._journal.complete_entry(
                            entry_id,
                            status="failed",
                            error_details=outcome.error_message,
                        )
                    except RuntimeError:
                        journaled = False

        if progress_callback is not None:
            progress_callback(
                ExecutionProgress(
                    completed=succeeded + failed,
                    total=total,
                    succeeded=succeeded,
                    failed=failed,
                )
            )

        if cancelled and succeeded == 0 and failed == 0:
            status = PlanStatus.CANCELLED
            message = "Organization cancelled before any files were moved."
        elif cancelled:
            status = PlanStatus.PARTIAL
            message = (
                f"Organization cancelled after {succeeded} success(es) "
                f"and {failed} failure(s)."
            )
        elif failed and succeeded:
            status = PlanStatus.PARTIAL
            message = (
                f"Organization finished with partial success: "
                f"{succeeded} moved, {failed} failed."
            )
        elif failed:
            status = PlanStatus.FAILED
            message = f"Organization failed: {failed} file(s) could not be moved."
        else:
            status = PlanStatus.COMPLETED
            message = f"Organization completed: {succeeded} file(s) moved."

        if self._journal is not None and batch_id:
            batch_status = {
                PlanStatus.COMPLETED: "completed",
                PlanStatus.PARTIAL: "partial",
                PlanStatus.CANCELLED: "cancelled",
                PlanStatus.FAILED: "failed",
            }.get(status, "failed")
            try:
                self._journal.complete_batch(batch_id, status=batch_status, summary=message)
            except RuntimeError:
                journaled = False
                message += " Journal finalization failed; undo may be unreliable."

        if not journaled and status == PlanStatus.COMPLETED:
            message += " Warning: journaling was incomplete."

        return ExecutionResult(
            plan=plan,
            batch_id=batch_id,
            status=status,
            items=results,
            message=message,
            journaled=journaled,
        )

    def _move_one(self, item: PlanItem, plan: OrganizePlan) -> PlanItem:
        source = normalize_path(item.source)
        destination = normalize_path(item.destination)

        def fail(message: str) -> PlanItem:
            return PlanItem(
                source=source,
                destination=destination,
                rule=item.rule,
                status=PlanItemStatus.FAILED,
                conflict_reason=item.conflict_reason,
                source_size=item.source_size,
                source_mtime_ns=item.source_mtime_ns,
                error_message=message,
            )

        try:
            if not source.exists():
                return fail("Source file disappeared after preview.")
            if source.is_symlink():
                return fail("Source became a symbolic link after preview.")
            ensure_not_symlink_or_junction(source)
            if not source.is_file():
                return fail("Source is no longer a regular file.")

            if not is_within(source, plan.source_root):
                return fail("Source file is outside the selected source folder.")
            if not is_within(destination, plan.destination_root):
                return fail("Destination escapes the selected destination folder.")

            size, mtime_ns = _fingerprint(source)
            if size != item.source_size or mtime_ns != item.source_mtime_ns:
                return fail(
                    "Source file changed after preview; move rejected to avoid "
                    "acting on a stale plan."
                )

            if destination.exists():
                return fail("Destination already exists; refusing to overwrite.")

            if is_same_path(source, destination):
                return fail("Source and destination are the same path.")

            if is_within(destination, source):
                return fail("Destination resolves inside the source path.")

            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                return fail("Destination appeared before move; refusing to overwrite.")

            try:
                source.rename(destination)
            except OSError as exc:
                if getattr(exc, "errno", None) == errno.EXDEV:
                    return fail(
                        "Cross-filesystem move is not supported. "
                        "Choose a destination on the same drive."
                    )
                if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {
                    5,
                    32,
                    33,
                }:
                    return fail(f"Permission or sharing lock prevented the move: {exc}")
                return fail(f"Move failed: {exc}")

            if not destination.exists():
                return fail("Move could not be verified at the destination.")
            if source.exists():
                return fail(
                    "Source still exists after rename; outcome is ambiguous and "
                    "was not marked successful."
                )

            return PlanItem(
                source=source,
                destination=destination,
                rule=item.rule,
                status=PlanItemStatus.SUCCESS,
                source_size=item.source_size,
                source_mtime_ns=item.source_mtime_ns,
            )
        except Exception as exc:  # noqa: BLE001 - convert to failed plan item
            return fail(f"Unexpected error: {exc}")
