"""GUI tests for Operation History page."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fileforge.database.journal import OperationJournal
from fileforge.main import create_main_window
from fileforge.services.history import HistoryOperationType
from fileforge.ui.pages.history_page import HistoryPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "history-gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    history = window._pages["history"]
    assert isinstance(history, HistoryPage)
    history.cancel_active_work(3000)
    window.close()
    database.close()


def _seed(window: MainWindow) -> None:
    journal = OperationJournal(window._database)
    batch = journal.begin_batch(
        operation_type="organize_move",
        summary="Organize demo",
        source_root=r"C:\demo\src",
        destination_root=r"C:\demo\dst",
        mode="extension",
    )
    eid = journal.add_entry(
        batch,
        source_path=r"C:\demo\src\report.txt",
        destination_path=r"C:\demo\dst\txt\report.txt",
        operation_type="move",
    )
    journal.complete_entry(eid, status="success")
    journal.complete_batch(batch, status="completed", summary="1 moved")

    batch2 = journal.begin_batch(
        operation_type="bulk_rename",
        summary="Rename demo",
        source_root=r"C:\demo\photos",
        destination_root=r"C:\demo\photos",
        mode="prefix",
    )
    eid2 = journal.add_entry(
        batch2,
        source_path=r"C:\demo\photos\IMG_001.JPG",
        destination_path=r"C:\demo\photos\holiday_IMG_001.JPG",
        operation_type="rename",
    )
    journal.complete_entry(eid2, status="failed", error_details="Destination exists")
    journal.complete_batch(batch2, status="failed", summary="1 failed")


def test_history_navigation_and_empty_state(main_window: MainWindow, qtbot) -> None:
    main_window.show_page("history")
    assert main_window.current_page_id() == "history"
    page = main_window._pages["history"]
    assert isinstance(page, HistoryPage)
    assert page.undo_button.isEnabled() is False
    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page.refresh()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page.empty_state.isVisible() or page._batch_model.rowCount() == 0


def test_history_populated_selection_and_details(
    main_window: MainWindow, qtbot
) -> None:
    _seed(main_window)
    page = main_window._pages["history"]
    assert isinstance(page, HistoryPage)
    main_window.show_page("history")
    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page.refresh()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page._batch_model.rowCount() == 2
    assert "Completed: 1" in page.summary_label.text()
    assert "Failed: 1" in page.summary_label.text()

    # Selecting a row loads entries (auto-select may already have started).
    page.batches_table.selectRow(0)
    qtbot.waitUntil(lambda: page._entry_model.rowCount() >= 1, timeout=10000)
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    entry = page._entry_model._entries[0]
    assert entry.source_path
    tip = page._entry_model.data(
        page._entry_model.index(0, 0), Qt.ItemDataRole.ToolTipRole
    )
    assert "Source:" in str(tip)
    assert r"C:\demo" in str(tip) or "demo" in str(tip).lower()


def test_history_filter_search_and_refresh(main_window: MainWindow, qtbot) -> None:
    _seed(main_window)
    page = main_window._pages["history"]
    assert isinstance(page, HistoryPage)
    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page.refresh()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)

    page.search_edit.setText("IMG_001")
    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page._on_filters_changed()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page._batch_model.rowCount() == 1
    assert page._batch_model.batch_at(0).operation_type == "bulk_rename"

    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page.type_combo.setCurrentIndex(
            page.type_combo.findData(HistoryOperationType.ORGANIZE_MOVE)
        )
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    # Organizer filter + IMG_001 search → no match
    assert page._batch_model.rowCount() == 0

    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page._clear_filters()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page._batch_model.rowCount() == 2


def test_history_no_match_state(main_window: MainWindow, qtbot) -> None:
    _seed(main_window)
    page = main_window._pages["history"]
    assert isinstance(page, HistoryPage)
    page.search_edit.setText("definitely-not-in-journal-xyz")
    with qtbot.waitSignal(page._controller.list_finished, timeout=10000):
        page._on_filters_changed()
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
    assert page._batch_model.rowCount() == 0
    # isVisible() is false when the page itself is not the current stack page;
    # isHidden() reflects the local show/hide flag set by the empty-state logic.
    assert not page.empty_state.isHidden()


def test_history_worker_cleanup(main_window: MainWindow, qtbot) -> None:
    _seed(main_window)
    page = main_window._pages["history"]
    assert isinstance(page, HistoryPage)
    page.refresh()
    qtbot.waitUntil(lambda: page.is_busy or page._has_loaded_once, timeout=5000)
    assert page.cancel_active_work(8000) is True
    qtbot.waitUntil(lambda: not page.is_busy, timeout=5000)
