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
    """Shell window hosting navigation and application pages."""

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

        scanner = ScannerPage()
        scanner.scan_summary_changed.connect(dashboard.set_last_scan_summary)
        scanner.scan_summary_changed.connect(self._on_scan_summary)

        pages: list[tuple[str, QWidget]] = [
            ("dashboard", dashboard),
            ("scanner", scanner),
            ("organizer", OrganizerPage(self._database)),
            ("duplicates", DuplicatesPage()),
            ("renamer", RenamerPage(self._database)),
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

    def _on_scan_summary(self, summary: str) -> None:
        status = self.statusBar()
        if status is None:
            return
        if summary.strip():
            status.showMessage(f"{__app_name__} v{__version__}  |  {summary}")
        elif self.current_page_id() == "scanner":
            status.showMessage(f"{__app_name__} v{__version__}  |  Folder Scanner")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        scanner = self._pages.get("scanner")
        if isinstance(scanner, ScannerPage) and scanner.is_scanning:
            answer = QMessageBox.question(
                self,
                "Scan in progress",
                "A folder scan is still running. Cancel it and exit FileForge?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            scanner.cancel_active_scan()

        organizer = self._pages.get("organizer")
        if isinstance(organizer, OrganizerPage) and organizer.is_busy:
            answer = QMessageBox.question(
                self,
                "Organization in progress",
                "An organization preview or apply is still running. "
                "Cancel it and exit FileForge?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            organizer.cancel_active_work()

        duplicates = self._pages.get("duplicates")
        if isinstance(duplicates, DuplicatesPage) and duplicates.is_scanning:
            answer = QMessageBox.question(
                self,
                "Duplicate scan in progress",
                "A duplicate scan is still running. Cancel it and exit FileForge?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            duplicates.cancel_active_scan()

        renamer = self._pages.get("renamer")
        if isinstance(renamer, RenamerPage) and renamer.is_busy:
            answer = QMessageBox.question(
                self,
                "Rename in progress",
                "A bulk rename load, preview, or apply is still running. "
                "Cancel it and exit FileForge?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            renamer.cancel_active_work()

        confirm = self._settings.get(SETTING_CONFIRM_EXIT, "1")
        if confirm == "0":
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Exit FileForge",
            "Close FileForge?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
