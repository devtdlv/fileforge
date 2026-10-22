"""Read-only Duplicate Finder page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from fileforge.services.duplicates import DuplicateProgress, DuplicateResult, DuplicateStatus
from fileforge.services.scanner import format_byte_size
from fileforge.ui.models.duplicate_table_model import (
    DuplicateGroupFilterProxy,
    DuplicateGroupModel,
    DuplicateMemberModel,
)
from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader
from fileforge.ui.workers.duplicate_worker import DuplicateWorkerController


class DuplicatesPage(QWidget):
    """Scan for identical file content without modifying anything."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        self._result: DuplicateResult | None = None
        self._controller = DuplicateWorkerController(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "Duplicate Finder",
                "Find files with identical content using size filtering and SHA-256. "
                "This page is read-only: FileForge never deletes or quarantines copies.",
            )
        )

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.choose_folder_button = QPushButton("Choose Folder…")
        self.choose_folder_button.setObjectName("SecondaryButton")
        self.choose_folder_button.clicked.connect(self._choose_folder)
        controls.addWidget(self.choose_folder_button)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setObjectName("MutedLabel")
        self.folder_label.setWordWrap(True)
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        controls.addWidget(self.folder_label, stretch=1)

        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)
        controls.addWidget(self.recursive_check)

        self.start_button = QPushButton("Start Scan")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_scan)
        controls.addWidget(self.start_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_scan)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter groups by path or hash")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_row.addWidget(self.search_edit)
        layout.addLayout(filter_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel(
            "Select a folder to find identical file content. Scanning is read-only."
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
            title="No duplicate results yet",
            body=(
                "Choose a folder and start a scan. Groups appear only when two or more "
                "distinct files share the same SHA-256 digest. Potential savings are "
                "theoretical and nothing is deleted."
            ),
            badge="Read-only detection",
        )
        layout.addWidget(self.empty_state)

        self._group_model = DuplicateGroupModel(self)
        self._group_proxy = DuplicateGroupFilterProxy(self)
        self._group_proxy.setSourceModel(self._group_model)
        self._member_model = DuplicateMemberModel(self)

        self.groups_table = QTableView()
        self.groups_table.setModel(self._group_proxy)
        self.groups_table.setSortingEnabled(True)
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.groups_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.groups_table.setWordWrap(False)
        self.groups_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.groups_table.verticalHeader().setVisible(False)
        self._configure_group_columns()
        self.groups_table.selectionModel().selectionChanged.connect(self._on_group_selected)

        self.members_table = QTableView()
        self.members_table.setModel(self._member_model)
        self.members_table.setAlternatingRowColors(True)
        self.members_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.members_table.setWordWrap(False)
        self.members_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.members_table.verticalHeader().setVisible(False)
        self._configure_member_columns()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.groups_table)
        splitter.addWidget(self.members_table)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setVisible(False)
        self._results_splitter = splitter
        layout.addWidget(splitter, stretch=1)

        # Kept disabled and clearly labeled: deletion is intentionally unavailable.
        self.delete_selected_button = QPushButton("Delete Selected Duplicates")
        self.delete_selected_button.setEnabled(False)
        self.delete_selected_button.setToolTip(
            "Deletion is not available. Duplicate Finder is read-only in this milestone."
        )
        self.delete_selected_button.setObjectName("SecondaryButton")
        layout.addWidget(self.delete_selected_button)

        note = QLabel(
            "Identical content does not mean a copy is safe to remove. "
            "Hard-linked paths are counted carefully so potential savings are not overstated. "
            "Results are kept in memory for this session only and are never uploaded."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._controller.progress.connect(self._on_progress)
        self._controller.finished.connect(self._on_finished)
        self._controller.failed.connect(self._on_failed)
        self._controller.settled.connect(self._on_settled)

    @property
    def is_scanning(self) -> bool:
        return self._controller.is_active

    def cancel_active_scan(self, wait_ms: int = 8000) -> bool:
        if not self._controller.is_active:
            return True
        self._controller.cancel()
        return self._controller.wait_for_idle(wait_ms)

    def _configure_group_columns(self) -> None:
        header = self.groups_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def _configure_member_columns(self) -> None:
        header = self.members_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

    def _choose_folder(self) -> None:
        if self._controller.is_active:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder to scan for duplicates")
        if not chosen:
            return
        self._folder = Path(chosen)
        self.folder_label.setText(str(self._folder))
        self.start_button.setEnabled(True)
        self.status_label.setText(
            "Folder selected. Start a scan when ready. No files will be modified."
        )

    def _start_scan(self) -> None:
        if self._folder is None or self._controller.is_active:
            return
        if not self._folder.exists() or not self._folder.is_dir():
            QMessageBox.warning(
                self,
                "Cannot start scan",
                "The selected folder is missing or is not a directory.",
            )
            return

        self._result = None
        self._group_model.clear()
        self._member_model.clear()
        self.empty_state.setVisible(False)
        self._results_splitter.setVisible(True)
        self.summary_label.setVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Scanning for duplicates… {self._folder}")
        self._set_busy_ui(True)
        try:
            self._controller.start(
                self._folder, recursive=self.recursive_check.isChecked()
            )
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot start scan", str(exc))

    def _cancel_scan(self) -> None:
        if self._controller.is_active:
            self.status_label.setText("Cancelling duplicate scan…")
            self._controller.cancel()

    def _on_progress(self, progress: DuplicateProgress) -> None:
        if progress.phase == "scanning":
            self.status_label.setText(
                f"Scanning folders… {progress.files_seen} file(s)"
                + (f"  |  {progress.current_path}" if progress.current_path else "")
            )
        else:
            self.status_label.setText(
                "Hashing candidates… "
                f"{progress.hashed}/{progress.size_candidates}  |  "
                f"groups: {progress.groups_found}"
                + (f"  |  {progress.current_path}" if progress.current_path else "")
            )

    def _on_finished(self, result: DuplicateResult) -> None:
        self._result = result
        self._group_model.set_groups(result.groups, root=result.root)
        self._group_proxy.invalidate()
        self.groups_table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self._member_model.clear()

        has_groups = bool(result.groups)
        self._results_splitter.setVisible(has_groups)
        self.empty_state.setVisible(not has_groups)
        if not has_groups:
            if result.status == DuplicateStatus.CANCELLED:
                self.empty_state.set_content(
                    "Scan cancelled",
                    "No duplicate groups were finalized. Choose a folder and try again.",
                )
            elif result.status == DuplicateStatus.FAILED:
                self.empty_state.set_content(
                    "Scan could not complete",
                    result.message or "The selected folder could not be scanned.",
                )
            else:
                self.empty_state.set_content(
                    "No duplicates found",
                    result.message
                    or "No two distinct files shared identical content.",
                )

        self.summary_label.setText(
            f"{result.message}  |  Files scanned: {result.files_scanned}  |  "
            f"Groups: {result.group_count}  |  Paths in groups: {result.duplicate_copy_count}  |  "
            f"Theoretical potential savings: {format_byte_size(result.potential_savings_bytes)}  |  "
            f"Issues: {len(result.errors)}"
        )
        self.summary_label.setVisible(True)
        self.status_label.setText(result.message)

        if result.groups:
            self.groups_table.selectRow(0)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(message)
        self.summary_label.setVisible(False)
        self._results_splitter.setVisible(False)
        self.empty_state.setVisible(True)
        QMessageBox.critical(self, "Duplicate scan failed", message)

    def _on_settled(self) -> None:
        self.progress_bar.setVisible(False)
        self._set_busy_ui(False)

    def _set_busy_ui(self, busy: bool) -> None:
        self.choose_folder_button.setEnabled(not busy)
        self.recursive_check.setEnabled(not busy)
        self.start_button.setEnabled(not busy and self._folder is not None)
        self.cancel_button.setEnabled(busy)
        self.search_edit.setEnabled(True)

    def _on_search_changed(self, text: str) -> None:
        self._group_proxy.set_query(text)

    def _on_group_selected(self, *_args: object) -> None:
        indexes = self.groups_table.selectionModel().selectedRows()
        if not indexes:
            self._member_model.clear()
            return
        proxy_index = indexes[0]
        source_index = self._group_proxy.mapToSource(proxy_index)
        group = self._group_model.group_at(source_index.row())
        if group is None:
            self._member_model.clear()
            return
        self._member_model.set_files(group.files)
