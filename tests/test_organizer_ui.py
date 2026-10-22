"""GUI tests for the Organizer page."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QMessageBox

from fileforge.main import create_main_window
from fileforge.services.organizer import OrganizeMode, PlanStatus
from fileforge.ui.pages.organizer_page import OrganizerPage
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    organizer = window._pages["organizer"]
    assert isinstance(organizer, OrganizerPage)
    organizer.cancel_active_work(5000)
    window.close()
    database.close()


def test_organizer_requires_folders_before_preview(main_window: MainWindow) -> None:
    organizer = main_window._pages["organizer"]
    assert isinstance(organizer, OrganizerPage)
    assert organizer.preview_button.isEnabled() is False
    assert organizer.apply_plan_button.isEnabled() is False


def test_organizer_preview_and_apply_flow(
    main_window: MainWindow, tmp_path: Path, qtbot, monkeypatch
) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "photo.jpg").write_bytes(b"img")
    (source / "notes.txt").write_text("text", encoding="utf-8")

    organizer = main_window._pages["organizer"]
    assert isinstance(organizer, OrganizerPage)
    organizer._source = source
    organizer._destination = dest
    organizer.source_label.setText(str(source))
    organizer.destination_label.setText(str(dest))
    organizer.preview_button.setEnabled(True)
    organizer.mode_combo.setCurrentIndex(1)  # category
    assert organizer._selected_mode() is OrganizeMode.CATEGORY

    with qtbot.waitSignal(organizer._controller.preview_finished, timeout=10000):
        organizer._start_preview()
    qtbot.waitUntil(lambda: not organizer.is_busy, timeout=5000)
    assert organizer._plan is not None
    assert organizer._plan.status == PlanStatus.READY
    assert organizer.apply_plan_button.isEnabled() is True
    assert organizer._table_model.rowCount() >= 2

    # Preview shows relative paths; absolute paths remain on the plan items.
    source_display = organizer._table_model.data(
        organizer._table_model.index(0, 1), Qt.ItemDataRole.DisplayRole
    )
    source_absolute = organizer._table_model.data(
        organizer._table_model.index(0, 1), Qt.ItemDataRole.UserRole
    )
    assert "C:" not in str(source_display)
    assert Path(str(source_absolute)).is_absolute()
    header = organizer.results_table.horizontalHeader()
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    with qtbot.waitSignal(organizer._controller.execute_finished, timeout=10000):
        organizer._confirm_and_apply()
    qtbot.waitUntil(lambda: not organizer.is_busy, timeout=5000)

    assert not (source / "photo.jpg").exists()
    assert (dest / "Images" / "photo.jpg").exists()
    assert (dest / "Documents" / "notes.txt").exists()
    assert organizer.apply_plan_button.isEnabled() is False


def test_organizer_apply_requires_confirmation(
    main_window: MainWindow, tmp_path: Path, qtbot, monkeypatch
) -> None:
    source = tmp_path / "src"
    dest = tmp_path / "dst"
    source.mkdir()
    dest.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")

    organizer = main_window._pages["organizer"]
    assert isinstance(organizer, OrganizerPage)
    organizer._source = source
    organizer._destination = dest
    organizer.preview_button.setEnabled(True)

    with qtbot.waitSignal(organizer._controller.preview_finished, timeout=10000):
        organizer._start_preview()
    qtbot.waitUntil(lambda: not organizer.is_busy, timeout=5000)
    assert organizer.apply_plan_button.isEnabled()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    organizer._confirm_and_apply()
    assert (source / "a.txt").exists()
    assert list(dest.rglob("*")) == [] or not any(p.is_file() for p in dest.rglob("*"))
