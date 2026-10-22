"""Tests for organization planning, safe execution, and journaling."""

from __future__ import annotations

from pathlib import Path

from fileforge.database.connection import DatabaseManager
from fileforge.database.journal import OperationJournal
from fileforge.database.schema import CURRENT_SCHEMA_VERSION
from fileforge.services.organizer import (
    OrganizeExecutor,
    OrganizeMode,
    OrganizePlanner,
    PlanItemStatus,
    PlanStatus,
)
from fileforge.services.organizer.categories import category_for_extension


def _tree(root: Path) -> None:
    (root / "photo.jpg").write_bytes(b"jpeg-bytes")
    (root / "notes.txt").write_text("hello", encoding="utf-8")
    (root / "song.mp3").write_bytes(b"id3")
    (root / "archive.zip").write_bytes(b"PK")
    nested = root / "nested"
    nested.mkdir()
    (nested / "clip.mp4").write_bytes(b"ftyp")


def test_schema_version_is_two(database: DatabaseManager) -> None:
    assert database.schema_version() == CURRENT_SCHEMA_VERSION == 2
    tables = {
        row["name"]
        for row in database.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "operation_batches" in tables
    assert "operation_entries" in tables


def test_category_mapping() -> None:
    assert category_for_extension("PNG") == "Images"
    assert category_for_extension("pdf") == "Documents"
    assert category_for_extension("mp4") == "Videos"
    assert category_for_extension("mp3") == "Audio"
    assert category_for_extension("zip") == "Archives"
    assert category_for_extension("xyz") == "Other"


def test_preview_by_extension_does_not_modify_files(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    _tree(source)
    before = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }

    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.status == PlanStatus.READY
    assert plan.can_apply
    assert any(item.destination.name == "photo.jpg" for item in plan.ready_items)
    assert any("jpg" in str(item.destination).lower() for item in plan.ready_items)

    after = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert list(dest.iterdir()) == []


def test_preview_by_category(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    _tree(source)
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.CATEGORY, recursive=False
    )
    assert plan.status == PlanStatus.READY
    destinations = {str(item.destination) for item in plan.ready_items}
    assert any("Images" in path for path in destinations)
    assert any("Documents" in path for path in destinations)
    assert all("clip.mp4" not in path for path in destinations)  # nonrecursive


def test_preview_by_year_month(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "dated.txt").write_text("x", encoding="utf-8")
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.YEAR_MONTH, recursive=True
    )
    assert plan.status == PlanStatus.READY
    assert plan.ready_items
    assert any(
        item.destination.parent.name.isdigit() or "UnknownDate" in str(item.destination)
        for item in plan.ready_items
    )


def test_collision_blocks_apply(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.txt").write_text("1", encoding="utf-8")
    (dest / "txt").mkdir()
    (dest / "txt" / "a.txt").write_text("existing", encoding="utf-8")

    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.status == PlanStatus.BLOCKED
    assert not plan.can_apply
    assert any(item.status == PlanItemStatus.CONFLICT for item in plan.items)


def test_case_insensitive_duplicate_targets_conflict(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "left").mkdir()
    (source / "right").mkdir()
    (source / "left" / "Report.txt").write_text("one", encoding="utf-8")
    (source / "right" / "report.txt").write_text("two", encoding="utf-8")

    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.status == PlanStatus.BLOCKED
    assert not plan.can_apply
    assert any("collision" in item.conflict_reason.lower() for item in plan.conflict_items)


def test_safe_execute_and_journal(tmp_path: Path, database: DatabaseManager) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "photo.jpg").write_bytes(b"jpeg")
    (source / "notes.txt").write_text("doc", encoding="utf-8")

    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.CATEGORY, recursive=True
    )
    assert plan.can_apply
    result = OrganizeExecutor(OperationJournal(database)).execute(plan)
    assert result.status == PlanStatus.COMPLETED
    assert result.journaled
    assert not (source / "photo.jpg").exists()
    assert (dest / "Images" / "photo.jpg").exists()
    assert (dest / "Documents" / "notes.txt").read_text(encoding="utf-8") == "doc"

    batch = database.connection.execute(
        "SELECT * FROM operation_batches WHERE id = ?", (result.batch_id,)
    ).fetchone()
    assert batch is not None
    assert batch["status"] == "completed"
    entries = database.connection.execute(
        "SELECT * FROM operation_entries WHERE batch_id = ?", (result.batch_id,)
    ).fetchall()
    assert len(entries) == 2
    assert all(row["status"] == "success" for row in entries)


def test_stale_plan_rejected(tmp_path: Path, database: DatabaseManager) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    target = source / "a.txt"
    target.write_text("v1", encoding="utf-8")
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.can_apply
    target.write_text("changed-after-preview", encoding="utf-8")
    result = OrganizeExecutor(OperationJournal(database)).execute(plan)
    assert result.status == PlanStatus.FAILED
    assert target.exists()
    assert "changed after preview" in result.items[-1].error_message.lower()


def test_refuse_overwrite_at_execution(tmp_path: Path, database: DatabaseManager) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.txt").write_text("src", encoding="utf-8")
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.can_apply
    # Create conflicting destination after preview.
    (dest / "txt").mkdir()
    (dest / "txt" / "a.txt").write_text("blocked", encoding="utf-8")
    result = OrganizeExecutor(OperationJournal(database)).execute(plan)
    assert result.status == PlanStatus.FAILED
    assert (source / "a.txt").exists()
    assert (dest / "txt" / "a.txt").read_text(encoding="utf-8") == "blocked"


def test_execution_cancellation(tmp_path: Path, database: DatabaseManager) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    for index in range(10):
        (source / f"f{index}.txt").write_text(str(index), encoding="utf-8")
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.can_apply
    cancel = {"stop": False}

    def cancel_check() -> bool:
        return cancel["stop"]

    def progress(progress) -> None:
        if progress.completed >= 1:
            cancel["stop"] = True

    result = OrganizeExecutor(OperationJournal(database)).execute(
        plan,
        cancel_check=cancel_check,
        progress_callback=progress,
    )
    assert result.status in {PlanStatus.CANCELLED, PlanStatus.PARTIAL}
    remaining = list(source.glob("*.txt"))
    assert remaining  # not everything moved


def test_journal_failure_blocks_execution(tmp_path: Path, database: DatabaseManager) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")
    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )

    class BrokenJournal(OperationJournal):
        def begin_batch(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("boom")

    result = OrganizeExecutor(BrokenJournal(database)).execute(plan)
    assert result.status == PlanStatus.FAILED
    assert (source / "a.txt").exists()
    assert result.journaled is False


def test_missing_source_folder_fails(tmp_path: Path) -> None:
    dest = tmp_path / "dst"
    dest.mkdir()
    plan = OrganizePlanner().build_plan(
        tmp_path / "missing", dest, mode=OrganizeMode.EXTENSION
    )
    assert plan.status == PlanStatus.FAILED
