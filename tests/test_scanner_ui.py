"""GUI tests for Folder Scanner page and worker cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fileforge.main import create_main_window
from fileforge.services.scanner import EntryKind, FolderScanner, ScanEntry, ScanStatus
from fileforge.ui.models.scan_table_model import ScanFilterProxyModel, ScanTableModel
from fileforge.ui.pages.scanner_page import ScannerPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    scanner = window._pages["scanner"]
    assert isinstance(scanner, ScannerPage)
    scanner.cancel_active_scan(2000)
    window.close()
    database.close()


def _make_tree(root: Path) -> None:
    (root / "alpha.txt").write_text("a", encoding="utf-8")
    (root / "beta.log").write_text("bbbb", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "gamma.txt").write_text("ccc", encoding="utf-8")


def test_scanner_controls_are_ready(main_window: MainWindow) -> None:
    scanner = main_window._pages["scanner"]
    assert isinstance(scanner, ScannerPage)
    assert scanner.choose_folder_button.isEnabled()
    assert scanner.start_button.isEnabled() is False
    assert scanner.cancel_button.isEnabled() is False


def test_scan_table_filter_and_sort() -> None:
    model = ScanTableModel()
    entries = [
        ScanEntry(
            name="alpha.txt",
            path=Path("alpha.txt"),
            relative_path="alpha.txt",
            extension="txt",
            size_bytes=10,
            modified_at=None,
            parent_directory=".",
            kind=EntryKind.FILE,
        ),
        ScanEntry(
            name="beta.log",
            path=Path("beta.log"),
            relative_path="beta.log",
            extension="log",
            size_bytes=20,
            modified_at=None,
            parent_directory=".",
            kind=EntryKind.FILE,
        ),
        ScanEntry(
            name="sub",
            path=Path("sub"),
            relative_path="sub",
            extension="",
            size_bytes=0,
            modified_at=None,
            parent_directory=".",
            kind=EntryKind.DIRECTORY,
        ),
    ]
    model.set_entries(entries)
    proxy = ScanFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.set_name_query("alpha")
    assert proxy.rowCount() == 1

    proxy.set_name_query("")
    proxy.set_extension_filter("log")
    assert proxy.rowCount() == 1

    proxy.set_extension_filter("__folders__")
    assert proxy.rowCount() == 1

    proxy.set_extension_filter("")
    proxy.sort(3, Qt.SortOrder.DescendingOrder)
    top = proxy.index(0, 0)
    assert proxy.data(top) == "beta.log"


def test_scanner_completes_against_temp_folder(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "sample"
    sample.mkdir()
    _make_tree(sample)

    scanner = main_window._pages["scanner"]
    assert isinstance(scanner, ScannerPage)
    scanner._selected_folder = sample
    scanner.folder_label.setText(str(sample))
    scanner.start_button.setEnabled(True)
    scanner.recursive_check.setChecked(True)

    with qtbot.waitSignal(scanner._controller.finished, timeout=10000) as blocker:
        scanner._start_scan()
    result = blocker.args[0]
    assert result.status in {ScanStatus.COMPLETED, ScanStatus.PARTIAL}
    assert result.file_count == 3
    assert scanner._table_model.rowCount() == result.file_count + result.directory_count

    dashboard = main_window._pages["dashboard"]
    # isVisible() is false while the Dashboard page is not current; isHidden()
    # reflects the local show/hide flag set by set_last_scan_summary.
    assert not dashboard.scan_summary_card.isHidden()
    assert "file" in dashboard.scan_summary_label.text().lower()


def test_scanner_cancellation(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "many"
    sample.mkdir()
    for index in range(200):
        (sample / f"f{index}.txt").write_text("x" * 100, encoding="utf-8")
        (sample / f"d{index}").mkdir()
        (sample / f"d{index}" / "inner.txt").write_text("y", encoding="utf-8")

    scanner = main_window._pages["scanner"]
    assert isinstance(scanner, ScannerPage)
    scanner._selected_folder = sample
    scanner.start_button.setEnabled(True)

    scanner._start_scan()
    assert scanner.is_scanning
    with qtbot.waitSignal(scanner._controller.finished, timeout=10000) as blocker:
        scanner._cancel_scan()
    result = blocker.args[0]
    assert result.status == ScanStatus.CANCELLED
    qtbot.waitUntil(lambda: not scanner.is_scanning, timeout=5000)


def test_worker_cleanup_on_cancel_wait(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "cleanup"
    sample.mkdir()
    for index in range(100):
        (sample / f"n{index}.bin").write_bytes(b"1234")

    scanner = main_window._pages["scanner"]
    assert isinstance(scanner, ScannerPage)
    scanner._selected_folder = sample
    scanner.start_button.setEnabled(True)
    scanner._start_scan()
    assert scanner.cancel_active_scan(5000) is True
    qtbot.waitUntil(lambda: not scanner.is_scanning, timeout=5000)


def test_engine_and_ui_agree_on_counts(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    result = FolderScanner().scan(tmp_path, recursive=True)
    assert result.file_count == 3
    assert result.directory_count == 1
