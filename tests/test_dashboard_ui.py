"""Dashboard journal summaries and empty-state behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from fileforge import __app_name__
from fileforge.database.journal import OperationJournal
from fileforge.main import create_main_window
from fileforge.ui.pages.dashboard_page import DashboardPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "dashboard-gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    window.close()
    database.close()


def test_dashboard_brands_as_junction(main_window: MainWindow) -> None:
    assert __app_name__ == "Junction"
    dashboard = main_window._pages["dashboard"]
    assert isinstance(dashboard, DashboardPage)
    titles = [
        label.text()
        for label in dashboard.findChildren(QLabel)
        if label.objectName() == "PageTitle"
    ]
    assert "Junction" in titles
    brand_texts = [
        label.text()
        for label in main_window.sidebar.findChildren(QLabel)
        if label.objectName() == "SidebarBrand"
    ]
    assert brand_texts == ["Junction"]


def test_dashboard_empty_journal_state(main_window: MainWindow) -> None:
    dashboard = main_window._pages["dashboard"]
    assert isinstance(dashboard, DashboardPage)
    dashboard.refresh_journal_summary()
    assert "No Organizer or Bulk Renamer batches" in dashboard.recent_label.text()
    total = dashboard.stat_total.findChild(QLabel, "StatValue")
    assert total is not None
    assert total.text() == "0"


def test_dashboard_shows_real_batch_stats(main_window: MainWindow) -> None:
    journal = OperationJournal(main_window._database)
    batch = journal.begin_batch(
        operation_type="organize_move",
        summary="Organize demo",
        source_root=r"C:\demo\src",
        destination_root=r"C:\demo\dst",
        mode="extension",
    )
    eid = journal.add_entry(
        batch,
        source_path=r"C:\demo\src\a.txt",
        destination_path=r"C:\demo\dst\txt\a.txt",
        operation_type="move",
    )
    journal.complete_entry(eid, status="success")
    journal.complete_batch(batch, status="completed", summary="1 moved")

    failed = journal.begin_batch(
        operation_type="bulk_rename",
        summary="Rename demo",
        source_root=r"C:\demo\photos",
        destination_root=r"C:\demo\photos",
        mode="prefix",
    )
    journal.complete_batch(failed, status="failed", summary="failed")

    dashboard = main_window._pages["dashboard"]
    assert isinstance(dashboard, DashboardPage)
    dashboard.refresh_journal_summary()

    total = dashboard.stat_total.findChild(QLabel, "StatValue")
    completed = dashboard.stat_completed.findChild(QLabel, "StatValue")
    attention = dashboard.stat_attention.findChild(QLabel, "StatValue")
    assert total is not None and total.text() == "2"
    assert completed is not None and completed.text() == "1"
    assert attention is not None and attention.text() == "1"
    text = dashboard.recent_label.text()
    assert "Organizer" in text
    assert "Bulk Renamer" in text
    assert "Completed" in text or "Failed" in text
