"""GUI tests for Duplicate Finder page and worker cleanup."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from fileforge.main import create_main_window
from fileforge.services.duplicates import (
    DuplicateFile,
    DuplicateGroup,
    DuplicateStatus,
)
from fileforge.ui.models.duplicate_table_model import (
    DuplicateGroupFilterProxy,
    DuplicateGroupModel,
    DuplicateMemberModel,
)
from fileforge.ui.pages.duplicates_page import DuplicatesPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "dup-gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    duplicates = window._pages["duplicates"]
    assert isinstance(duplicates, DuplicatesPage)
    duplicates.cancel_active_scan(2000)
    window.close()
    database.close()


def _sample_tree(root: Path) -> None:
    """Create true duplicates, same-size false positives, unique, and empty files."""
    same = b"identical-content-payload"
    (root / "alpha.dat").write_bytes(same)
    (root / "beta.dat").write_bytes(same)
    (root / "same_size_a.bin").write_bytes(b"AAAA")
    (root / "same_size_b.bin").write_bytes(b"BBBB")
    (root / "unique.txt").write_text("only-once", encoding="utf-8")
    (root / "empty_one").write_bytes(b"")
    (root / "empty_two").write_bytes(b"")


def test_duplicates_page_controls_ready(main_window: MainWindow) -> None:
    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    assert page.choose_folder_button.isEnabled()
    assert page.start_button.isEnabled() is False
    assert page.cancel_button.isEnabled() is False
    assert page.delete_selected_button.isEnabled() is False
    main_window.show_page("duplicates")
    assert main_window.current_page_id() == "duplicates"


def test_group_model_filter_and_members() -> None:
    content = b"xyz"
    digest = hashlib.sha256(content).hexdigest()
    group = DuplicateGroup(
        size_bytes=len(content),
        sha256=digest,
        files=[
            DuplicateFile(
                path=Path(r"C:\tmp\one.txt"),
                relative_path="one.txt",
                size_bytes=len(content),
                device=1,
                inode=10,
            ),
            DuplicateFile(
                path=Path(r"C:\tmp\nested\two.txt"),
                relative_path="nested/two.txt",
                size_bytes=len(content),
                device=1,
                inode=11,
            ),
        ],
    )
    model = DuplicateGroupModel()
    model.set_groups([group])
    proxy = DuplicateGroupFilterProxy()
    proxy.setSourceModel(model)
    assert proxy.rowCount() == 1

    proxy.set_query("nested")
    assert proxy.rowCount() == 1
    proxy.set_query("no-such-path")
    assert proxy.rowCount() == 0
    proxy.set_query(digest[:8])
    assert proxy.rowCount() == 1

    members = DuplicateMemberModel()
    members.set_files(group.files)
    assert members.rowCount() == 2
    assert members.data(members.index(0, 0)) == "one.txt"


def test_duplicate_scan_completes(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "sample"
    sample.mkdir()
    _sample_tree(sample)

    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    page._folder = sample
    page.folder_label.setText(str(sample))
    page.start_button.setEnabled(True)
    page.recursive_check.setChecked(True)

    with qtbot.waitSignal(page._controller.finished, timeout=15000) as blocker:
        page._start_scan()
    result = blocker.args[0]
    assert result.status in {
        DuplicateStatus.COMPLETED,
        DuplicateStatus.PARTIAL,
        DuplicateStatus.EMPTY,
    }
    # True duplicates (alpha/beta) + empty pair → 2 groups
    assert result.group_count == 2
    assert page._group_model.rowCount() == 2
    assert page.delete_selected_button.isEnabled() is False

    savings = sum(g.potential_savings_bytes for g in result.groups)
    assert savings == len(b"identical-content-payload")  # empty savings are 0
    assert "Theoretical potential savings" in page.summary_label.text()
    qtbot.waitUntil(lambda: not page.is_scanning, timeout=5000)


def test_duplicate_scan_cancellation(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "many"
    sample.mkdir()
    payload = b"X" * 20_000
    for index in range(40):
        (sample / f"dup_{index}.bin").write_bytes(payload)

    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    page._folder = sample
    page.start_button.setEnabled(True)
    page._start_scan()
    assert page.is_scanning
    with qtbot.waitSignal(page._controller.finished, timeout=15000) as blocker:
        page._cancel_scan()
    result = blocker.args[0]
    assert result.status == DuplicateStatus.CANCELLED
    qtbot.waitUntil(lambda: not page.is_scanning, timeout=5000)


def test_duplicate_worker_cleanup(main_window: MainWindow, tmp_path: Path, qtbot) -> None:
    sample = tmp_path / "cleanup"
    sample.mkdir()
    payload = b"Y" * 8_000
    for index in range(30):
        (sample / f"n{index}.bin").write_bytes(payload)

    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    page._folder = sample
    page.start_button.setEnabled(True)
    page._start_scan()
    assert page.cancel_active_scan(8000) is True
    qtbot.waitUntil(lambda: not page.is_scanning, timeout=5000)


def test_no_fake_results_on_empty_page(main_window: MainWindow) -> None:
    page = main_window._pages["duplicates"]
    assert isinstance(page, DuplicatesPage)
    assert page._group_model.rowCount() == 0
    assert page.empty_state.isVisible() or not page._results_splitter.isVisible()
