"""Functional smoke test for a packaged Junction.exe using disposable files.

Launches the frozen app indirectly is not practical for full GUI automation here.
Instead this script validates packaging invariants and exercises the same service
layer the EXE embeds, then optionally smoke-exits the packaged binary.

Usage (from repo root):

    .\\.venv\\Scripts\\python.exe tools\\smoke_packaged_junction.py
    .\\.venv\\Scripts\\python.exe tools\\smoke_packaged_junction.py --exe dist\\Junction\\Junction.exe
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fileforge import __app_name__, __version__  # noqa: E402
from fileforge.core.paths import get_default_database_path  # noqa: E402
from fileforge.database.connection import DatabaseManager  # noqa: E402
from fileforge.database.journal import OperationJournal  # noqa: E402
from fileforge.services.duplicates import DuplicateFinder  # noqa: E402
from fileforge.services.history import HistoryFilters, HistoryQueryService  # noqa: E402
from fileforge.services.organizer import OrganizeMode, OrganizePlanner  # noqa: E402
from fileforge.services.renamer import RenamePlanner, RenameRules  # noqa: E402
from fileforge.services.scanner import FolderScanner  # noqa: E402


def _write_demo(folder: Path) -> None:
    (folder / "reports").mkdir(parents=True)
    (folder / "photos").mkdir(parents=True)
    (folder / "reports" / "a.txt").write_text("junction package smoke\n", encoding="utf-8")
    (folder / "reports" / "b.md").write_text("# smoke\n", encoding="utf-8")
    payload = b"junction-pack-dup"
    (folder / "photos" / "x.bin").write_bytes(payload)
    (folder / "photos" / "y.bin").write_bytes(payload)
    (folder / "photos" / "z.bin").write_bytes(b"unique")


def _assert_db_path_invariant() -> None:
    path = get_default_database_path()
    assert path.name == "fileforge.db", path
    assert path.parent.name == "FileForge", path
    local = os.environ.get("LOCALAPPDATA")
    if local:
        assert str(path).lower().startswith(str(Path(local)).lower())
    print(f"OK database path invariant: {path}")


def _exercise_services(demo: Path, dest: Path) -> None:
    scan = FolderScanner().scan(demo, recursive=True)
    assert scan.file_count >= 5, scan
    print(f"OK scanner: {scan.file_count} files")

    plan = OrganizePlanner().build_plan(
        demo, dest, mode=OrganizeMode.EXTENSION, recursive=True
    )
    assert plan.items, plan
    print(f"OK organizer preview: {len(plan.items)} items")

    dups = DuplicateFinder().find(demo, recursive=True)
    assert dups.group_count >= 1, dups
    print(f"OK duplicates: {dups.group_count} group(s)")

    rename = RenamePlanner().build_plan(
        demo,
        [demo / "reports" / "a.txt"],
        RenameRules(prefix="pack_"),
        recursive=False,
    )
    assert rename.items, rename
    print(f"OK renamer preview: {len(rename.items)} item(s)")

    # Journal write/read using a temporary database (never touches user history).
    with tempfile.TemporaryDirectory(prefix="junction-pack-db-") as tmp:
        db_path = Path(tmp) / "smoke.db"
        database = DatabaseManager(db_path)
        database.initialize()
        journal = OperationJournal(database)
        batch = journal.begin_batch(
            operation_type="bulk_rename",
            summary="pack smoke",
            source_root=str(demo),
            destination_root=str(demo),
            mode="prefix",
        )
        eid = journal.add_entry(
            batch,
            source_path=str(demo / "reports" / "a.txt"),
            destination_path=str(demo / "reports" / "pack_a.txt"),
            operation_type="rename",
        )
        journal.complete_entry(eid, status="success")
        journal.complete_batch(batch, status="completed", summary="1 renamed")
        history = HistoryQueryService(database).list_batches(HistoryFilters(limit=10))
        assert history.totals.all_batches == 1
        database.close()
        print("OK journal write/read on disposable database")


def _smoke_exe(exe: Path) -> None:
    if not exe.is_file():
        raise SystemExit(f"Executable not found: {exe}")
    env = os.environ.copy()
    env["FILEFORGE_SMOKE_EXIT"] = "1"
    started = time.perf_counter()
    completed = subprocess.run(
        [str(exe)],
        cwd=str(exe.parent),
        env=env,
        check=False,
        timeout=60,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise SystemExit(f"Packaged EXE smoke failed with exit {completed.returncode}")
    print(f"OK packaged EXE smoke exit=0 in {elapsed:.2f}s ({exe})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe",
        type=Path,
        default=ROOT / "dist" / "Junction" / "Junction.exe",
        help="Path to Junction.exe",
    )
    parser.add_argument("--skip-exe", action="store_true")
    args = parser.parse_args()

    print(f"App: {__app_name__} {__version__}")
    _assert_db_path_invariant()

    tmp = Path(tempfile.mkdtemp(prefix="junction-pack-smoke-"))
    try:
        demo = tmp / "demo"
        dest = tmp / "out"
        dest.mkdir()
        _write_demo(demo)
        _exercise_services(demo, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not args.skip_exe:
        _smoke_exe(args.exe.resolve())

    digest = hashlib.sha256(args.exe.read_bytes()).hexdigest() if args.exe.is_file() else None
    if digest:
        print(f"EXE SHA-256 (informational): {digest}")
    print("Packaging smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
