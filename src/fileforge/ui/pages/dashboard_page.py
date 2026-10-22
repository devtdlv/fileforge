"""Dashboard: overview, feature shortcuts, and journal-backed recent activity."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from fileforge.core.safety import SAFETY_HIGHLIGHTS
from fileforge.database.connection import DatabaseManager
from fileforge.services.history import (
    HistoryFilters,
    HistoryQueryService,
    label_batch_status,
    label_operation_type,
)
from fileforge.ui.models.history_table_model import _format_local_timestamp
from fileforge.ui.widgets.page_header import PageHeader


class DashboardPage(QWidget):
    """Landing page with shortcuts and real journal summaries."""

    open_scanner_requested = Signal()
    open_organizer_requested = Signal()
    open_duplicates_requested = Signal()
    open_renamer_requested = Signal()
    open_history_requested = Signal()

    def __init__(
        self,
        database: DatabaseManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._loaded_once = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Junction",
                "A local-first Windows toolkit for scanning folders, organizing "
                "files, finding duplicates, and renaming in bulk. Previews come "
                "first; confirmed changes are journaled on this machine only.",
            )
        )

        # --- Stats ---
        stats = QFrame()
        stats.setObjectName("SectionCard")
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(18, 16, 18, 16)
        stats_layout.setSpacing(12)

        self.stat_total = self._make_stat("0", "Batches recorded")
        self.stat_completed = self._make_stat("0", "Completed")
        self.stat_attention = self._make_stat("0", "Failed / partial")
        self.stat_recent = self._make_stat("—", "Most recent")
        for card in (
            self.stat_total,
            self.stat_completed,
            self.stat_attention,
            self.stat_recent,
        ):
            stats_layout.addWidget(card, stretch=1)
        layout.addWidget(stats)

        # --- Shortcuts ---
        shortcuts_kicker = QLabel("Feature shortcuts")
        shortcuts_kicker.setObjectName("SectionKicker")
        layout.addWidget(shortcuts_kicker)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.open_scanner_button = self._shortcut_button(
            "Folder Scanner",
            "Read-only inventory of a folder you choose.",
            self.open_scanner_requested,
        )
        self.open_organizer_button = self._shortcut_button(
            "Smart Organizer",
            "Preview-first moves by extension, category, or date.",
            self.open_organizer_requested,
        )
        self.open_duplicates_button = self._shortcut_button(
            "Duplicate Finder",
            "Find identical content with size filtering and SHA-256.",
            self.open_duplicates_requested,
        )
        self.open_renamer_button = self._shortcut_button(
            "Bulk Renamer",
            "Rule-based renames with preview and collision checks.",
            self.open_renamer_requested,
        )
        self.open_history_button = self._shortcut_button(
            "Operation History",
            "Browse journaled Organizer and Renamer batches.",
            self.open_history_requested,
        )

        grid.addWidget(self.open_scanner_button, 0, 0)
        grid.addWidget(self.open_organizer_button, 0, 1)
        grid.addWidget(self.open_duplicates_button, 1, 0)
        grid.addWidget(self.open_renamer_button, 1, 1)
        grid.addWidget(self.open_history_button, 2, 0, 1, 2)
        layout.addLayout(grid)

        # --- Session scan summary ---
        self.scan_summary_card = QFrame()
        self.scan_summary_card.setObjectName("SectionCard")
        self.scan_summary_card.setVisible(False)
        summary_layout = QVBoxLayout(self.scan_summary_card)
        summary_layout.setContentsMargins(20, 16, 20, 16)
        summary_layout.setSpacing(6)
        summary_kicker = QLabel("Latest Folder Scanner result (this session)")
        summary_kicker.setObjectName("SectionKicker")
        summary_layout.addWidget(summary_kicker)
        self.scan_summary_label = QLabel("")
        self.scan_summary_label.setObjectName("BodyLabel")
        self.scan_summary_label.setWordWrap(True)
        summary_layout.addWidget(self.scan_summary_label)
        summary_note = QLabel(
            "Scanner and Duplicate Finder results are session-only and are not "
            "written to the operation journal."
        )
        summary_note.setObjectName("MutedLabel")
        summary_note.setWordWrap(True)
        summary_layout.addWidget(summary_note)
        layout.addWidget(self.scan_summary_card)

        # --- Recent operations ---
        recent_card = QFrame()
        recent_card.setObjectName("SectionCard")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(20, 16, 20, 16)
        recent_layout.setSpacing(8)
        recent_kicker = QLabel("Recent operations")
        recent_kicker.setObjectName("SectionKicker")
        recent_layout.addWidget(recent_kicker)
        self.recent_label = QLabel("Loading recent journal activity…")
        self.recent_label.setObjectName("BodyLabel")
        self.recent_label.setWordWrap(True)
        self.recent_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        recent_layout.addWidget(self.recent_label)
        layout.addWidget(recent_card)

        # --- Safety ---
        safety = QFrame()
        safety.setObjectName("SectionCard")
        safety_layout = QVBoxLayout(safety)
        safety_layout.setContentsMargins(20, 16, 20, 16)
        safety_layout.setSpacing(8)
        safety_kicker = QLabel("Safety overview")
        safety_kicker.setObjectName("SectionKicker")
        safety_layout.addWidget(safety_kicker)
        for highlight in SAFETY_HIGHLIGHTS:
            row = QLabel(f"•  {highlight}")
            row.setObjectName("MutedLabel")
            row.setWordWrap(True)
            safety_layout.addWidget(row)
        layout.addWidget(safety)

        note = QLabel(
            "No fabricated storage metrics are shown. Batch counts come from the "
            "local SQLite journal only."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh_journal_summary()

    def refresh_journal_summary(self) -> None:
        """Reload journal-backed stats and recent batches (lightweight query)."""
        if self._database is None:
            self._set_stat(self.stat_total, "—")
            self._set_stat(self.stat_completed, "—")
            self._set_stat(self.stat_attention, "—")
            self._set_stat(self.stat_recent, "—")
            self.recent_label.setText("Journal unavailable on this dashboard.")
            return
        try:
            service = HistoryQueryService(self._database)
            result = service.list_batches(
                HistoryFilters(newest_first=True, limit=5, offset=0)
            )
        except Exception as exc:  # noqa: BLE001
            self.recent_label.setText(f"Unable to read operation journal: {exc}")
            return

        totals = result.totals
        attention = totals.all_failed + totals.all_partial
        self._set_stat(self.stat_total, str(totals.all_batches))
        self._set_stat(self.stat_completed, str(totals.all_completed))
        self._set_stat(self.stat_attention, str(attention))
        if result.batches:
            when = _format_local_timestamp(result.batches[0].created_at) or "—"
            self._set_stat(self.stat_recent, when)
            lines = []
            for batch in result.batches:
                when_i = _format_local_timestamp(batch.created_at) or batch.created_at
                lines.append(
                    f"• {when_i}  ·  {label_operation_type(batch.operation_type)}  ·  "
                    f"{label_batch_status(batch.status)}  ·  "
                    f"{batch.entry_success}/{batch.entry_total} succeeded"
                )
            self.recent_label.setText("\n".join(lines))
        else:
            self._set_stat(self.stat_recent, "—")
            self.recent_label.setText(
                "No Organizer or Bulk Renamer batches recorded yet. "
                "Apply a previewed plan to create history."
            )
        self._loaded_once = True

    def set_last_scan_summary(self, summary: str) -> None:
        """Show or hide the in-session scan summary card."""
        text = summary.strip()
        if not text:
            self.scan_summary_card.setVisible(False)
            self.scan_summary_label.clear()
            return
        self.scan_summary_label.setText(text)
        self.scan_summary_card.setVisible(True)

    def _shortcut_button(self, title: str, body: str, signal: Signal) -> QPushButton:
        button = QPushButton(f"{title}\n{body}")
        button.setObjectName("SecondaryButton")
        button.setMinimumHeight(72)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton#SecondaryButton { text-align: left; padding: 14px 16px; "
            "font-weight: 600; }"
        )
        button.setToolTip(f"Open {title}")
        button.clicked.connect(signal.emit)
        return button

    def _make_stat(self, value: str, caption: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ShortcutCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(4)
        value_label = QLabel(value)
        value_label.setObjectName("StatValue")
        value_label.setWordWrap(True)
        caption_label = QLabel(caption)
        caption_label.setObjectName("StatCaption")
        caption_label.setWordWrap(True)
        box.addWidget(value_label)
        box.addWidget(caption_label)
        frame.setProperty("value_label", value_label)
        return frame

    @staticmethod
    def _set_stat(frame: QFrame, value: str) -> None:
        label = frame.findChild(QLabel, "StatValue")
        if label is not None:
            label.setText(value)
