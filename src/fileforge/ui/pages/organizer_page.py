"""Smart Organizer page with preview-first, confirmed file moves."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from fileforge.database.connection import DatabaseManager
from fileforge.services.organizer import (
    ExecutionProgress,
    ExecutionResult,
    OrganizeMode,
    OrganizePlan,
    PlanStatus,
)
from fileforge.services.scanner import ScanProgress
from fileforge.ui.models.organize_table_model import OrganizeTableModel
from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader
from fileforge.ui.widgets.table_utils import configure_result_table
from fileforge.ui.workers.organize_worker import OrganizeWorkerController

_MODE_LABELS = (
    ("By file extension", OrganizeMode.EXTENSION),
    ("By file category", OrganizeMode.CATEGORY),
    ("By modified year/month", OrganizeMode.YEAR_MONTH),
)


class OrganizerPage(QWidget):
    """Preview organization plans and apply them only after confirmation."""

    def __init__(
        self,
        database: DatabaseManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._source: Path | None = None
        self._destination: Path | None = None
        self._plan: OrganizePlan | None = None
        self._controller = OrganizeWorkerController(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "Smart Organizer",
                "Build a move plan, review every destination, then confirm before "
                "any files are relocated. Overwrites are never silent.",
            )
        )

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.choose_source_button = QPushButton("Source Folder…")
        self.choose_source_button.setObjectName("SecondaryButton")
        self.choose_source_button.clicked.connect(self._choose_source)
        path_row.addWidget(self.choose_source_button)
        self.source_label = QLabel("No source selected")
        self.source_label.setObjectName("MutedLabel")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_row.addWidget(self.source_label, stretch=1)
        layout.addLayout(path_row)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)
        self.choose_destination_button = QPushButton("Destination Folder…")
        self.choose_destination_button.setObjectName("SecondaryButton")
        self.choose_destination_button.clicked.connect(self._choose_destination)
        dest_row.addWidget(self.choose_destination_button)
        self.destination_label = QLabel("No destination selected")
        self.destination_label.setObjectName("MutedLabel")
        self.destination_label.setWordWrap(True)
        self.destination_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        dest_row.addWidget(self.destination_label, stretch=1)
        layout.addLayout(dest_row)

        options = QHBoxLayout()
        options.setSpacing(10)
        self.mode_combo = QComboBox()
        for label, mode in _MODE_LABELS:
            self.mode_combo.addItem(label, mode)
        options.addWidget(QLabel("Organize by"))
        options.addWidget(self.mode_combo)
        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)
        options.addWidget(self.recursive_check)
        options.addStretch(1)
        layout.addLayout(options)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.preview_button = QPushButton("Preview Plan")
        self.preview_button.setObjectName("PrimaryButton")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._start_preview)
        actions.addWidget(self.preview_button)

        self.apply_plan_button = QPushButton("Apply Organization Plan")
        self.apply_plan_button.setEnabled(False)
        self.apply_plan_button.setToolTip("Requires a conflict-free preview and confirmation")
        self.apply_plan_button.setObjectName("SecondaryButton")
        self.apply_plan_button.clicked.connect(self._confirm_and_apply)
        actions.addWidget(self.apply_plan_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel(
            "Select source and destination folders, then preview a plan. "
            "Preview never modifies files."
        )
        self.status_label.setObjectName("BodyLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setVisible(False)
        layout.addWidget(self.summary_label)

        self.empty_state = EmptyStateWidget(
            title="No organization plan yet",
            body=(
                "Choose folders and click Preview Plan to see every proposed move. "
                "Apply stays disabled until the plan is conflict-free and you confirm."
            ),
            badge="Preview before apply",
        )
        layout.addWidget(self.empty_state)

        self._table_model = OrganizeTableModel(self)
        self.results_table = QTableView()
        self.results_table.setModel(self._table_model)
        configure_result_table(self.results_table, min_height=220)
        self.results_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.results_table.setVisible(False)
        self._configure_results_columns()
        layout.addWidget(self.results_table, stretch=1)

        self._controller.preview_progress.connect(self._on_preview_progress)
        self._controller.preview_finished.connect(self._on_preview_finished)
        self._controller.preview_failed.connect(self._on_preview_failed)
        self._controller.execute_progress.connect(self._on_execute_progress)
        self._controller.execute_finished.connect(self._on_execute_finished)
        self._controller.execute_failed.connect(self._on_execute_failed)
        self._controller.settled.connect(self._on_settled)

    @property
    def is_busy(self) -> bool:
        return self._controller.is_active

    def cancel_active_work(self, wait_ms: int = 8000) -> bool:
        if not self._controller.is_active:
            return True
        self._controller.cancel()
        return self._controller.wait_for_idle(wait_ms)

    def _configure_results_columns(self) -> None:
        """Give Source/Destination room to breathe; keep columns user-resizable."""
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Source
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Destination
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Rule
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Notes
        self.results_table.setColumnWidth(1, 280)
        self.results_table.setColumnWidth(2, 280)
        self.results_table.setColumnWidth(4, 160)

    def _choose_source(self) -> None:
        if self._controller.is_active:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose source folder")
        if not chosen:
            return
        self._source = Path(chosen)
        self.source_label.setText(str(self._source))
        self._plan = None
        self.apply_plan_button.setEnabled(False)
        self._refresh_preview_enabled()

    def _choose_destination(self) -> None:
        if self._controller.is_active:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose destination folder")
        if not chosen:
            return
        self._destination = Path(chosen)
        self.destination_label.setText(str(self._destination))
        self._plan = None
        self.apply_plan_button.setEnabled(False)
        self._refresh_preview_enabled()

    def _refresh_preview_enabled(self) -> None:
        self.preview_button.setEnabled(
            self._source is not None
            and self._destination is not None
            and not self._controller.is_active
        )

    def _selected_mode(self) -> OrganizeMode:
        mode = self.mode_combo.currentData()
        assert isinstance(mode, OrganizeMode)
        return mode

    def _start_preview(self) -> None:
        if self._source is None or self._destination is None or self._controller.is_active:
            return
        self._plan = None
        self.apply_plan_button.setEnabled(False)
        self._table_model.clear()
        self.empty_state.setVisible(False)
        self.results_table.setVisible(True)
        self.summary_label.setVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Building preview… (no files will be modified)")
        self._set_busy_ui(True)
        try:
            self._controller.start_preview(
                self._source,
                self._destination,
                mode=self._selected_mode(),
                recursive=self.recursive_check.isChecked(),
            )
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot preview", str(exc))

    def _confirm_and_apply(self) -> None:
        if self._plan is None or not self._plan.can_apply or self._controller.is_active:
            return
        ready_count = len(self._plan.ready_items)
        answer = QMessageBox.question(
            self,
            "Confirm organization",
            (
                f"Move {ready_count} file(s) according to the previewed plan?\n\n"
                f"Source: {self._plan.source_root}\n"
                f"Destination: {self._plan.destination_root}\n\n"
                "Existing destination files will never be overwritten. "
                "This cannot be undone in the current milestone."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Apply cancelled. Preview remains unchanged.")
            return

        self.progress_bar.setRange(0, max(ready_count, 1))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Applying organization plan…")
        self._set_busy_ui(True)
        try:
            self._controller.start_execute(self._plan, self._database.path)
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot apply plan", str(exc))

    def _cancel(self) -> None:
        if self._controller.is_active:
            self.status_label.setText("Cancelling…")
            self._controller.cancel()

    def _on_preview_progress(self, progress: ScanProgress) -> None:
        self.status_label.setText(
            "Scanning for preview… "
            f"{progress.files_seen} file(s), {progress.directories_seen} folder(s)"
        )

    def _on_preview_finished(self, plan: OrganizePlan) -> None:
        self._plan = plan
        self._table_model.set_items(
            plan.items,
            source_root=plan.source_root,
            destination_root=plan.destination_root,
        )
        has_rows = bool(plan.items)
        self.results_table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        if not has_rows:
            self.empty_state.set_content(
                "Nothing to organize",
                plan.message or "No files matched the selected folders.",
            )

        conflicts = len(plan.conflict_items)
        ready = len(plan.ready_items)
        self.summary_label.setText(
            f"{len(plan.items)} items · {ready} ready · {conflicts} conflicts/invalid"
        )
        self.summary_label.setToolTip(plan.message)
        self.summary_label.setVisible(True)
        self.status_label.setText(plan.message)
        self.apply_plan_button.setEnabled(plan.can_apply)
        if plan.status == PlanStatus.BLOCKED:
            QMessageBox.warning(
                self,
                "Conflicts block apply",
                plan.message
                + "\n\nResolve destination collisions or choose different folders, "
                "then preview again.",
            )

    def _on_preview_failed(self, message: str) -> None:
        self._plan = None
        self.apply_plan_button.setEnabled(False)
        self.status_label.setText(message)
        QMessageBox.critical(self, "Preview failed", message)

    def _on_execute_progress(self, progress: ExecutionProgress) -> None:
        if progress.total > 0:
            self.progress_bar.setRange(0, progress.total)
            self.progress_bar.setValue(progress.completed)
        self.status_label.setText(
            f"Moving files… {progress.completed}/{progress.total} "
            f"(ok: {progress.succeeded}, failed: {progress.failed})"
            + (f"  |  {progress.current_source}" if progress.current_source else "")
        )

    def _on_execute_finished(self, result: ExecutionResult) -> None:
        self._table_model.set_items(
            result.items,
            source_root=result.plan.source_root,
            destination_root=result.plan.destination_root,
        )
        self.results_table.setVisible(True)
        self.empty_state.setVisible(False)
        self.summary_label.setText(result.message)
        self.summary_label.setVisible(True)
        self.status_label.setText(result.message)
        # Require a fresh preview after execution.
        self._plan = None
        self.apply_plan_button.setEnabled(False)
        if result.status in {PlanStatus.PARTIAL, PlanStatus.FAILED}:
            QMessageBox.warning(self, "Organization finished with issues", result.message)
        elif result.status == PlanStatus.COMPLETED:
            QMessageBox.information(self, "Organization completed", result.message)

    def _on_execute_failed(self, message: str) -> None:
        self.status_label.setText(message)
        self.apply_plan_button.setEnabled(False)
        QMessageBox.critical(self, "Organization failed", message)

    def _on_settled(self) -> None:
        self.progress_bar.setVisible(False)
        self._set_busy_ui(False)

    def _set_busy_ui(self, busy: bool) -> None:
        self.choose_source_button.setEnabled(not busy)
        self.choose_destination_button.setEnabled(not busy)
        self.mode_combo.setEnabled(not busy)
        self.recursive_check.setEnabled(not busy)
        self.preview_button.setEnabled(
            not busy and self._source is not None and self._destination is not None
        )
        self.apply_plan_button.setEnabled(
            not busy and self._plan is not None and self._plan.can_apply
        )
        self.cancel_button.setEnabled(busy)
