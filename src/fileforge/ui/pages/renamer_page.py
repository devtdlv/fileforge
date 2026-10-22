"""Preview-first Bulk Renamer page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from fileforge.database.connection import DatabaseManager
from fileforge.services.renamer import (
    CaseMode,
    RenameExecutionResult,
    RenameItemStatus,
    RenamePlan,
    RenamePlanStatus,
    RenameProgress,
    RenameRules,
)
from fileforge.services.renamer.rules import RULE_ORDER_DESCRIPTION
from fileforge.ui.models.rename_table_model import RenameFileListModel, RenamePreviewModel
from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader
from fileforge.ui.widgets.table_utils import configure_result_table
from fileforge.ui.workers.rename_worker import RenameWorkerController

# Practical pane floors so both tables stay usable; the page scrolls when the
# window cannot fit header + rules + actions + these minimums together.
_FILES_TABLE_MIN_HEIGHT = 200
_PREVIEW_TABLE_MIN_HEIGHT = 220
_SPLITTER_HANDLE = 8


class RenamerPage(QWidget):
    """Select files, preview renames, and apply only after confirmation."""

    def __init__(
        self,
        database: DatabaseManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database = database
        self._folder: Path | None = None
        self._plan: RenamePlan | None = None
        self._preview_valid = False
        self._pending_reload = False
        self._controller = RenameWorkerController(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("RenamerScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll)
        self._scroll = scroll

        content = QWidget()
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        layout.addWidget(
            PageHeader(
                "Bulk Renamer",
                "Configure rules, preview every proposed name, then confirm. "
                "Extensions are preserved by default.",
            )
        )

        # --- Folder / load ---
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.choose_folder_button = QPushButton("Choose Folder…")
        self.choose_folder_button.setObjectName("SecondaryButton")
        self.choose_folder_button.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.choose_folder_button)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setObjectName("MutedLabel")
        self.folder_label.setWordWrap(True)
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        folder_row.addWidget(self.folder_label, stretch=1)

        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)
        self.recursive_check.stateChanged.connect(self._invalidate_preview)
        folder_row.addWidget(self.recursive_check)

        self.load_button = QPushButton("Load Files")
        self.load_button.setObjectName("SecondaryButton")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self._start_inventory)
        folder_row.addWidget(self.load_button)
        layout.addLayout(folder_row)

        # --- Rules (compact so tables keep vertical room on laptop heights) ---
        rules_box = QGroupBox("Rename rules")
        rules_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        rules_form = QFormLayout(rules_box)
        rules_form.setContentsMargins(12, 10, 12, 10)
        rules_form.setHorizontalSpacing(10)
        rules_form.setVerticalSpacing(6)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g. holiday_")
        self.prefix_edit.textChanged.connect(self._invalidate_preview)
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("e.g. _final (before extension)")
        self.suffix_edit.setToolTip("Inserted before the file extension.")
        self.suffix_edit.textChanged.connect(self._invalidate_preview)
        affix_row = QHBoxLayout()
        affix_row.setSpacing(8)
        affix_row.addWidget(QLabel("Prefix"))
        affix_row.addWidget(self.prefix_edit, stretch=1)
        affix_row.addWidget(QLabel("Suffix"))
        affix_row.addWidget(self.suffix_edit, stretch=1)
        rules_form.addRow("Affixes", affix_row)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find text in the stem")
        self.search_edit.textChanged.connect(self._invalidate_preview)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replacement")
        self.replace_edit.textChanged.connect(self._invalidate_preview)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(QLabel("→"))
        search_row.addWidget(self.replace_edit)
        rules_form.addRow("Search / replace", search_row)

        number_row = QHBoxLayout()
        self.numbering_check = QCheckBox("Sequential numbering")
        self.numbering_check.toggled.connect(self._on_numbering_toggled)
        self.number_start = QSpinBox()
        self.number_start.setRange(0, 999_999)
        self.number_start.setValue(1)
        self.number_start.setEnabled(False)
        self.number_start.valueChanged.connect(self._invalidate_preview)
        self.number_padding = QSpinBox()
        self.number_padding.setRange(1, 8)
        self.number_padding.setValue(3)
        self.number_padding.setEnabled(False)
        self.number_padding.valueChanged.connect(self._invalidate_preview)
        self.number_separator = QLineEdit("_")
        self.number_separator.setMaximumWidth(48)
        self.number_separator.setEnabled(False)
        self.number_separator.textChanged.connect(self._invalidate_preview)
        self.case_combo = QComboBox()
        self.case_combo.addItem("No change", CaseMode.NONE)
        self.case_combo.addItem("lowercase (stem)", CaseMode.LOWER)
        self.case_combo.addItem("UPPERCASE (stem)", CaseMode.UPPER)
        self.case_combo.addItem("Title Case (stem)", CaseMode.TITLE)
        self.case_combo.currentIndexChanged.connect(self._invalidate_preview)
        number_row.addWidget(self.numbering_check)
        number_row.addWidget(QLabel("Start"))
        number_row.addWidget(self.number_start)
        number_row.addWidget(QLabel("Pad"))
        number_row.addWidget(self.number_padding)
        number_row.addWidget(QLabel("Sep"))
        number_row.addWidget(self.number_separator)
        number_row.addWidget(QLabel("Case"))
        number_row.addWidget(self.case_combo, stretch=1)
        rules_form.addRow("Options", number_row)

        order_note = QLabel(f"Applied in order: {RULE_ORDER_DESCRIPTION}")
        order_note.setObjectName("MutedLabel")
        order_note.setWordWrap(True)
        order_note.setToolTip(
            "Rules always run in this fixed sequence so previews stay predictable."
        )
        rules_form.addRow("", order_note)
        layout.addWidget(rules_box)

        # --- Actions ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setObjectName("SecondaryButton")
        self.select_all_button.setEnabled(False)
        self.select_all_button.clicked.connect(self._select_all)
        actions.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setObjectName("SecondaryButton")
        self.clear_selection_button.setEnabled(False)
        self.clear_selection_button.clicked.connect(self._clear_selection)
        actions.addWidget(self.clear_selection_button)

        self.selection_label = QLabel("0 selected")
        self.selection_label.setObjectName("MutedLabel")
        actions.addWidget(self.selection_label)

        actions.addStretch(1)

        self.preview_button = QPushButton("Preview Renames")
        self.preview_button.setObjectName("PrimaryButton")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._start_preview)
        actions.addWidget(self.preview_button)

        self.apply_rename_button = QPushButton("Apply Renames")
        self.apply_rename_button.setEnabled(False)
        self.apply_rename_button.setObjectName("SecondaryButton")
        self.apply_rename_button.setToolTip(
            "Requires a conflict-free preview and explicit confirmation"
        )
        self.apply_rename_button.clicked.connect(self._confirm_and_apply)
        actions.addWidget(self.apply_rename_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel(
            "Choose a folder and load files. Preview is required before apply. "
            "Undo is not available in this milestone."
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
            title="No rename preview yet",
            body=(
                "Load files, select the ones to rename, configure rules, then "
                "click Preview Renames. Apply stays disabled until the plan is "
                "conflict-free and you confirm."
            ),
            badge="Preview before apply",
        )
        layout.addWidget(self.empty_state)

        self._file_model = RenameFileListModel(self)
        self.files_table = QTableView()
        self.files_table.setModel(self._file_model)
        configure_result_table(self.files_table, min_height=_FILES_TABLE_MIN_HEIGHT)
        self.files_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._configure_file_columns()
        self._file_model.dataChanged.connect(self._on_selection_changed)

        self._preview_model = RenamePreviewModel(self)
        self.preview_table = QTableView()
        self.preview_table.setModel(self._preview_model)
        configure_result_table(self.preview_table, min_height=_PREVIEW_TABLE_MIN_HEIGHT)
        self.preview_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._configure_preview_columns()

        files_pane = self._labeled_table_pane("File selection", self.files_table)
        preview_pane = self._labeled_table_pane("Rename preview", self.preview_table)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("RenamerSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(_SPLITTER_HANDLE)
        splitter.addWidget(files_pane)
        splitter.addWidget(preview_pane)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        # Floor both panes so the handle never has to crush either table.
        splitter.setMinimumHeight(
            _FILES_TABLE_MIN_HEIGHT + _PREVIEW_TABLE_MIN_HEIGHT + _SPLITTER_HANDLE + 48
        )
        splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        splitter.setVisible(False)
        self._splitter = splitter
        layout.addWidget(splitter, stretch=1)
        self._reset_splitter_sizes()

        self._controller.inventory_progress.connect(self._on_inventory_progress)
        self._controller.inventory_finished.connect(self._on_inventory_finished)
        self._controller.inventory_failed.connect(self._on_failed)
        self._controller.preview_finished.connect(self._on_preview_finished)
        self._controller.preview_failed.connect(self._on_failed)
        self._controller.execute_progress.connect(self._on_execute_progress)
        self._controller.execute_finished.connect(self._on_execute_finished)
        self._controller.execute_failed.connect(self._on_failed)
        self._controller.settled.connect(self._on_settled)

    @property
    def is_busy(self) -> bool:
        return self._controller.is_active

    def cancel_active_work(self, wait_ms: int = 8000) -> bool:
        if not self._controller.is_active:
            return True
        self._controller.cancel()
        return self._controller.wait_for_idle(wait_ms)

    @staticmethod
    def _labeled_table_pane(title: str, table: QTableView) -> QWidget:
        """Wrap a result table with a caption so panes stay identifiable when resized."""
        pane = QWidget()
        pane.setMinimumHeight(table.minimumHeight() + 28)
        pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        box = QVBoxLayout(pane)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        caption = QLabel(title)
        caption.setObjectName("SectionKicker")
        box.addWidget(caption)
        box.addWidget(table, stretch=1)
        return pane

    def _reset_splitter_sizes(self) -> None:
        """Apply a balanced initial split that respects both table floors."""
        total = max(self._splitter.height(), self._splitter.minimumHeight())
        # Prefer a slightly taller preview pane; both stay above their floors.
        files = max(_FILES_TABLE_MIN_HEIGHT + 28, int(total * 0.40))
        preview = max(_PREVIEW_TABLE_MIN_HEIGHT + 28, total - files - _SPLITTER_HANDLE)
        if preview < _PREVIEW_TABLE_MIN_HEIGHT + 28:
            preview = _PREVIEW_TABLE_MIN_HEIGHT + 28
            files = max(_FILES_TABLE_MIN_HEIGHT + 28, total - preview - _SPLITTER_HANDLE)
        self._splitter.setSizes([files, preview])

    def _configure_file_columns(self) -> None:
        header = self.files_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    def _configure_preview_columns(self) -> None:
        header = self.preview_table.horizontalHeader()
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

    def _choose_folder(self) -> None:
        if self._controller.is_active:
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder for bulk rename")
        if not chosen:
            return
        self._folder = Path(chosen)
        self.folder_label.setText(str(self._folder))
        self.load_button.setEnabled(True)
        self._invalidate_preview()
        self._file_model.clear()
        self._preview_model.clear()
        self._splitter.setVisible(False)
        self.empty_state.setVisible(True)
        self.status_label.setText("Folder selected. Click Load Files to inventory.")
        self._update_selection_label()

    def _current_rules(self) -> RenameRules:
        return RenameRules(
            prefix=self.prefix_edit.text(),
            suffix=self.suffix_edit.text(),
            search=self.search_edit.text(),
            replace=self.replace_edit.text(),
            numbering_enabled=self.numbering_check.isChecked(),
            number_start=self.number_start.value(),
            number_padding=self.number_padding.value(),
            number_separator=self.number_separator.text(),
            case_mode=self.case_combo.currentData(),
        )

    def _on_numbering_toggled(self, checked: bool) -> None:
        self.number_start.setEnabled(checked)
        self.number_padding.setEnabled(checked)
        self.number_separator.setEnabled(checked)
        self._invalidate_preview()

    def _invalidate_preview(self, *_args: object) -> None:
        self._plan = None
        self._preview_valid = False
        self.apply_rename_button.setEnabled(False)
        self.preview_button.setEnabled(
            self._folder is not None
            and self._file_model.selected_count() > 0
            and not self._controller.is_active
        )

    def _on_selection_changed(self, *_args: object) -> None:
        self._update_selection_label()
        self._invalidate_preview()

    def _update_selection_label(self) -> None:
        total = self._file_model.rowCount()
        selected = self._file_model.selected_count()
        self.selection_label.setText(f"{selected} of {total} selected")

    def _select_all(self) -> None:
        self._file_model.select_all()
        self._update_selection_label()
        self._invalidate_preview()

    def _clear_selection(self) -> None:
        self._file_model.clear_selection()
        self._update_selection_label()
        self._invalidate_preview()

    def _start_inventory(self) -> None:
        if self._folder is None or self._controller.is_active:
            return
        self._plan = None
        self._preview_valid = False
        self._preview_model.clear()
        self.apply_rename_button.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Loading files… {self._folder}")
        self._set_busy_ui(True)
        try:
            self._controller.start_inventory(
                self._folder, recursive=self.recursive_check.isChecked()
            )
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot load files", str(exc))

    def _start_preview(self) -> None:
        if self._folder is None or self._controller.is_active:
            return
        selected = self._file_model.selected_paths()
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select at least one file.")
            return
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Building rename preview…")
        self._set_busy_ui(True)
        try:
            self._controller.start_preview(
                self._folder,
                selected,
                self._current_rules(),
                recursive=self.recursive_check.isChecked(),
            )
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot preview", str(exc))

    def _confirm_and_apply(self) -> None:
        if (
            self._plan is None
            or not self._preview_valid
            or not self._plan.can_apply
            or self._controller.is_active
        ):
            return
        count = len(self._plan.ready_items)
        answer = QMessageBox.question(
            self,
            "Confirm bulk rename",
            (
                f"Rename {count} file(s) as shown in the preview?\n\n"
                "This cannot be undone from Junction in this milestone.\n"
                "Existing files will never be overwritten."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.progress_bar.setRange(0, max(count, 1))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Applying renames…")
        self._set_busy_ui(True)
        try:
            self._controller.start_execute(self._plan, self._database.path)
        except RuntimeError as exc:
            self._set_busy_ui(False)
            self.progress_bar.setVisible(False)
            QMessageBox.warning(self, "Cannot apply", str(exc))

    def _cancel(self) -> None:
        if self._controller.is_active:
            self.status_label.setText("Cancelling…")
            self._controller.cancel()

    def _on_inventory_progress(self, progress) -> None:
        self.status_label.setText(
            f"Loading files… {progress.files_seen} seen"
            + (f"  |  {progress.current_path}" if progress.current_path else "")
        )

    def _on_inventory_finished(self, files: list) -> None:
        assert self._folder is not None
        self._file_model.set_files(list(files), root=self._folder)
        self._file_model.select_all()
        self._update_selection_label()
        self._splitter.setVisible(True)
        self.empty_state.setVisible(False)
        self._reset_splitter_sizes()
        self.select_all_button.setEnabled(True)
        self.clear_selection_button.setEnabled(True)
        self.status_label.setText(
            f"Loaded {len(files)} file(s). Select files and click Preview Renames."
        )
        self.summary_label.setVisible(False)
        self._invalidate_preview()

    def _on_preview_finished(self, plan: RenamePlan) -> None:
        self._plan = plan
        self._preview_valid = plan.status in {
            RenamePlanStatus.READY,
            RenamePlanStatus.BLOCKED,
            RenamePlanStatus.EMPTY,
        }
        self._preview_model.set_items(plan.items)
        self._splitter.setVisible(True)
        self.empty_state.setVisible(False)
        self._reset_splitter_sizes()

        ready = sum(1 for i in plan.items if i.status == RenameItemStatus.READY)
        unchanged = plan.unchanged_count
        conflicts = len(plan.conflict_items)
        self.status_label.setText(plan.status.name.replace("_", " ").title())
        self.summary_label.setText(
            f"{len(plan.items)} selected · {ready} ready · "
            f"{unchanged} unchanged · {conflicts} conflicts/invalid"
        )
        self.summary_label.setToolTip(plan.message)
        self.summary_label.setVisible(True)
        self.apply_rename_button.setEnabled(bool(plan.can_apply))

    def _on_execute_progress(self, progress: RenameProgress) -> None:
        if progress.total > 0:
            self.progress_bar.setRange(0, progress.total)
            self.progress_bar.setValue(progress.completed)
        self.status_label.setText(
            f"{progress.phase.title()}… {progress.completed}/{progress.total}"
            + (f"  |  {progress.current_path}" if progress.current_path else "")
        )

    def _on_execute_finished(self, result: RenameExecutionResult) -> None:
        self._plan = None
        self._preview_valid = False
        self.apply_rename_button.setEnabled(False)
        self._preview_model.set_items(result.items)
        self.status_label.setText(result.status.name.replace("_", " ").title())
        self.summary_label.setText(result.message)
        self.summary_label.setVisible(True)
        # Refresh inventory after successful or partial apply so names match disk.
        self._pending_reload = result.status in {
            RenamePlanStatus.COMPLETED,
            RenamePlanStatus.PARTIAL,
        }

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(message)
        self.summary_label.setVisible(False)
        QMessageBox.critical(self, "Bulk Renamer error", message)

    def _on_settled(self) -> None:
        self.progress_bar.setVisible(False)
        self._set_busy_ui(False)
        if getattr(self, "_pending_reload", False) and self._folder is not None:
            self._pending_reload = False
            self._start_inventory()

    def _set_busy_ui(self, busy: bool) -> None:
        self.choose_folder_button.setEnabled(not busy)
        self.recursive_check.setEnabled(not busy)
        self.load_button.setEnabled(not busy and self._folder is not None)
        self.select_all_button.setEnabled(not busy and self._file_model.rowCount() > 0)
        self.clear_selection_button.setEnabled(
            not busy and self._file_model.rowCount() > 0
        )
        for widget in (
            self.prefix_edit,
            self.suffix_edit,
            self.search_edit,
            self.replace_edit,
            self.numbering_check,
            self.case_combo,
        ):
            widget.setEnabled(not busy)
        numbering = self.numbering_check.isChecked() and not busy
        self.number_start.setEnabled(numbering)
        self.number_padding.setEnabled(numbering)
        self.number_separator.setEnabled(numbering)
        self.preview_button.setEnabled(
            not busy
            and self._folder is not None
            and self._file_model.selected_count() > 0
        )
        self.apply_rename_button.setEnabled(
            not busy and self._preview_valid and self._plan is not None and self._plan.can_apply
        )
        self.cancel_button.setEnabled(busy)
        self.files_table.setEnabled(not busy)
