"""Planner tests for bulk rename preview and conflict detection."""

from __future__ import annotations

from pathlib import Path

from fileforge.services.renamer import (
    CaseMode,
    RenameItemStatus,
    RenamePlanner,
    RenamePlanStatus,
    RenameRules,
)


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_valid_preview_and_deterministic_numbering(tmp_path: Path) -> None:
    a = _touch(tmp_path / "b.txt", b"1")
    b = _touch(tmp_path / "a.txt", b"2")
    rules = RenameRules(
        numbering_enabled=True,
        number_start=1,
        number_padding=3,
        number_separator="_",
    )
    plan = RenamePlanner().build_plan(tmp_path, [a, b], rules)
    assert plan.status == RenamePlanStatus.READY
    by_name = {item.source.name: item for item in plan.items}
    assert by_name["a.txt"].proposed_name == "a_001.txt"
    assert by_name["b.txt"].proposed_name == "b_002.txt"


def test_empty_selection(tmp_path: Path) -> None:
    plan = RenamePlanner().build_plan(tmp_path, [], RenameRules(prefix="x_"))
    assert plan.status == RenamePlanStatus.EMPTY


def test_noop_unchanged(tmp_path: Path) -> None:
    path = _touch(tmp_path / "keep.txt")
    plan = RenamePlanner().build_plan(tmp_path, [path], RenameRules())
    assert plan.items[0].status == RenameItemStatus.UNCHANGED
    assert plan.status == RenamePlanStatus.EMPTY


def test_destination_occupied_by_unselected_file(tmp_path: Path) -> None:
    left = _touch(tmp_path / "left.txt")
    _touch(tmp_path / "right.txt")
    plan = RenamePlanner().build_plan(
        tmp_path, [left], RenameRules(search="left", replace="right")
    )
    assert plan.status == RenamePlanStatus.BLOCKED
    assert plan.items[0].status == RenameItemStatus.CONFLICT


def test_selected_peer_blocks_when_not_moving_away(tmp_path: Path) -> None:
    left = _touch(tmp_path / "left.txt")
    right = _touch(tmp_path / "right.txt")
    plan = RenamePlanner().build_plan(
        tmp_path,
        [left, right],
        RenameRules(search="left", replace="right"),
    )
    assert any(i.status == RenameItemStatus.CONFLICT for i in plan.items)


def test_duplicate_proposed_targets(tmp_path: Path) -> None:
    """Renaming one selected file onto another's current name is a conflict."""
    one = _touch(tmp_path / "one_src.txt", b"1")
    two = _touch(tmp_path / "two_src.txt", b"2")
    plan = RenamePlanner().build_plan(
        tmp_path,
        [one, two],
        RenameRules(search="one_src", replace="two_src"),
    )
    assert any(i.status == RenameItemStatus.CONFLICT for i in plan.items)


def test_existing_target_conflict(tmp_path: Path) -> None:
    src = _touch(tmp_path / "old.txt")
    _touch(tmp_path / "taken.txt")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(search="old", replace="taken")
    )
    assert plan.status == RenamePlanStatus.BLOCKED
    assert plan.items[0].status == RenameItemStatus.CONFLICT


def test_invalid_and_reserved_names(tmp_path: Path) -> None:
    path = _touch(tmp_path / "ok.txt")
    plan = RenamePlanner().build_plan(
        tmp_path, [path], RenameRules(search="ok", replace="NUL")
    )
    assert plan.items[0].status == RenameItemStatus.INVALID

    plan2 = RenamePlanner().build_plan(
        tmp_path, [path], RenameRules(prefix="bad:")
    )
    assert plan2.items[0].status == RenameItemStatus.INVALID


def test_case_insensitive_collision(tmp_path: Path) -> None:
    src = _touch(tmp_path / "Report.txt")
    _touch(tmp_path / "other.TXT")
    plan = RenamePlanner().build_plan(
        tmp_path, [src], RenameRules(search="Report", replace="other")
    )
    assert plan.items[0].status == RenameItemStatus.CONFLICT


def test_case_only_rename_is_ready(tmp_path: Path) -> None:
    path = _touch(tmp_path / "Mixed.txt")
    plan = RenamePlanner().build_plan(
        tmp_path, [path], RenameRules(case_mode=CaseMode.LOWER)
    )
    assert plan.items[0].status == RenameItemStatus.READY
    assert plan.items[0].proposed_name == "mixed.txt"
    assert plan.status == RenamePlanStatus.READY


def test_nested_folders_and_unicode(tmp_path: Path) -> None:
    nested = tmp_path / "子"
    path = _touch(nested / "照片.JPG", b"img")
    plan = RenamePlanner().build_plan(
        tmp_path, [path], RenameRules(prefix="trip_"), recursive=True
    )
    assert plan.status == RenamePlanStatus.READY
    assert plan.items[0].proposed_name == "trip_照片.JPG"


def test_missing_source(tmp_path: Path) -> None:
    missing = tmp_path / "gone.txt"
    plan = RenamePlanner().build_plan(tmp_path, [missing], RenameRules(prefix="x_"))
    assert plan.items[0].status == RenameItemStatus.MISSING


def test_inventory_skips_directories(tmp_path: Path) -> None:
    _touch(tmp_path / "a.txt")
    (tmp_path / "subdir").mkdir()
    files = RenamePlanner().inventory(tmp_path, recursive=True)
    assert len(files) == 1
    assert files[0].name == "a.txt"


def test_numbering_chain_preview_ready(tmp_path: Path) -> None:
    """photo → photo_001 while photo_001 → photo_001_001 is a valid staged chain."""
    first = _touch(tmp_path / "photo.txt", b"1")
    second = _touch(tmp_path / "photo_001.txt", b"2")
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
    assert plan.status == RenamePlanStatus.READY
    by_name = {i.source.name: i.proposed_name for i in plan.items}
    assert by_name["photo.txt"] == "photo_001.txt"
    assert by_name["photo_001.txt"] == "photo_001_002.txt"
