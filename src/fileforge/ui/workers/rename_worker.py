"""Background workers for bulk rename inventory, preview, and execution."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from fileforge.database.connection import DatabaseManager
from fileforge.database.journal import OperationJournal
from fileforge.services.renamer import (
    RenameExecutor,
    RenamePlanner,
    RenameRules,
)


class _InventoryWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, root: Path, recursive: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root
        self._recursive = recursive
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        planner = RenamePlanner()
        try:
            files = planner.inventory(
                self._root,
                recursive=self._recursive,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=lambda progress: self.progress.emit(progress),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to load files: {exc}")
            return
        self.finished.emit(files)


class _PreviewWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        root: Path,
        selected: list[Path],
        rules: RenameRules,
        recursive: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._root = root
        self._selected = selected
        self._rules = rules
        self._recursive = recursive
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        if self._cancel_requested:
            from fileforge.services.renamer import RenamePlan, RenamePlanStatus

            plan = RenamePlan(
                root=self._root,
                recursive=self._recursive,
                rules=self._rules,
                status=RenamePlanStatus.CANCELLED,
                message="Preview cancelled.",
            )
            self.finished.emit(plan)
            return
        planner = RenamePlanner()
        try:
            plan = planner.build_plan(
                self._root,
                self._selected,
                self._rules,
                recursive=self._recursive,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to build rename preview: {exc}")
            return
        self.finished.emit(plan)


class _ExecuteWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        plan,
        database_path: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._plan = plan
        self._database_path = database_path
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        database: DatabaseManager | None = None
        try:
            database = DatabaseManager(self._database_path)
            database.initialize()
            journal = OperationJournal(database)
            executor = RenameExecutor(journal)
            result = executor.execute(
                self._plan,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=lambda progress: self.progress.emit(progress),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to apply rename plan: {exc}")
            return
        finally:
            if database is not None:
                database.close()
        self.finished.emit(result)


class RenameWorkerController(QObject):
    """Owns inventory/preview/execute worker threads for the Bulk Renamer page."""

    inventory_progress = Signal(object)
    inventory_finished = Signal(object)
    inventory_failed = Signal(str)
    preview_finished = Signal(object)
    preview_failed = Signal(str)
    execute_progress = Signal(object)
    execute_finished = Signal(object)
    execute_failed = Signal(str)
    settled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._active = False
        self._mode = "idle"

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def active_mode(self) -> str:
        return self._mode

    def start_inventory(self, root: Path | str, *, recursive: bool) -> None:
        if self._active:
            raise RuntimeError("A rename operation is already running.")
        self._cleanup_thread()
        thread = QThread(self)
        worker = _InventoryWorker(Path(root), recursive)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.inventory_progress.emit)
        worker.finished.connect(self.inventory_finished.emit)
        worker.failed.connect(self.inventory_failed.emit)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._active = True
        self._mode = "inventory"
        thread.start()

    def start_preview(
        self,
        root: Path | str,
        selected: list[Path],
        rules: RenameRules,
        *,
        recursive: bool,
    ) -> None:
        if self._active:
            raise RuntimeError("A rename operation is already running.")
        self._cleanup_thread()
        thread = QThread(self)
        worker = _PreviewWorker(Path(root), list(selected), rules, recursive)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.preview_finished.emit)
        worker.failed.connect(self.preview_failed.emit)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._active = True
        self._mode = "preview"
        thread.start()

    def start_execute(self, plan, database_path: Path | str) -> None:
        if self._active:
            raise RuntimeError("A rename operation is already running.")
        self._cleanup_thread()
        thread = QThread(self)
        worker = _ExecuteWorker(plan, Path(database_path))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.execute_progress.emit)
        worker.finished.connect(self.execute_finished.emit)
        worker.failed.connect(self.execute_failed.emit)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._active = True
        self._mode = "execute"
        thread.start()

    def cancel(self) -> None:
        if self._worker is not None and hasattr(self._worker, "request_cancel"):
            self._worker.request_cancel()

    def wait_for_idle(self, timeout_ms: int = 8000) -> bool:
        thread = self._thread
        if thread is None or not thread.isRunning():
            self._active = False
            self._mode = "idle"
            return True
        self.cancel()
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while thread.isRunning():
            QCoreApplication.processEvents()
            if thread.wait(50):
                break
            if time.monotonic() >= deadline:
                return False
        self._active = False
        self._mode = "idle"
        return True

    def _on_thread_finished(self) -> None:
        self._active = False
        self._mode = "idle"
        self._worker = None
        self._thread = None
        self.settled.emit()

    def _cleanup_thread(self) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            self.cancel()
            thread.quit()
            thread.wait(2000)
        self._thread = None
        self._worker = None
        self._active = False
        self._mode = "idle"
