"""Startup configuration and high-DPI warning regression tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from fileforge.main import configure_qt_before_app


def test_configure_qt_before_app_sets_passthrough_policy() -> None:
    """When no QGuiApplication exists yet, the policy can be configured.

    pytest-qt usually creates a QApplication before tests run, so this assertion
    only validates the helper when the instance is still absent. The subprocess
    test below covers the real startup path.
    """
    if QGuiApplication.instance() is not None:
        configure_qt_before_app()
        return

    configure_qt_before_app()
    assert (
        QGuiApplication.highDpiScaleFactorRoundingPolicy()
        == Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def test_startup_emits_no_highdpi_warning() -> None:
    """Launch a fresh interpreter so QApplication is created by FileForge."""
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(project_root / "src") + os.pathsep + env.get("PYTHONPATH", "")

    script = """
from PySide6.QtCore import QTimer
from fileforge.main import create_application, create_main_window
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from pathlib import Path
import tempfile

app = create_application([])
with tempfile.TemporaryDirectory() as tmp:
    window, database = create_main_window(Path(tmp) / "startup.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    window.show()
    for page_id in window.page_ids():
        window.show_page(page_id)
    QTimer.singleShot(50, app.quit)
    code = app.exec()
    database.close()
raise SystemExit(code)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "setHighDpiScaleFactorRoundingPolicy" not in combined
