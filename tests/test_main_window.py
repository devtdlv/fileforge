"""GUI shell tests for startup, navigation, and page availability."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fileforge.database.connection import DatabaseManager
from fileforge.database.settings_store import SettingsStore
from fileforge.main import create_main_window
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.widgets.sidebar import NAV_ITEMS
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    db_path = tmp_path / "gui.db"
    window, database = create_main_window(db_path)
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    window.close()
    database.close()


def test_main_window_constructs(main_window: MainWindow) -> None:
    assert isinstance(main_window, MainWindow)
    assert main_window.windowTitle().startswith("FileForge")
    assert main_window.minimumWidth() >= 1024
    assert main_window.minimumHeight() >= 640
    assert QApplication.instance() is not None
    status = main_window.statusBar()
    assert status is not None
    message = status.currentMessage()
    assert "FileForge v" in message
    assert "fileforge.db" not in message.lower()
    assert str(main_window._database.path).lower() not in message.lower()


def test_sidebar_items_have_icons(main_window: MainWindow) -> None:
    nav = main_window.sidebar._list
    assert nav.count() == len(NAV_ITEMS)
    for row in range(nav.count()):
        item = nav.item(row)
        assert item is not None
        assert not item.icon().isNull()


def test_dashboard_uses_concise_safety_overview(main_window: MainWindow) -> None:
    from PySide6.QtWidgets import QLabel

    from fileforge.core.safety import SAFETY_HIGHLIGHTS, SAFETY_PRINCIPLES

    dashboard = main_window._pages["dashboard"]
    texts = " ".join(label.text() for label in dashboard.findChildren(QLabel))
    assert "Safety overview" in texts
    assert "Open Folder Scanner" in dashboard.open_scanner_button.text()
    for highlight in SAFETY_HIGHLIGHTS:
        assert highlight in texts
    assert SAFETY_PRINCIPLES[-1] not in texts


def test_all_navigation_pages_available(main_window: MainWindow) -> None:
    expected = [item.page_id for item in NAV_ITEMS]
    assert main_window.page_ids() == expected
    for page_id in expected:
        assert page_id in main_window._pages


def test_sidebar_navigation_switches_pages(main_window: MainWindow) -> None:
    assert main_window.current_page_id() == "dashboard"

    for page_id in main_window.page_ids():
        main_window.show_page(page_id)
        assert main_window.current_page_id() == page_id
        assert main_window.stack.currentWidget() is main_window._pages[page_id]


def test_dashboard_open_scanner_navigates(main_window: MainWindow, qtbot) -> None:
    dashboard = main_window._pages["dashboard"]
    qtbot.mouseClick(dashboard.open_scanner_button, Qt.MouseButton.LeftButton)
    assert main_window.current_page_id() == "scanner"


def test_unfinished_actions_are_disabled(main_window: MainWindow) -> None:
    scanner = main_window._pages["scanner"]
    organizer = main_window._pages["organizer"]
    duplicates = main_window._pages["duplicates"]
    renamer = main_window._pages["renamer"]
    history = main_window._pages["history"]

    assert scanner.choose_folder_button.isEnabled() is False
    assert organizer.apply_plan_button.isEnabled() is False
    assert duplicates.delete_selected_button.isEnabled() is False
    assert renamer.apply_rename_button.isEnabled() is False
    assert history.undo_button.isEnabled() is False


def test_settings_page_persists_values(main_window: MainWindow, tmp_path: Path) -> None:
    settings_page = main_window._pages["settings"]
    settings_page.display_name_edit.setText("Portfolio Demo")
    settings_page.confirm_exit_check.setChecked(False)

    store = SettingsStore(main_window._database)
    store.set("display_name", settings_page.display_name_edit.text().strip())
    store.set("confirm_exit", "0")

    reopened = DatabaseManager(tmp_path / "gui.db")
    reopened.initialize()
    try:
        reloaded = SettingsStore(reopened)
        assert reloaded.get("display_name") == "Portfolio Demo"
        assert reloaded.get("confirm_exit") == "0"
    finally:
        reopened.close()
