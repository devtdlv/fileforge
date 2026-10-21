"""Primary FileForge application window with sidebar navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from fileforge import __app_name__, __version__
from fileforge.database.connection import DatabaseManager
from fileforge.database.settings_store import SettingsStore
from fileforge.ui.pages.dashboard_page import DashboardPage
from fileforge.ui.pages.duplicates_page import DuplicatesPage
from fileforge.ui.pages.history_page import HistoryPage
from fileforge.ui.pages.organizer_page import OrganizerPage
from fileforge.ui.pages.renamer_page import RenamerPage
from fileforge.ui.pages.scanner_page import ScannerPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT, SettingsPage
from fileforge.ui.styles.theme import APP_STYLESHEET
from fileforge.ui.widgets.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Shell window hosting navigation and milestone-1 content pages."""

    def __init__(
        self,
        database: DatabaseManager,
        settings: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._settings = settings

        self.setWindowTitle(f"{__app_name__}")
        self.setMinimumSize(1024, 640)
        self.resize(1180, 720)
        self.setStyleSheet(APP_STYLESHEET)

        central = QWidget()
        central.setObjectName("ContentHost")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentHost")
        root.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        self._pages: dict[str, QWidget] = {}
        self._register_pages()

        self.sidebar.page_selected.connect(self.show_page)
        self.show_page("dashboard")

        status = QStatusBar()
        status.setObjectName("StatusBar")
        status.showMessage(f"{__app_name__} v{__version__}  |  Ready")
        self.setStatusBar(status)

    def _register_pages(self) -> None:
        dashboard = DashboardPage()
        dashboard.open_scanner_requested.connect(lambda: self.show_page("scanner"))

        pages: list[tuple[str, QWidget]] = [
            ("dashboard", dashboard),
            ("scanner", ScannerPage()),
            ("organizer", OrganizerPage()),
            ("duplicates", DuplicatesPage()),
            ("renamer", RenamerPage()),
            ("history", HistoryPage()),
            ("settings", SettingsPage(self._settings, Path(self._database.path))),
        ]
        for page_id, widget in pages:
            index = self.stack.addWidget(widget)
            widget.setProperty("page_id", page_id)
            widget.setProperty("stack_index", index)
            self._pages[page_id] = widget

    def page_ids(self) -> list[str]:
        """Return registered page identifiers in sidebar order."""
        return self.sidebar.page_ids()

    def current_page_id(self) -> str | None:
        return self.sidebar.current_page_id()

    def show_page(self, page_id: str) -> None:
        """Navigate to a page and keep the sidebar selection in sync."""
        widget = self._pages.get(page_id)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        if self.sidebar.current_page_id() != page_id:
            self.sidebar.select_page(page_id)

        titles = {
            "dashboard": "Dashboard",
            "scanner": "Folder Scanner",
            "organizer": "Organizer",
            "duplicates": "Duplicate Finder",
            "renamer": "Bulk Renamer",
            "history": "Operation History",
            "settings": "Settings",
        }
        page_title = titles.get(page_id, page_id)
        self.setWindowTitle(f"{__app_name__} - {page_title}")
        status = self.statusBar()
        if status is not None:
            status.showMessage(f"{__app_name__} v{__version__}  |  {page_title}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        confirm = self._settings.get(SETTING_CONFIRM_EXIT, "1")
        if confirm == "0":
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Exit FileForge",
            "Close FileForge? No file operations are in progress in this milestone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
