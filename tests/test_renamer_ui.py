"""GUI tests for Bulk Renamer and Duplicate Finder messaging refinements."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from fileforge.main import create_main_window
from fileforge.services.renamer import RenamePlanStatus
from fileforge.ui.pages.duplicates_page import DuplicatesPage
from fileforge.ui.pages.renamer_page import RenamerPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "renamer-gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    renamer = window._pages["renamer"]
    assert isinstance(renamer, RenamerPage)
    renamer.cancel_active_work(2000)
    duplicates = window._pages["duplicates"]
    assert isinstance(duplicates, DuplicatesPage)
    duplicates.cancel_active_scan(2000)
    window.close()
    database.close()


def _sample_tree(root: Path) -> None:
    (root / "IMG_001.JPG").write_bytes(b"img1")
    (root / "IMG_002.JPG").write_bytes(b"img2")
    (root / "report.txt").write_text("report", encoding="utf-8")
    (root / "notes.md").write_text("notes", encoding="utf-8")
    (root / "archive.zip").write_bytes(b"PK")
    nested = root / "nested"
    nested.mkdir()
    (nested / "IMG_003.JPG").write_bytes(b"img3")


def test_renamer_page_navigation_and_controls(main_window: MainWindow) -> None:
    main_window.show_page("renamer")
    assert main_window.current_page_id() == "renamer"
    page = main_window._pages["renamer"]
    assert isinstance(page, RenamerPage)
    assert page.apply_rename_button.isEnabled() is False
    assert page.preview_button.isEnabled() is False
    assert page.load_button.isEnabled() is False


def test_renamer_load_select_preview_apply(
    main_window: MainWindow, tmp_path: Path, qtbot, monkeypatch
) -> None:
    sample = tmp_path / "FileForge-Renamer-Test"
    sample.mkdir()
    _sample_tree(sample)

    page = main_window._pages["renamer"]
    assert isinstance(page, RenamerPage)
    page._folder = sample
    page.folder_label.setText(str(sample))
    page.load_button.setEnabled(True)
    page.recursive_check.setChecked(True)

    with qtbot.waitSignal(page._controller.inventory_finished, timeout=15000):
        page._start_inventory()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page._file_model.rowCount() == 6
    assert page._file_model.selected_count() == 6

    page.prefix_edit.setText("holiday_")
    page.search_edit.setText("IMG")
    page.replace_edit.setText("PHOTO")

    with qtbot.waitSignal(page._controller.preview_finished, timeout=15000) as blocker:
        page._start_preview()
    plan = blocker.args[0]
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert plan.status == RenamePlanStatus.READY
    assert page.apply_rename_button.isEnabled()
    # Preview must not modify files
    assert (sample / "IMG_001.JPG").exists()

    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    with qtbot.waitSignal(page._controller.execute_finished, timeout=20000) as blocker:
        page._confirm_and_apply()
    result = blocker.args[0]
    assert result.status == RenamePlanStatus.COMPLETED
    # Apply may trigger an inventory reload; wait until fully idle.
    qtbot.waitUntil(lambda: not page.is_busy, timeout=15000)
    assert (sample / "holiday_PHOTO_001.JPG").exists()
    assert (sample / "holiday_PHOTO_001.JPG").read_bytes() == b"img1"
    assert not (sample / "IMG_001.JPG").exists()


def test_renamer_worker_cleanup(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "cleanup"
    sample.mkdir()
    for index in range(20):
        (sample / f"f{index}.txt").write_text("x", encoding="utf-8")
    page = main_window._pages["renamer"]
    assert isinstance(page, RenamerPage)
    page._folder = sample
    page.load_button.setEnabled(True)
    page._start_inventory()
    assert page.cancel_active_work(8000) is True
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)


def test_duplicate_finder_completion_messaging_not_redundant(
    main_window: MainWindow, tmp_path: Path, qtbot
) -> None:
    sample = tmp_path / "dup-msg"
    sample.mkdir()
    same = b"dup-bytes"
    (sample / "a.bin").write_bytes(same)
    (sample / "b.bin").write_bytes(same)

    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    # Subtitle should wrap without a fixed clipping height
    header = page.layout().itemAt(0).widget()
    assert header is not None
    subtitle = header._subtitle
    assert subtitle.wordWrap() is True
    assert subtitle.sizePolicy().verticalPolicy().name in {
        "MinimumExpanding",
        "Preferred",
        "Minimum",
    }

    page._folder = sample
    page.start_button.setEnabled(True)
    with qtbot.waitSignal(page._controller.finished, timeout=15000):
        page._start_scan()
    qtbot.waitUntil(lambda: not page.is_scanning, timeout=5000)

    status = page.status_label.text()
    summary = page.summary_label.text()
    assert status.startswith("Scan") or status.startswith("No duplicates")
    assert "Files scanned:" in summary
    # Completion sentence must not be repeated at the start of the stats line.
    assert not summary.startswith(status)
    assert "Found" not in summary.split("|")[0] or "Files scanned" in summary
