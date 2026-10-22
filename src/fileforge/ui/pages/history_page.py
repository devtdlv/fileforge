"""Read-only Operation History browser."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from fileforge.database.connection import DatabaseManager
from fileforge.services.history import (
    DEFAULT_PAGE_SIZE,
    BatchListResult,
    BatchSummary,
    HistoryBatchStatus,
    HistoryFilters,
    HistoryOperationType,
    HistoryQueryService,
)
from fileforge.ui.models.history_table_model import HistoryBatchModel, HistoryEntryModel
from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader
from fileforge.ui.widgets.table_utils import configure_result_table
from fileforge.ui.workers.history_worker import HistoryWorkerController


class HistoryPage(QWidget):
    """Browse journaled Organizer and Bulk Renamer batches (read-only)."""

    def __init__(
        self,
        database: DatabaseManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._controller = HistoryWorkerController(self)
        self._filters = HistoryFilters(limit=DEFAULT_PAGE_SIZE, offset=0)
        self._selected_batch_id: str | None = None
        self._has_loaded_once = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        layout.addWidget(
            PageHeader(
                "Operation History",
                "Review recorded Organizer moves and Bulk Renamer batches from the "
                "local SQLite journal. This page is read-only: Junction does not "
                "undo, retry, delete, or edit history here.",
            )
        )

        self.summary_label = QLabel("No history loaded yet.")
        self.summary_label.setObjectName("MutedLabel")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.type_combo = QComboBox()
        self.type_combo.addItem("All types", HistoryOperationType.ALL)
        self.type_combo.addItem("Organizer", HistoryOperationType.ORGANIZE_MOVE)
        self.type_combo.addItem("Bulk Renamer", HistoryOperationType.BULK_RENAME)
        self.type_combo.currentIndexChanged.connect(self._on_filters_changed)
        filter_row.addWidget(QLabel("Type"))
        filter_row.addWidget(self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItem("All statuses", HistoryBatchStatus.ALL)
        self.status_combo.addItem("Completed", HistoryBatchStatus.COMPLETED)
        self.status_combo.addItem("Partial", HistoryBatchStatus.PARTIAL)
        self.status_combo.addItem("Failed", HistoryBatchStatus.FAILED)
        self.status_combo.addItem("Cancelled", HistoryBatchStatus.CANCELLED)
        self.status_combo.addItem("Pending", HistoryBatchStatus.PENDING)
        self.status_combo.currentIndexChanged.connect(self._on_filters_changed)
        filter_row.addWidget(QLabel("Status"))
        filter_row.addWidget(self.status_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Newest first", True)
        self.sort_combo.addItem("Oldest first", False)
        self.sort_combo.currentIndexChanged.connect(self._on_filters_changed)
        filter_row.addWidget(QLabel("Sort"))
        filter_row.addWidget(self.sort_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search paths, summary, or errors")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.returnPressed.connect(self._on_filters_changed)
        filter_row.addWidget(self.search_edit, stretch=1)

        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("SecondaryButton")
        self.search_button.clicked.connect(self._on_filters_changed)
        filter_row.addWidget(self.search_button)

        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setObjectName("SecondaryButton")
        self.clear_filters_button.clicked.connect(self._clear_filters)
        filter_row.addWidget(self.clear_filters_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self.refresh)
        filter_row.addWidget(self.refresh_button)
        layout.addLayout(filter_row)

        page_row = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.setObjectName("SecondaryButton")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._prev_page)
        page_row.addWidget(self.prev_button)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("SecondaryButton")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._next_page)
        page_row.addWidget(self.next_button)
        self.page_label = QLabel("")
        self.page_label.setObjectName("MutedLabel")
        page_row.addWidget(self.page_label, stretch=1)
        layout.addLayout(page_row)

        self.status_label = QLabel(
            "History loads when you open this page or click Refresh. "
            "Viewing history never changes files."
        )
        self.status_label.setObjectName("BodyLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.empty_state = EmptyStateWidget(
            title="No operation history yet",
            body=(
                "Completed Organizer and Bulk Renamer operations are recorded in "
                "the local database. Run a previewed apply or rename to create history, "
                "then refresh this page."
            ),
            badge="Read-only journal",
        )
        layout.addWidget(self.empty_state)

        self._batch_model = HistoryBatchModel(self)
        self.batches_table = QTableView()
        self.batches_table.setModel(self._batch_model)
        configure_result_table(self.batches_table, min_height=200)
        self.batches_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.batches_table.setSortingEnabled(False)
        self._configure_batch_columns()
        self.batches_table.selectionModel().selectionChanged.connect(
            self._on_batch_selected
        )

        self.detail_label = QLabel("Select a batch to inspect file-level outcomes.")
        self.detail_label.setObjectName("MutedLabel")
        self.detail_label.setWordWrap(True)

        self._entry_model = HistoryEntryModel(self)
        self.entries_table = QTableView()
        self.entries_table.setModel(self._entry_model)
        configure_result_table(self.entries_table, min_height=180)
        self.entries_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._configure_entry_columns()

        detail_host = QWidget()
        detail_layout = QVBoxLayout(detail_host)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)
        detail_layout.addWidget(self.detail_label)
        detail_layout.addWidget(self.entries_table, stretch=1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.batches_table)
        splitter.addWidget(detail_host)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([280, 240])
        splitter.setVisible(False)
        self._splitter = splitter
        layout.addWidget(splitter, stretch=1)

        # Undo remains intentionally unavailable.
        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.setEnabled(False)
        self.undo_button.setToolTip(
            "Undo is not implemented. Operation History is read-only in this milestone."
        )
        self.undo_button.setAccessibleName("Undo Last Operation (unavailable)")
        self.undo_button.setObjectName("SecondaryButton")
        layout.addWidget(self.undo_button)

        note = QLabel(
            "Journal statuses come from recorded outcomes only. Entries still marked "
            "pending were not completed successfully. Skipped files that never received "
            "a journal row are not listed. Nothing on this page modifies the filesystem "
            "or the journal."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._controller.list_finished.connect(self._on_list_finished)
        self._controller.failed.connect(self._on_failed)
        self._controller.settled.connect(self._on_settled)

    @property
    def is_busy(self) -> bool:
        return self._controller.is_active

    def cancel_active_work(self, wait_ms: int = 5000) -> bool:
        if not self._controller.is_active:
            return True
        self._controller.cancel()
        return self._controller.wait_for_idle(wait_ms)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._has_loaded_once:
            self.refresh()

    def refresh(self) -> None:
        """Reload the current filter page from the database."""
        self._filters = HistoryFilters(
            operation_type=self.type_combo.currentData(),
            batch_status=self.status_combo.currentData(),
            search=self.search_edit.text().strip(),
            newest_first=bool(self.sort_combo.currentData()),
            limit=DEFAULT_PAGE_SIZE,
            offset=self._filters.offset,
        )
        self.status_label.setText("Loading operation history…")
        self._set_busy(True)
        try:
            self._controller.load_batches(self._database.path, self._filters)
        except RuntimeError as exc:
            self._set_busy(False)
            QMessageBox.warning(self, "Cannot load history", str(exc))

    def _configure_batch_columns(self) -> None:
        header = self.batches_table.horizontalHeader()
        header.setMinimumSectionSize(64)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        # Prefer Interactive so users can widen long path columns; stretch both.
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(80)
        self.batches_table.setColumnWidth(7, 220)
        self.batches_table.setColumnWidth(8, 220)

    def _configure_entry_columns(self) -> None:
        header = self.entries_table.horizontalHeader()
        header.setMinimumSectionSize(64)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    def _on_filters_changed(self, *_args: object) -> None:
        self._filters = HistoryFilters(
            operation_type=self.type_combo.currentData(),
            batch_status=self.status_combo.currentData(),
            search=self.search_edit.text().strip(),
            newest_first=bool(self.sort_combo.currentData()),
            limit=DEFAULT_PAGE_SIZE,
            offset=0,
        )
        self.refresh()

    def _clear_filters(self) -> None:
        self.type_combo.blockSignals(True)
        self.status_combo.blockSignals(True)
        self.sort_combo.blockSignals(True)
        self.type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self.type_combo.blockSignals(False)
        self.status_combo.blockSignals(False)
        self.sort_combo.blockSignals(False)
        self._filters = HistoryFilters(limit=DEFAULT_PAGE_SIZE, offset=0)
        self.refresh()

    def _prev_page(self) -> None:
        offset = max(0, self._filters.offset - self._filters.limit)
        self._filters = HistoryFilters(
            operation_type=self._filters.operation_type,
            batch_status=self._filters.batch_status,
            search=self._filters.search,
            newest_first=self._filters.newest_first,
            limit=self._filters.limit,
            offset=offset,
        )
        self.refresh()

    def _next_page(self) -> None:
        self._filters = HistoryFilters(
            operation_type=self._filters.operation_type,
            batch_status=self._filters.batch_status,
            search=self._filters.search,
            newest_first=self._filters.newest_first,
            limit=self._filters.limit,
            offset=self._filters.offset + self._filters.limit,
        )
        self.refresh()

    def _on_list_finished(self, result: BatchListResult) -> None:
        self._has_loaded_once = True
        if result.error:
            self._show_error_state(result.error)
            return

        totals = result.totals
        self.summary_label.setText(
            f"All batches: {totals.all_batches}  |  "
            f"Completed: {totals.all_completed}  |  "
            f"Partial: {totals.all_partial}  |  "
            f"Failed: {totals.all_failed}  |  "
            f"Cancelled: {totals.all_cancelled}  |  "
            f"Matching filters: {totals.matching_batches}"
        )

        self._batch_model.set_batches(result.batches)
        self._entry_model.clear()
        self._selected_batch_id = None

        has_rows = bool(result.batches)
        self._splitter.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        if not has_rows:
            if totals.all_batches == 0:
                self.empty_state.set_content(
                    "No operation history yet",
                    "Organizer and Bulk Renamer writes appear here after a confirmed apply.",
                )
            else:
                self.empty_state.set_content(
                    "No matching results",
                    "Try clearing filters or adjusting the search text.",
                )
            self.detail_label.setText("Select a batch to inspect file-level outcomes.")

        self.status_label.setText(result.message)
        matching = totals.matching_batches
        offset = result.filters.offset
        limit = result.filters.limit
        page = (offset // limit) + 1 if limit else 1
        pages = max(1, (matching + limit - 1) // limit) if limit else 1
        self.page_label.setText(f"Page {page} of {pages}")
        self.prev_button.setEnabled(offset > 0)
        self.next_button.setEnabled(offset + limit < matching)

        if has_rows:
            self.batches_table.selectRow(0)

    def _on_batch_selected(self, *_args: object) -> None:
        indexes = self.batches_table.selectionModel().selectedRows()
        if not indexes:
            self._entry_model.clear()
            self._selected_batch_id = None
            self.detail_label.setText("Select a batch to inspect file-level outcomes.")
            return
        batch = self._batch_model.batch_at(indexes[0].row())
        if batch is None:
            return
        self._load_entries_for_batch(batch)

    def _load_entries_for_batch(self, batch: BatchSummary) -> None:
        """Load entries on the GUI thread (bounded, typically small)."""
        self._selected_batch_id = batch.batch_id
        self.detail_label.setText(
            f"{batch.operation_label} · {batch.status_label} · "
            f"{batch.summary or '(no summary)'} · "
            f"{batch.entry_total} journal entr(y/ies)"
        )
        try:
            service = HistoryQueryService(self._database)
            entries = service.list_entries(batch.batch_id)
        except Exception as exc:  # noqa: BLE001
            self._entry_model.clear()
            self.status_label.setText(f"Unable to load entries: {exc}")
            return
        self._entry_model.set_entries(
            entries,
            source_root=batch.source_root,
            destination_root=batch.destination_root,
        )
        self.status_label.setText(
            f"Showing {len(entries)} entr(y/ies) for batch {batch.batch_id[:8]}…"
        )

    def _on_failed(self, message: str) -> None:
        self._show_error_state(message)
        QMessageBox.warning(self, "Operation History", message)

    def _show_error_state(self, message: str) -> None:
        self._batch_model.clear()
        self._entry_model.clear()
        self._splitter.setVisible(False)
        self.empty_state.setVisible(True)
        self.empty_state.set_content(
            "Unable to load history",
            message,
        )
        self.status_label.setText(message)
        self.summary_label.setText("History unavailable.")

    def _on_settled(self) -> None:
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.search_button.setEnabled(not busy)
        self.clear_filters_button.setEnabled(not busy)
        self.type_combo.setEnabled(not busy)
        self.status_combo.setEnabled(not busy)
        self.sort_combo.setEnabled(not busy)
        self.search_edit.setEnabled(not busy)
        # Keep prev/next gated by page state when not busy; refresh() re-enables via result.
        if busy:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
