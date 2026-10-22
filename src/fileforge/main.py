"""Application entry point for Junction (``python -m fileforge``)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from fileforge import __app_name__, __version__
from fileforge.core.resources import application_icon_path
from fileforge.database.connection import DatabaseError, DatabaseManager
from fileforge.database.settings_store import SettingsStore
from fileforge.ui.windows.main_window import MainWindow

_POLICY_BY_NAME: dict[str, Qt.HighDpiScaleFactorRoundingPolicy] = {
    "round": Qt.HighDpiScaleFactorRoundingPolicy.Round,
    "ceil": Qt.HighDpiScaleFactorRoundingPolicy.Ceil,
    "floor": Qt.HighDpiScaleFactorRoundingPolicy.Floor,
    "roundpreferfloor": Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor,
    "passthrough": Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
}


def _parse_scale_factor_rounding_policy(
    value: str,
) -> Qt.HighDpiScaleFactorRoundingPolicy | None:
    """Map a QT_SCALE_FACTOR_ROUNDING_POLICY value to a Qt enum member."""
    return _POLICY_BY_NAME.get(value.strip().lower())


def configure_qt_before_app() -> None:
    """Prepare Qt settings that must precede QGuiApplication construction.

    Qt 6.9 can emit:

        setHighDpiScaleFactorRoundingPolicy must be called before creating
        the QGuiApplication instance

    when ``QT_SCALE_FACTOR_ROUNDING_POLICY`` is set in the process environment.
    Qt applies that variable by calling ``setHighDpiScaleFactorRoundingPolicy``
    after the application object already exists (QTBUG-132430, fixed upstream
    in Qt 6.10). Cursor and other host environments often set this variable.

    Junction therefore:
    1. Reads and removes ``QT_SCALE_FACTOR_ROUNDING_POLICY`` from ``os.environ``
    2. Applies a recognized policy via the public API before constructing
       ``QApplication``

    Calling ``setHighDpiScaleFactorRoundingPolicy`` alone does not prevent the
    warning while the environment variable remains set.
    """
    # Always remove the variable first. Leaving it set makes Qt 6.9 warn during
    # QApplication construction even if the API was already called.
    raw_policy = os.environ.pop("QT_SCALE_FACTOR_ROUNDING_POLICY", None)

    if QGuiApplication.instance() is not None:
        # Too late to change the policy safely; avoid calling the setter.
        return

    if raw_policy is None:
        return

    policy = _parse_scale_factor_rounding_policy(raw_policy)
    if policy is not None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(policy)


def create_application(argv: list[str] | None = None) -> QApplication:
    """Create the Qt application instance with basic metadata."""
    configure_qt_before_app()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__app_name__)
    icon = _load_application_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    return app


def _load_application_icon() -> QIcon | None:
    """Load the Junction icon from package resources when present."""
    path = application_icon_path()
    if not path.is_file():
        return None
    icon = QIcon(str(path))
    if icon.isNull():
        return None
    return icon


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
    """Launch Junction and return the Qt exit code."""
    app = create_application(argv)
    database: DatabaseManager | None = None
    try:
        window, database = create_main_window()
    except DatabaseError as exc:
        QMessageBox.critical(
            None,
            f"{__app_name__} could not start",
            (
                f"{__app_name__} could not initialize its local database.\n\n"
                f"{exc}\n\n"
                "Check that your user application-data folder is writable, "
                "then try again."
            ),
        )
        return 1

    window.show()

    # Optional smoke-exit for automated verification of ``python -m fileforge``.
    if os.environ.get("FILEFORGE_SMOKE_EXIT") == "1":
        from PySide6.QtCore import QTimer

        from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT

        # Avoid a blocking exit-confirmation dialog in non-interactive smoke runs.
        SettingsStore(database).set(SETTING_CONFIRM_EXIT, "0")
        QTimer.singleShot(100, app.quit)

    try:
        return app.exec()
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    raise SystemExit(run())
