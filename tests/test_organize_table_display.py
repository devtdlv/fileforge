"""Tests for Organizer preview path display formatting."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fileforge.services.organizer import (
    OrganizeMode,
    OrganizePlanner,
    PlanItem,
    PlanItemStatus,
)
from fileforge.services.organizer.paths import relative_display_path
from fileforge.ui.models.organize_table_model import OrganizeTableModel


def test_relative_display_path_nested_and_unicode(tmp_path: Path) -> None:
    source = tmp_path / "src"
    nested = source / "photos" / "2024"
    nested.mkdir(parents=True)
    file_path = nested / "假期-照片.jpg"
    file_path.write_bytes(b"img")

    assert relative_display_path(file_path, source) == "photos/2024/假期-照片.jpg"
    assert relative_display_path(file_path, None) == "假期-照片.jpg"


def test_relative_destination_display(tmp_path: Path) -> None:
    dest = tmp_path / "dst"
    target = dest / "Images" / "photo.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    assert relative_display_path(target, dest) == "Images/photo.jpg"


def test_table_model_shows_relative_keeps_absolute(qapp: QApplication, tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "nested").mkdir()
    src_file = source / "nested" / "report.txt"
    src_file.write_text("data", encoding="utf-8")
    dest_file = dest / "Documents" / "report.txt"

    item = PlanItem(
        source=src_file,
        destination=dest_file,
        rule="Category: Documents",
        status=PlanItemStatus.READY,
        source_size=4,
        source_mtime_ns=1,
    )
    model = OrganizeTableModel()
    model.set_items([item], source_root=source, destination_root=dest)

    source_index = model.index(0, 1)
    dest_index = model.index(0, 2)
    assert model.data(source_index, Qt.ItemDataRole.DisplayRole) == "nested/report.txt"
    assert model.data(dest_index, Qt.ItemDataRole.DisplayRole) == "Documents/report.txt"
    assert model.data(source_index, Qt.ItemDataRole.UserRole) == str(src_file)
    assert model.data(dest_index, Qt.ItemDataRole.UserRole) == str(dest_file)
    assert str(src_file) in str(model.data(source_index, Qt.ItemDataRole.ToolTipRole))
    assert str(dest_file) in str(model.data(dest_index, Qt.ItemDataRole.ToolTipRole))

    # Underlying plan item paths remain absolute Path objects.
    stored = model.items()[0]
    assert stored.source == src_file
    assert stored.destination == dest_file


def test_preview_plan_unchanged_by_display_formatting(tmp_path: Path) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "deep").mkdir()
    (source / "deep" / "photo.jpg").write_bytes(b"img")

    plan = OrganizePlanner().build_plan(
        source, dest, mode=OrganizeMode.CATEGORY, recursive=True
    )
    assert plan.ready_items
    original = [
        (item.source, item.destination, item.rule, item.status)
        for item in plan.items
    ]

    model = OrganizeTableModel()
    model.set_items(
        plan.items,
        source_root=plan.source_root,
        destination_root=plan.destination_root,
    )
    after = [
        (item.source, item.destination, item.rule, item.status)
        for item in model.items()
    ]
    assert after == original
    display_source = model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole)
    assert "C:" not in str(display_source)
    assert display_source == "deep/photo.jpg"
