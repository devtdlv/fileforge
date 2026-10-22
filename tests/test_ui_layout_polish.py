"""Layout and display polish regression checks (Milestone 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fileforge.main import create_main_window
from fileforge.ui.models.history_table_model import HistoryBatchModel, _short_path
from fileforge.ui.pages.settings_page import SETTING_CONFIRM_EXIT
from fileforge.ui.windows.main_window import MainWindow


@pytest.fixture
def main_window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    window, database = create_main_window(tmp_path / "layout-gui.db")
    window._settings.set(SETTING_CONFIRM_EXIT, "0")
    yield window
    for page_id in ("scanner", "organizer", "duplicates", "renamer", "history"):
        page = window._pages[page_id]
        cancel = getattr(page, "cancel_active_work", None) or getattr(
            page, "cancel_active_scan", None
        )
        if callable(cancel):
            cancel(2000)
    window.close()
    database.close()


def test_short_path_keeps_meaningful_tail() -> None:
    long_path = r"C:\Users\demo\Documents\Projects\fileforge\samples\reports\annual.txt"
    short = _short_path(long_path, max_len=40)
    assert short.startswith("…")
    assert "annual.txt" in short
    assert "reports" in short or short.endswith("annual.txt")
    assert _short_path("short.txt") == "short.txt"


def test_renamer_tables_have_usable_min_heights(main_window: MainWindow) -> None:
    page = main_window._pages["renamer"]
    assert page.files_table.minimumHeight() >= 200
    assert page.preview_table.minimumHeight() >= 220
    assert page._splitter.childrenCollapsible() is False
    assert page._splitter.minimumHeight() >= (
        page.files_table.minimumHeight() + page.preview_table.minimumHeight()
    )
    assert page._scroll is not None
    assert page._scroll.widgetResizable() is True


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1280, 720),
        (1366, 768),
        (1600, 900),
        (1920, 1080),
    ],
)
def test_renamer_splitter_keeps_both_tables_usable(
    main_window: MainWindow, width: int, height: int
) -> None:
    """At common sizes both renamer panes keep their floor heights (page may scroll)."""
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from fileforge.services.renamer import RenameItem, RenameItemStatus

    main_window.show()
    main_window.resize(width, height)
    main_window.show_page("renamer")
    page = main_window._pages["renamer"]

    # Simulate a loaded inventory + preview so the splitter is visible.
    demo = Path(r"C:\junction-demo")
    files = [demo / "a.txt", demo / "b.txt", demo / "c.txt"]
    page._folder = demo
    page._file_model.set_files(files, root=demo)
    page._file_model.select_all()
    page._preview_model.set_items(
        [
            RenameItem(
                source=path,
                proposed_name=f"junction_{path.name}",
                destination=path.with_name(f"junction_{path.name}"),
                relative_folder=path.parent.name,
                rule_summary="prefix 'junction_'",
                status=RenameItemStatus.READY,
            )
            for path in files
        ]
    )
    page.empty_state.setVisible(False)
    page._splitter.setVisible(True)
    page._reset_splitter_sizes()
    QApplication.processEvents()
    main_window.repaint()
    QApplication.processEvents()

    assert page.files_table.isVisible()
    assert page.preview_table.isVisible()
    assert page.files_table.height() >= page.files_table.minimumHeight()
    assert page.preview_table.height() >= page.preview_table.minimumHeight()
    assert page._splitter.height() >= page._splitter.minimumHeight()
    # On short windows the page scroll area must be able to reveal both tables.
    content = page._scroll.widget()
    assert content is not None
    if height <= 768:
        assert content.sizeHint().height() >= page._splitter.minimumHeight()
    # Rules + preview actions remain reachable above the tables.
    assert page.preview_button.isVisible()
    assert page.apply_rename_button.isVisible()
    assert page.prefix_edit.isVisible()


def test_history_tables_have_usable_min_heights(main_window: MainWindow) -> None:
    page = main_window._pages["history"]
    assert page.batches_table.minimumHeight() >= 200
    assert page.entries_table.minimumHeight() >= 180
    assert page._splitter.childrenCollapsible() is False
    assert page.undo_button.isEnabled() is False


def test_duplicates_splitter_min_heights(main_window: MainWindow) -> None:
    page = main_window._pages["duplicates"]
    assert page.groups_table.minimumHeight() >= 180
    assert page.members_table.minimumHeight() >= 160
    assert page._results_splitter.childrenCollapsible() is False
    assert page.delete_selected_button.isEnabled() is False


def test_scanner_and_organizer_table_min_heights(main_window: MainWindow) -> None:
    scanner = main_window._pages["scanner"]
    organizer = main_window._pages["organizer"]
    assert scanner.results_table.minimumHeight() >= 220
    assert organizer.results_table.minimumHeight() >= 220


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1280, 720),
        (1366, 768),
        (1600, 900),
        (1920, 1080),
    ],
)
def test_window_resize_keeps_pages_usable(
    main_window: MainWindow, width: int, height: int
) -> None:
    main_window.show()
    main_window.resize(width, height)
    assert main_window.width() == width
    assert main_window.height() == height
    for page_id in main_window.page_ids():
        main_window.show_page(page_id)
        widget = main_window._pages[page_id]
        assert main_window.stack.currentWidget() is widget
        assert widget.minimumWidth() >= 0
        assert widget.sizeHint().width() > 0


def test_keyboard_sidebar_shortcuts_switch_pages(main_window: MainWindow) -> None:
    """Ctrl+N shortcuts are ApplicationShortcuts owned by the sidebar."""
    from PySide6.QtGui import QKeySequence, QShortcut

    by_page = {
        "scanner": "Ctrl+2",
        "organizer": "Ctrl+3",
        "renamer": "Ctrl+5",
        "dashboard": "Ctrl+1",
    }
    for page_id, sequence in by_page.items():
        match = next(
            (
                sc
                for sc in main_window.sidebar.findChildren(QShortcut)
                if QKeySequence(sequence).matches(sc.key())
                == QKeySequence.SequenceMatch.ExactMatch
            ),
            None,
        )
        assert match is not None, f"missing shortcut {sequence}"
        match.activated.emit()
        assert main_window.current_page_id() == page_id


def test_sidebar_lists_smart_organizer(main_window: MainWindow) -> None:
    labels = [
        main_window.sidebar._list.item(row).text()
        for row in range(main_window.sidebar._list.count())
    ]
    assert "Smart Organizer" in labels
    assert "Junction" not in labels  # brand is separate from nav labels


def test_history_batch_model_tooltip_has_full_paths() -> None:
    from fileforge.services.history import BatchSummary

    model = HistoryBatchModel()
    model.set_batches(
        [
            BatchSummary(
                batch_id="abc",
                operation_type="organize_move",
                status="completed",
                summary="ok",
                source_root=r"C:\very\long\source\path\demo",
                destination_root=r"C:\very\long\destination\path\demo",
                mode="extension",
                created_at="2026-01-01T00:00:00+00:00",
                completed_at="2026-01-01T00:00:01+00:00",
                entry_total=1,
                entry_success=1,
                entry_failed=0,
                entry_pending=0,
            )
        ]
    )
    index = model.index(0, 7)
    tip = model.data(index, Qt.ItemDataRole.ToolTipRole)
    assert tip is not None
    assert r"C:\very\long\source\path\demo" in tip
    display = model.data(index, Qt.ItemDataRole.DisplayRole)
    assert display is not None
    assert len(str(display)) <= len(r"C:\very\long\source\path\demo")
