"""Background workers for organization preview and execution."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from fileforge.database.connection import DatabaseManager
from fileforge.database.journal import OperationJournal
from fileforge.services.organizer import (
    OrganizeExecutor,
    OrganizeMode,
    OrganizePlanner,
)
from fileforge.services.scanner import ScanProgress


class _PreviewWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        source: Path,
        destination: Path,
        mode: OrganizeMode,
        recursive: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._destination = destination
        self._mode = mode
        self._recursive = recursive
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        planner = OrganizePlanner()
        try:
            plan = planner.build_plan(
                self._source,
                self._destination,
                mode=self._mode,
                recursive=self._recursive,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=self._emit_progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to build organization preview: {exc}")
            return
        self.finished.emit(plan)

    def _emit_progress(self, progress: ScanProgress) -> None:
        self.progress.emit(progress)


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
            executor = OrganizeExecutor(journal)
            result = executor.execute(
                self._plan,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=lambda progress: self.progress.emit(progress),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to apply organization plan: {exc}")
            return
        finally:
            if database is not None:
                database.close()
        self.finished.emit(result)


class OrganizeWorkerController(QObject):
    """Owns preview/execute worker threads for the Organizer page."""

    preview_progress = Signal(object)
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

    def start_preview(
        self,
        source: Path | str,
        destination: Path | str,
        *,
        mode: OrganizeMode,
        recursive: bool,
    ) -> None:
        if self._active:
            raise RuntimeError("An organizer operation is already running.")
        self._cleanup_thread()
        thread = QThread(self)
        worker = _PreviewWorker(Path(source), Path(destination), mode, recursive)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.preview_progress.emit)
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
            raise RuntimeError("An organizer operation is already running.")
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
        worker = self._worker
        if worker is not None and hasattr(worker, "request_cancel"):
            worker.request_cancel()

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
