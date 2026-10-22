"""Capture authentic Junction portfolio screenshots from the live PySide6 UI.

Uses disposable demo files under ``C:\\junction-demo`` (no personal paths) and a
temporary SQLite database. Run from the project root with a working display:

    .\\.venv\\Scripts\\python.exe tools\\capture_portfolio_screenshots.py
"""

from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fileforge.database.journal import OperationJournal  # noqa: E402
from fileforge.main import create_application, create_main_window  # noqa: E402
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"
DEMO_ROOT = Path(r"C:\junction-demo")


def _write_demo_tree(folder: Path) -> Path:
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "reports").mkdir(parents=True)
    (folder / "photos").mkdir(parents=True)
    (folder / "reports" / "summary.txt").write_text("Junction demo report\n", encoding="utf-8")
    (folder / "reports" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    payload = b"junction-duplicate-bytes"
    (folder / "photos" / "copy-a.bin").write_bytes(payload)
    (folder / "photos" / "copy-b.bin").write_bytes(payload)
    (folder / "photos" / "unique.bin").write_bytes(b"unique-content")
    return folder


def _seed_history(database, demo: Path, dest: Path) -> None:
    journal = OperationJournal(database)
    batch = journal.begin_batch(
        operation_type="organize_move",
        summary="Demo organize",
        source_root=str(demo),
        destination_root=str(dest),
        mode="extension",
    )
    eid = journal.add_entry(
        batch,
        source_path=str(demo / "reports" / "summary.txt"),
        destination_path=str(dest / "txt" / "summary.txt"),
        operation_type="move",
    )
    journal.complete_entry(eid, status="success")
    journal.complete_batch(batch, status="completed", summary="1 moved (demo)")


def _wait_ms(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _run_and_wait(start_fn, signal, timeout_ms: int = 20000) -> bool:
    """Connect first, then start work, so fast workers cannot race the waiter."""
    loop = QEventLoop()
    result = {"ok": False}

    def _ok(*_args: object) -> None:
        result["ok"] = True
        loop.quit()

    signal.connect(_ok)
    QTimer.singleShot(timeout_ms, loop.quit)
    start_fn()
    loop.exec()
    with contextlib.suppress(RuntimeError):
        signal.disconnect(_ok)
    return result["ok"]


def _grab(window, page_id: str, filename: str) -> None:
    window.show_page(page_id)
    window.repaint()
    QApplication.processEvents()
    _wait_ms(250)
    path = SHOTS / filename
    if not window.grab().save(str(path), "PNG"):
        raise RuntimeError(f"Failed to write {path}")
    print(f"Wrote {path}")


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="junction-shots-db-"))
    create_application([])
    window = None
    database = None
    try:
        demo = _write_demo_tree(DEMO_ROOT)
        dest = DEMO_ROOT.parent / "junction-demo-out"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir()

        window, database = create_main_window(tmp / "shots.db")
        window._settings.set(SETTING_CONFIRM_EXIT, "0")
        _seed_history(database, demo, dest)
        window.resize(1366, 768)
        window.show()
        QApplication.processEvents()

        dashboard = window._pages["dashboard"]
        dashboard.refresh_journal_summary()
        _grab(window, "dashboard", "01-dashboard.png")

        scanner = window._pages["scanner"]
        scanner._selected_folder = demo
        scanner.folder_label.setText(str(demo))
        scanner.folder_label.setToolTip(str(demo))
        scanner.start_button.setEnabled(True)
        if not _run_and_wait(scanner._start_scan, scanner._controller.finished):
            raise RuntimeError("Folder Scanner did not finish in time")
        _wait_ms(300)
        _grab(window, "scanner", "02-folder-scanner.png")

        organizer = window._pages["organizer"]
        organizer._source = demo
        organizer._destination = dest
        organizer.source_label.setText(str(demo))
        organizer.destination_label.setText(str(dest))
        organizer.preview_button.setEnabled(True)
        if not _run_and_wait(
            organizer._start_preview, organizer._controller.preview_finished
        ):
            raise RuntimeError("Smart Organizer preview did not finish in time")
        _wait_ms(300)
        _grab(window, "organizer", "03-smart-organizer.png")

        duplicates = window._pages["duplicates"]
        duplicates._folder = demo
        duplicates.folder_label.setText(str(demo))
        duplicates.start_button.setEnabled(True)
        if not _run_and_wait(duplicates._start_scan, duplicates._controller.finished):
            raise RuntimeError("Duplicate Finder did not finish in time")
        _wait_ms(300)
        _grab(window, "duplicates", "04-duplicate-finder.png")

        renamer = window._pages["renamer"]
        renamer._folder = demo
        renamer.folder_label.setText(str(demo))
        renamer.load_button.setEnabled(True)
        renamer.prefix_edit.setText("junction_")
        if not _run_and_wait(
            renamer._start_inventory, renamer._controller.inventory_finished
        ):
            raise RuntimeError("Bulk Renamer inventory did not finish in time")
        for _ in range(100):
            if not renamer._controller.is_active:
                break
            _wait_ms(50)
        renamer._select_all()
        QApplication.processEvents()
        if not _run_and_wait(
            renamer._start_preview, renamer._controller.preview_finished
        ):
            raise RuntimeError("Bulk Renamer preview did not finish in time")
        for _ in range(100):
            if not renamer._controller.is_active:
                break
            _wait_ms(50)
        renamer._reset_splitter_sizes()
        QApplication.processEvents()
        # Taller frame so rules + both table floors fit without crushing panes.
        window.resize(1920, 1080)
        window.show_page("renamer")
        QApplication.processEvents()
        _wait_ms(300)
        _grab(window, "renamer", "05-bulk-renamer.png")
        window.resize(1366, 768)

        history = window._pages["history"]
        history.refresh()
        _wait_ms(1200)
        _grab(window, "history", "06-operation-history.png")

        window.close()
    finally:
        if database is not None:
            database.close()
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(DEMO_ROOT, ignore_errors=True)
        shutil.rmtree(DEMO_ROOT.parent / "junction-demo-out", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
