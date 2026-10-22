"""Functional read-only Folder Scanner page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from fileforge.services.scanner import (
    EntryKind,
    ScanProgress,
    ScanResult,
    ScanStatus,
    format_byte_size,
)
from fileforge.ui.models.scan_table_model import ScanFilterProxyModel, ScanTableModel
from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader
from fileforge.ui.widgets.table_utils import configure_result_table
from fileforge.ui.workers.scan_worker import ScanWorkerController, summarize_scan_result


class ScannerPage(QWidget):
    """Choose a folder, scan metadata in the background, and review results."""

    scan_summary_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_folder: Path | None = None
        self._last_result: ScanResult | None = None
        self._controller = ScanWorkerController(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        layout.addWidget(
            PageHeader(
                "Folder Scanner",
                "Inventory a folder you choose. Scanning is read-only: Junction "
                "never moves, renames, overwrites, or deletes files while scanning.",
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
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.folder_label.setWordWrap(True)
        controls.addWidget(self.folder_label, stretch=1)

        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)
        self.recursive_check.setToolTip("When unchecked, only the selected folder's immediate contents are listed.")
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
        filter_row.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name or relative path")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_row.addWidget(self.search_edit, stretch=2)

        self.extension_filter = QComboBox()
        self.extension_filter.setMinimumWidth(160)
        self.extension_filter.addItem("All types", "")
        self.extension_filter.addItem("Files only", "__files__")
        self.extension_filter.addItem("Folders only", "__folders__")
        self.extension_filter.currentIndexChanged.connect(self._on_extension_changed)
        filter_row.addWidget(self.extension_filter)
        layout.addLayout(filter_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate while running
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Select a folder to begin a read-only scan.")
        self.status_label.setObjectName("BodyLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedLabel")
        self.summary_label.setWordWrap(True)
        self.summary_label.setVisible(False)
        layout.addWidget(self.summary_label)

        self.empty_state = EmptyStateWidget(
            title="No scan results yet",
            body=(
                "Choose a folder and start a scan to review file names, sizes, "
                "and modification times. Results stay in this session only and "
                "are not written back to the scanned folder."
            ),
            badge="Read-only inventory",
        )
        layout.addWidget(self.empty_state)

        self._table_model = ScanTableModel(self)
        self._proxy = ScanFilterProxyModel(self)
        self._proxy.setSourceModel(self._table_model)

        self.results_table = QTableView()
        self.results_table.setModel(self._proxy)
        self.results_table.setSortingEnabled(True)
        configure_result_table(self.results_table, min_height=220)
        self.results_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.results_table.horizontalHeader().setSectionsMovable(False)
        self._configure_result_columns()
        self.results_table.setVisible(False)
        layout.addWidget(self.results_table, stretch=1)

        self._controller.progress.connect(self._on_progress)
        self._controller.finished.connect(self._on_finished)
        self._controller.failed.connect(self._on_failed)
        self._controller.settled.connect(self._on_settled)

    @property
    def is_scanning(self) -> bool:
        return self._controller.is_active

    @property
    def last_result(self) -> ScanResult | None:
        return self._last_result

    def selected_folder(self) -> Path | None:
        return self._selected_folder

    def cancel_active_scan(self, wait_ms: int = 5000) -> bool:
        """Cancel any in-flight scan and wait briefly for the worker to settle."""
        if not self._controller.is_active:
            return True
        self._controller.cancel()
        return self._controller.wait_for_idle(wait_ms)

    def _choose_folder(self) -> None:
        if self._controller.is_active:
            return
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose folder to scan",
            str(self._selected_folder or Path.home()),
        )
        if not chosen:
            return
        self._selected_folder = Path(chosen)
        display = str(self._selected_folder)
        self.folder_label.setText(display)
        self.folder_label.setToolTip(display)
        self.start_button.setEnabled(True)
        self.status_label.setText(
            "Folder selected. Start a scan when ready. Scanning will not modify files."
        )

    def _start_scan(self) -> None:
        if self._selected_folder is None or self._controller.is_active:
            return
        root = self._selected_folder
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(
                self,
                "Cannot start scan",
                "The selected folder is missing or is not a directory.",
            )
            return

        self._last_result = None
        self._table_model.clear()
        self._reset_extension_filter_options()
        self.empty_state.setVisible(False)
        self.results_table.setVisible(True)
        self.summary_label.setVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Scanning… {root}")
        self._set_scanning_ui(True)
        try:
            self._controller.start(root, recursive=self.recursive_check.isChecked())
        except RuntimeError as exc:
            self._set_scanning_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot start scan", str(exc))

    def _cancel_scan(self) -> None:
        if self._controller.is_active:
            self.status_label.setText("Cancelling scan…")
            self._controller.cancel()

    def _on_progress(self, progress: ScanProgress) -> None:
        self.status_label.setText(
            "Scanning… "
            f"{progress.files_seen} file(s), {progress.directories_seen} folder(s), "
            f"{progress.errors_seen} issue(s)"
            + (f"  |  {progress.current_path}" if progress.current_path else "")
        )

    def _on_finished(self, result: ScanResult) -> None:
        self._last_result = result
        self._table_model.set_entries(result.entries)
        self._populate_extension_filter(result)
        self._proxy.invalidate()
        self.results_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._update_summary(result)
        summary = summarize_scan_result(result)
        self.scan_summary_changed.emit(summary)

        has_rows = bool(result.entries)
        self.results_table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        if not has_rows:
            if result.status == ScanStatus.CANCELLED:
                self.empty_state.set_content(
                    "Scan cancelled",
                    "No entries were kept from the cancelled scan. "
                    "Choose a folder and try again.",
                )
            elif result.status == ScanStatus.FAILED:
                self.empty_state.set_content(
                    "Scan could not complete",
                    result.message or "The selected folder could not be scanned.",
                )
            else:
                self.empty_state.set_content(
                    "Folder is empty",
                    "The selected folder did not contain any listable entries.",
                )

        status_prefix = {
            ScanStatus.COMPLETED: "Scan completed",
            ScanStatus.CANCELLED: "Scan cancelled",
            ScanStatus.PARTIAL: "Scan completed with issues",
            ScanStatus.FAILED: "Scan failed",
        }.get(result.status, "Scan finished")
        # Avoid repeating the same phrase when the engine message already states it.
        message = (result.message or "").strip()
        if message and message.casefold().startswith(status_prefix.casefold()):
            self.status_label.setText(message)
        elif message:
            self.status_label.setText(f"{status_prefix}. {message}")
        else:
            self.status_label.setText(status_prefix)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(message)
        self.summary_label.setVisible(False)
        self.results_table.setVisible(False)
        self.empty_state.setVisible(True)
        QMessageBox.critical(self, "Scan failed", message)
        self.scan_summary_changed.emit("")

    def _on_settled(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self._set_scanning_ui(False)

    def _set_scanning_ui(self, scanning: bool) -> None:
        self.choose_folder_button.setEnabled(not scanning)
        self.recursive_check.setEnabled(not scanning)
        self.start_button.setEnabled(not scanning and self._selected_folder is not None)
        self.cancel_button.setEnabled(scanning)
        self.search_edit.setEnabled(True)
        self.extension_filter.setEnabled(True)

    def _update_summary(self, result: ScanResult) -> None:
        text = (
            f"Files: {result.file_count}  |  "
            f"Folders: {result.directory_count}  |  "
            f"Skipped links/junctions/other: {result.skipped_count}  |  "
            f"Total size: {format_byte_size(result.total_size_bytes)}  |  "
            f"Issues: {len(result.errors)}"
        )
        if result.errors:
            sample = "; ".join(
                f"{error.path}: {error.message}" for error in result.errors[:3]
            )
            extra = f"  |  Examples: {sample}"
            if len(result.errors) > 3:
                extra += f" (+{len(result.errors) - 3} more)"
            text += extra
        self.summary_label.setText(text)
        self.summary_label.setVisible(True)

    def _reset_extension_filter_options(self) -> None:
        current = self.extension_filter.currentData()
        self.extension_filter.blockSignals(True)
        self.extension_filter.clear()
        self.extension_filter.addItem("All types", "")
        self.extension_filter.addItem("Files only", "__files__")
        self.extension_filter.addItem("Folders only", "__folders__")
        self.extension_filter.blockSignals(False)
        if current:
            index = self.extension_filter.findData(current)
            if index >= 0:
                self.extension_filter.setCurrentIndex(index)
        self._proxy.set_extension_filter(str(self.extension_filter.currentData() or ""))

    def _populate_extension_filter(self, result: ScanResult) -> None:
        extensions = sorted(
            {
                entry.extension
                for entry in result.entries
                if entry.kind == EntryKind.FILE and entry.extension
            }
        )
        self._reset_extension_filter_options()
        self.extension_filter.blockSignals(True)
        for ext in extensions:
            self.extension_filter.addItem(f".{ext}", ext)
        self.extension_filter.blockSignals(False)

    def _configure_result_columns(self) -> None:
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Ext
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Modified
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Relative path
        # Ensure datetime strings are not clipped at common window widths.
        self.results_table.setColumnWidth(4, 150)

    def _on_search_changed(self, text: str) -> None:
        self._proxy.set_name_query(text)

    def _on_extension_changed(self, _index: int) -> None:
        self._proxy.set_extension_filter(str(self.extension_filter.currentData() or ""))
