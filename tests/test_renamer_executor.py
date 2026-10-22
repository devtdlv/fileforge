"""Execution and journal tests for bulk rename."""

from __future__ import annotations

from pathlib import Path

from fileforge.database.connection import DatabaseManager
from fileforge.database.journal import OperationJournal
from fileforge.services.renamer import (
    CaseMode,
    RenameExecutor,
    RenameItemStatus,
    RenamePlanner,
    RenamePlanStatus,
    RenameRules,
)


def _touch(path: Path, data: bytes = b"payload") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_successful_rename_preserves_contents(tmp_path: Path) -> None:
    src = _touch(tmp_path / "photo.jpg", b"image-bytes")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(prefix="holiday_")
    )
    assert plan.can_apply
    result = RenameExecutor().execute(plan)
    assert result.status == RenamePlanStatus.COMPLETED
    dest = tmp_path / "holiday_photo.jpg"
    assert dest.exists()
    assert dest.read_bytes() == b"image-bytes"
    assert not src.exists()
    assert not list(tmp_path.glob(".fileforge_rename_tmp_*"))


def test_no_overwrite(tmp_path: Path) -> None:
    src = _touch(tmp_path / "old.txt", b"old")
    taken = _touch(tmp_path / "taken.txt", b"keep")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(search="old", replace="taken")
    )
    assert not plan.can_apply
    result = RenameExecutor().execute(plan)
    assert result.status == RenamePlanStatus.BLOCKED
    assert taken.read_bytes() == b"keep"
    assert src.exists()


def test_case_only_rename(tmp_path: Path) -> None:
    src = _touch(tmp_path / "Mixed.TXT", b"data")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(case_mode=CaseMode.LOWER)
    )
    assert plan.can_apply
    assert plan.items[0].proposed_name == "mixed.TXT"  # stem only; ext casing kept
    result = RenameExecutor().execute(plan)
    assert result.status == RenamePlanStatus.COMPLETED
    names = [p.name for p in tmp_path.iterdir() if p.is_file()]
    assert names == ["mixed.TXT"]
    assert (tmp_path / "mixed.TXT").read_bytes() == b"data"


def test_numbering_chain_uses_staging(tmp_path: Path) -> None:
    """photo.txt → photo_001.txt while photo_001.txt → photo_001_001.txt."""
    first = _touch(tmp_path / "photo.txt", b"one")
    second = _touch(tmp_path / "photo_001.txt", b"two")
    plan = RenamePlanner().build_plan(
        tmp_path,
        [first, second],
        RenameRules(
            numbering_enabled=True,
            number_start=1,
            number_padding=3,
            number_separator="_",
        ),
    )
    assert plan.can_apply
    by_name = {i.source.name: i.proposed_name for i in plan.items}
    # Numbering order is sorted; photo.txt → _001, photo_001.txt → _002
    assert by_name["photo.txt"] == "photo_001.txt"
    assert by_name["photo_001.txt"] == "photo_001_002.txt"
    result = RenameExecutor().execute(plan)
    assert result.status == RenamePlanStatus.COMPLETED
    assert (tmp_path / "photo_001.txt").read_bytes() == b"one"
    assert (tmp_path / "photo_001_002.txt").read_bytes() == b"two"
    assert not list(tmp_path.glob(".fileforge_rename_tmp_*"))


def test_stale_plan_rejected(tmp_path: Path) -> None:
    src = _touch(tmp_path / "doc.txt", b"v1")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(prefix="new_")
    )
    src.write_bytes(b"v2-changed")
    result = RenameExecutor().execute(plan)
    assert result.status in {RenamePlanStatus.FAILED, RenamePlanStatus.PARTIAL}
    assert any(
        item.status in {RenameItemStatus.STALE, RenameItemStatus.FAILED}
        for item in result.items
    )


def test_missing_source_at_execution(tmp_path: Path) -> None:
    src = _touch(tmp_path / "ephemeral.txt", b"x")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(prefix="z_")
    )
    src.unlink()
    result = RenameExecutor().execute(plan)
    assert result.status == RenamePlanStatus.FAILED
    assert any(item.status == RenameItemStatus.FAILED for item in result.items)


def test_cancellation_before_work(tmp_path: Path) -> None:
    files = [_touch(tmp_path / f"f{i}.txt", b"x") for i in range(5)]
    plan = RenamePlanner().build_plan(
        tmp_path, files, RenameRules(prefix="n_")
    )
    result = RenameExecutor().execute(plan, cancel_check=lambda: True)
    assert result.status == RenamePlanStatus.CANCELLED
    assert all((tmp_path / f"f{i}.txt").exists() for i in range(5))


def test_journal_records_outcomes(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "journal.db")
    db.initialize()
    journal = OperationJournal(db)
    src = _touch(tmp_path / "note.md", b"hi")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(suffix="_done")
    )
    result = RenameExecutor(journal).execute(plan)
    assert result.status == RenamePlanStatus.COMPLETED
    assert result.journaled
    assert result.batch_id
    batch = journal.get_batch(result.batch_id)
    assert batch is not None
    assert batch["operation_type"] == "bulk_rename"
    assert batch["status"] == "completed"
    entries = journal.list_batch_entries(result.batch_id)
    assert len(entries) == 1
    assert entries[0]["status"] == "success"
    assert entries[0]["operation_type"] == "rename"
    db.close()


def test_journal_failure_refuses_execution(tmp_path: Path) -> None:
    class BoomJournal(OperationJournal):
        def begin_batch(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("disk full")

    src = _touch(tmp_path / "a.txt", b"a")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(prefix="p_")
    )
    # OperationJournal requires a database; bypass by constructing poorly.
    # Use a real journal then monkeypatch:
    db = DatabaseManager(tmp_path / "j.db")
    db.initialize()
    journal = OperationJournal(db)

    def boom(**_kwargs):
        raise RuntimeError("disk full")

    journal.begin_batch = boom  # type: ignore[method-assign]
    result = RenameExecutor(journal).execute(plan)
    assert result.status == RenamePlanStatus.FAILED
    assert not result.journaled
    assert src.exists()
    db.close()
