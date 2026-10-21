"""Startup configuration and high-DPI warning regression tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from fileforge.main import (
    _parse_scale_factor_rounding_policy,
    configure_qt_before_app,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WARNING_SNIPPET = "setHighDpiScaleFactorRoundingPolicy"


def _subprocess_env(**updates: str | None) -> dict[str, str]:
    """Build an env that forces Qt warnings onto stderr for reliable asserts."""
    env = os.environ.copy()
    env["QT_LOGGING_TO_CONSOLE"] = "1"
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    # Avoid inheriting an agent/offscreen platform unless a test sets one.
    env.pop("QT_QPA_PLATFORM", None)
    for key, value in updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def test_parse_scale_factor_rounding_policy_names() -> None:
    assert (
        _parse_scale_factor_rounding_policy("RoundPreferFloor")
        == Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
    )
    assert (
        _parse_scale_factor_rounding_policy("passthrough")
        == Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    assert _parse_scale_factor_rounding_policy("not-a-policy") is None


def test_configure_qt_before_app_consumes_env_policy(monkeypatch) -> None:
    if QGuiApplication.instance() is not None:
        # pytest-qt already created an application; only verify env consumption
        # remains safe (no crash) in that situation.
        monkeypatch.setenv("QT_SCALE_FACTOR_ROUNDING_POLICY", "RoundPreferFloor")
        configure_qt_before_app()
        assert "QT_SCALE_FACTOR_ROUNDING_POLICY" not in os.environ
        return

    monkeypatch.setenv("QT_SCALE_FACTOR_ROUNDING_POLICY", "RoundPreferFloor")
    configure_qt_before_app()
    assert "QT_SCALE_FACTOR_ROUNDING_POLICY" not in os.environ
    assert (
        QGuiApplication.highDpiScaleFactorRoundingPolicy()
        == Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
    )


def test_module_entry_point_no_highdpi_warning_with_rounding_policy_env() -> None:
    """Exercise ``python -m fileforge`` with the env var that triggers QTBUG-132430."""
    env = _subprocess_env(
        QT_SCALE_FACTOR_ROUNDING_POLICY="RoundPreferFloor",
        QT_QPA_PLATFORM="windows",
        FILEFORGE_SMOKE_EXIT="1",
    )
    result = subprocess.run(
        [sys.executable, "-m", "fileforge"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert WARNING_SNIPPET not in combined, combined


def test_startup_warning_still_occurs_without_fileforge_mitigation() -> None:
    """Control: raw QApplication still warns when the env var is left in place."""
    env = _subprocess_env(
        QT_SCALE_FACTOR_ROUNDING_POLICY="RoundPreferFloor",
        QT_QPA_PLATFORM="windows",
    )
    script = """
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication([])
QTimer.singleShot(50, app.quit)
raise SystemExit(app.exec())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert WARNING_SNIPPET in combined


def test_create_application_path_no_highdpi_warning() -> None:
    env = _subprocess_env(
        QT_SCALE_FACTOR_ROUNDING_POLICY="RoundPreferFloor",
        QT_QPA_PLATFORM="windows",
    )
    script = """
from PySide6.QtCore import QTimer
from fileforge.main import create_application, create_main_window
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from pathlib import Path
import tempfile
import os

app = create_application([])
assert "QT_SCALE_FACTOR_ROUNDING_POLICY" not in os.environ
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
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert WARNING_SNIPPET not in combined, combined
