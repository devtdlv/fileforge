"""Unit tests for the read-only FolderScanner engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from fileforge.services.scanner import (
    EntryKind,
    FolderScanner,
    ScanStatus,
    format_byte_size,
)


def _build_sample_tree(root: Path) -> None:
    (root / "readme.txt").write_text("hello", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "nested.json").write_text("{}", encoding="utf-8")
    (root / "data" / "deep").mkdir()
    (root / "data" / "deep" / "note.md").write_text("# note", encoding="utf-8")
    (root / "unicode-文件名.txt").write_text("ok", encoding="utf-8")


def test_recursive_scan_collects_files_and_directories(tmp_path: Path) -> None:
    _build_sample_tree(tmp_path)
    result = FolderScanner().scan(tmp_path, recursive=True)

    assert result.status == ScanStatus.COMPLETED
    assert result.file_count == 4
    assert result.directory_count == 2
    names = {entry.name for entry in result.entries}
    assert "readme.txt" in names
    assert "nested.json" in names
    assert "note.md" in names
    assert "unicode-文件名.txt" in names
    assert "data" in names
    assert "deep" in names

    readme = next(entry for entry in result.entries if entry.name == "readme.txt")
    assert readme.kind == EntryKind.FILE
    assert readme.extension == "txt"
    assert readme.size_bytes == 5
    assert readme.relative_path == "readme.txt"
    assert readme.modified_at is not None


def test_nonrecursive_scan_lists_only_top_level(tmp_path: Path) -> None:
    _build_sample_tree(tmp_path)
    result = FolderScanner().scan(tmp_path, recursive=False)

    assert result.status == ScanStatus.COMPLETED
    assert result.file_count == 2  # readme + unicode
    assert result.directory_count == 1  # data
    names = {entry.name for entry in result.entries}
    assert "note.md" not in names
    assert "nested.json" not in names
    assert "data" in names


def test_cancellation_stops_scan(tmp_path: Path) -> None:
    for index in range(40):
        (tmp_path / f"file_{index:02d}.txt").write_text("x", encoding="utf-8")

    cancel_flag = {"stop": False}

    def cancel_check() -> bool:
        return cancel_flag["stop"]

    def progress_and_cancel(progress) -> None:
        if progress.files_seen >= 3:
            cancel_flag["stop"] = True

    result = FolderScanner().scan(
        tmp_path,
        recursive=True,
        cancel_check=cancel_check,
        progress_callback=progress_and_cancel,
        progress_every=1,
    )
    assert result.status == ScanStatus.CANCELLED
    assert result.file_count < 40


def test_missing_root_fails(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = FolderScanner().scan(missing)
    assert result.status == ScanStatus.FAILED
    assert not result.entries


def test_file_as_root_fails(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    result = FolderScanner().scan(target)
    assert result.status == ScanStatus.FAILED


def test_permission_error_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_sample_tree(tmp_path)

    real_scandir = os.scandir

    def flaky_scandir(path):
        if Path(path).name == "data":
            raise PermissionError("denied for test")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", flaky_scandir)
    result = FolderScanner().scan(tmp_path, recursive=True)
    assert result.status == ScanStatus.PARTIAL
    assert any("Permission denied" in error.message for error in result.errors)
    assert result.file_count >= 1


def test_disappeared_file_during_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "keep.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "ghost.txt").write_text("bye", encoding="utf-8")

    original_lstat = Path.lstat

    def flaky_lstat(self: Path):
        if self.name == "ghost.txt":
            raise FileNotFoundError("gone")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    result = FolderScanner().scan(tmp_path, recursive=False)
    assert any("disappeared" in error.message.lower() for error in result.errors)
    assert any(entry.name == "keep.txt" for entry in result.entries)


def test_symlink_is_listed_but_not_followed(tmp_path: Path) -> None:
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "secret.txt").write_text("secret", encoding="utf-8")
    link = tmp_path / "link-to-target"
    try:
        link.symlink_to(target_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")

    result = FolderScanner().scan(tmp_path, recursive=True)
    names = {entry.name for entry in result.entries}
    assert "link-to-target" in names
    assert "secret.txt" not in names
    link_entry = next(entry for entry in result.entries if entry.name == "link-to-target")
    assert link_entry.kind == EntryKind.SYMLINK


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions only")
def test_junction_is_listed_but_not_followed(tmp_path: Path) -> None:
    target_dir = tmp_path / "junction-target"
    target_dir.mkdir()
    (target_dir / "inside.txt").write_text("x", encoding="utf-8")
    junction = tmp_path / "junction-link"
    try:
        # Prefer os.symlink with dir flag; if that creates a symlink not junction, still OK.
        os.symlink(str(target_dir), str(junction), target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Unable to create directory link: {exc}")

    result = FolderScanner().scan(tmp_path, recursive=True)
    names = {entry.name for entry in result.entries}
    assert "junction-link" in names
    assert "inside.txt" not in names
    entry = next(item for item in result.entries if item.name == "junction-link")
    assert entry.kind in {EntryKind.SYMLINK, EntryKind.JUNCTION}


def test_scan_does_not_modify_files(tmp_path: Path) -> None:
    sample = tmp_path / "tracked.txt"
    sample.write_text("immutable", encoding="utf-8")
    before = sample.stat()
    FolderScanner().scan(tmp_path, recursive=True)
    after = sample.stat()
    assert before.st_mtime_ns == after.st_mtime_ns
    assert before.st_size == after.st_size
    assert sample.read_text(encoding="utf-8") == "immutable"


def test_format_byte_size() -> None:
    assert format_byte_size(0) == "0 B"
    assert format_byte_size(1024).endswith("KB")


def test_traversal_loop_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "file.txt").write_text("x", encoding="utf-8")

    real_resolve = Path.resolve

    def looping_resolve(self: Path, *args, **kwargs):
        if self.name in {"a", "b"}:
            return tmp_path / "LOOP"
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", looping_resolve)
    result = FolderScanner().scan(tmp_path, recursive=True)
    assert any("loop" in error.message.lower() for error in result.errors)
