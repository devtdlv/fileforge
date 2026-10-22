"""Unit tests for the read-only duplicate detection engine."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from fileforge.services.duplicates import (
    DuplicateFinder,
    DuplicateStatus,
    sha256_file,
)
from fileforge.services.duplicates.hasher import CHUNK_SIZE, FileChangedError


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    target = _write(tmp_path / "payload.bin", b"FileForge-duplicate-hash")
    st = target.lstat()
    digest = sha256_file(
        target,
        expected_size=st.st_size,
        expected_mtime_ns=int(st.st_mtime_ns),
    )
    assert digest == hashlib.sha256(b"FileForge-duplicate-hash").hexdigest()


def test_chunked_hashing_of_large_file(tmp_path: Path) -> None:
    payload = (b"ABCDEFGH" * 200_000)  # ~1.6 MiB > CHUNK_SIZE
    assert len(payload) > CHUNK_SIZE
    target = _write(tmp_path / "large.bin", payload)
    st = target.lstat()
    digest = sha256_file(
        target,
        expected_size=st.st_size,
        expected_mtime_ns=int(st.st_mtime_ns),
        chunk_size=64 * 1024,
    )
    assert digest == hashlib.sha256(payload).hexdigest()


def test_size_filter_skips_unique_sizes(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", b"aaa")
    _write(tmp_path / "b.txt", b"bbbb")
    _write(tmp_path / "c.txt", b"ccccc")
    result = DuplicateFinder().find(tmp_path)
    assert result.status == DuplicateStatus.EMPTY
    assert result.hashed_files == 0
    assert result.group_count == 0


def test_true_duplicates_different_names(tmp_path: Path) -> None:
    content = b"identical-bytes-here"
    _write(tmp_path / "copy_one.dat", content)
    _write(tmp_path / "copy_two.dat", content)
    _write(tmp_path / "unique.dat", b"something-else")
    result = DuplicateFinder().find(tmp_path)
    assert result.status == DuplicateStatus.COMPLETED
    assert result.group_count == 1
    group = result.groups[0]
    assert group.path_count == 2
    assert group.size_bytes == len(content)
    assert group.sha256 == hashlib.sha256(content).hexdigest()
    assert group.potential_savings_bytes == len(content)
    assert result.potential_savings_bytes == len(content)
    names = {f.path.name for f in group.files}
    assert names == {"copy_one.dat", "copy_two.dat"}


def test_same_size_different_content_not_grouped(tmp_path: Path) -> None:
    _write(tmp_path / "left.bin", b"AAAA")
    _write(tmp_path / "right.bin", b"BBBB")
    result = DuplicateFinder().find(tmp_path)
    assert result.status == DuplicateStatus.EMPTY
    assert result.hashed_files == 2
    assert result.group_count == 0


def test_same_name_different_content_not_duplicates(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    _write(tmp_path / "report.txt", b"version-one")
    _write(nested / "report.txt", b"version-two-longer")
    result = DuplicateFinder().find(tmp_path)
    assert result.group_count == 0


def test_zero_byte_files_are_duplicates(tmp_path: Path) -> None:
    _write(tmp_path / "empty_a", b"")
    _write(tmp_path / "empty_b", b"")
    _write(tmp_path / "filled", b"x")
    result = DuplicateFinder().find(tmp_path)
    assert result.group_count == 1
    assert result.groups[0].size_bytes == 0
    assert result.groups[0].potential_savings_bytes == 0


def test_nested_and_unicode_paths(tmp_path: Path) -> None:
    content = b"nested-unicode-dup"
    _write(tmp_path / "top.txt", content)
    _write(tmp_path / "子目录" / "副本.txt", content)
    result = DuplicateFinder().find(tmp_path, recursive=True)
    assert result.group_count == 1
    assert result.groups[0].path_count == 2


def test_nonrecursive_skips_nested_duplicates(tmp_path: Path) -> None:
    content = b"only-top-level-matters"
    _write(tmp_path / "a.txt", content)
    _write(tmp_path / "deep" / "b.txt", content)
    result = DuplicateFinder().find(tmp_path, recursive=False)
    assert result.group_count == 0
    assert result.files_scanned == 1


def test_empty_folder(tmp_path: Path) -> None:
    result = DuplicateFinder().find(tmp_path)
    assert result.status == DuplicateStatus.EMPTY
    assert result.files_scanned == 0


def test_missing_root_fails(tmp_path: Path) -> None:
    result = DuplicateFinder().find(tmp_path / "missing")
    assert result.status == DuplicateStatus.FAILED


def test_cancellation_during_hashing(tmp_path: Path) -> None:
    payload = b"Z" * 50_000
    for index in range(12):
        _write(tmp_path / f"dup_{index}.bin", payload)

    cancel_flag = {"stop": False}

    def cancel_check() -> bool:
        return cancel_flag["stop"]

    def on_progress(progress) -> None:
        if progress.phase == "hashing" and progress.hashed >= 1:
            cancel_flag["stop"] = True

    result = DuplicateFinder().find(
        tmp_path,
        cancel_check=cancel_check,
        progress_callback=on_progress,
    )
    assert result.status == DuplicateStatus.CANCELLED


def test_file_changed_during_hash_is_excluded(tmp_path: Path) -> None:
    target = _write(tmp_path / "mutable.bin", b"original")
    st = target.lstat()
    target.write_bytes(b"changed!!")
    with pytest.raises(FileChangedError):
        sha256_file(
            target,
            expected_size=st.st_size,
            expected_mtime_ns=int(st.st_mtime_ns),
        )


def test_read_only_does_not_modify_files(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.txt", b"same")
    b = _write(tmp_path / "b.txt", b"same")
    before = {
        a: (a.read_bytes(), a.stat().st_mtime_ns, a.stat().st_size),
        b: (b.read_bytes(), b.stat().st_mtime_ns, b.stat().st_size),
    }
    DuplicateFinder().find(tmp_path)
    for path, (data, mtime, size) in before.items():
        assert path.read_bytes() == data
        assert path.stat().st_size == size
        assert path.stat().st_mtime_ns == mtime


def test_hard_link_savings_not_overstated(tmp_path: Path) -> None:
    content = b"hard-link-content"
    original = _write(tmp_path / "original.bin", content)
    linked = tmp_path / "linked.bin"
    try:
        os.link(original, linked)
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")

    # Two hard-linked paths alone are one physical file → not a duplicate group.
    result = DuplicateFinder().find(tmp_path)
    assert result.group_count == 0

    # Add a second physical copy with the same content.
    _write(tmp_path / "second_copy.bin", content)
    result = DuplicateFinder().find(tmp_path)
    assert result.group_count == 1
    group = result.groups[0]
    assert group.path_count == 3
    assert group.unique_physical_count == 2
    assert group.potential_savings_bytes == len(content)


def test_symlink_not_followed(tmp_path: Path) -> None:
    content = b"symlink-target-bytes"
    real = _write(tmp_path / "real.bin", content)
    link = tmp_path / "alias.bin"
    try:
        link.symlink_to(real)
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")

    _write(tmp_path / "other.bin", content)
    result = DuplicateFinder().find(tmp_path)
    # Only real.bin and other.bin should form a group; alias is skipped.
    assert result.group_count == 1
    names = {f.path.name for f in result.groups[0].files}
    assert "alias.bin" not in names
    assert names == {"real.bin", "other.bin"}


@pytest.mark.skipif(sys.platform != "win32", reason="Junction coverage is Windows-specific")
def test_junction_not_followed(tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    content = b"junction-dup"
    _write(inner / "a.bin", content)
    _write(tmp_path / "b.bin", content)
    junction = tmp_path / "linkdir"
    try:
        os.symlink(str(inner), str(junction), target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Directory link/junction unavailable: {exc}")

    result = DuplicateFinder().find(tmp_path, recursive=True)
    paths = [str(f.path) for g in result.groups for f in g.files]
    assert not any("linkdir" in p.lower() for p in paths)
