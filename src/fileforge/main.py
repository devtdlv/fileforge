"""Application entry point for FileForge."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from fileforge import __app_name__, __version__
from fileforge.database.connection import DatabaseError, DatabaseManager
from fileforge.database.settings_store import SettingsStore
from fileforge.ui.windows.main_window import MainWindow


def configure_qt_before_app() -> None:
    """Apply Qt settings that must precede QGuiApplication construction.

    On Windows, Qt may emit a high-DPI rounding-policy warning if this is not
    configured before the application instance exists.
    """
    if QGuiApplication.instance() is not None:
        return
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create the Qt application instance with basic metadata."""
    configure_qt_before_app()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__app_name__)
    return app


def create_main_window(
    database_path: Path | str | None = None,
) -> tuple[MainWindow, DatabaseManager]:
    """Initialize the database and construct the main window.

    Raises:
        DatabaseError: If the database cannot be initialized.
    """
    database = DatabaseManager(database_path)
    database.initialize()
    settings = SettingsStore(database)
    window = MainWindow(database=database, settings=settings)
    return window, database


def run(argv: list[str] | None = None) -> int:
    """Launch FileForge and return the Qt exit code."""
    app = create_application(argv)
    database: DatabaseManager | None = None
    try:
        window, database = create_main_window()
    except DatabaseError as exc:
        QMessageBox.critical(
            None,
            f"{__app_name__} could not start",
            (
                "FileForge could not initialize its local database.\n\n"
                f"{exc}\n\n"
                "Check that your user application-data folder is writable, "
                "then try again."
            ),
        )
        return 1

    window.show()
    try:
        return app.exec()
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(run())
