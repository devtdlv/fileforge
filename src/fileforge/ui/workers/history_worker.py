"""Background loader for read-only Operation History batch lists."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from fileforge.services.history import (
    BatchListResult,
    HistoryFilters,
    HistoryQueryService,
)


class _HistoryLoadWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        database_path: Path,
        filters: HistoryFilters,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._filters = filters
        self._cancel_requested = False

    @Slot()
    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        manager = None
        try:
            if self._cancel_requested:
                self.finished.emit(
                    BatchListResult(filters=self._filters, message="Load cancelled.")
                )
                return
            service, manager = HistoryQueryService.open(self._database_path)
            if self._cancel_requested:
                self.finished.emit(
                    BatchListResult(filters=self._filters, message="Load cancelled.")
                )
                return
            result = service.list_batches(self._filters)
            if self._cancel_requested:
                self.finished.emit(
                    BatchListResult(filters=self._filters, message="Load cancelled.")
                )
                return
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unable to load operation history: {exc}")
        finally:
            if manager is not None:
                manager.close()


class HistoryWorkerController(QObject):
    """Owns short-lived history query threads (own SQLite connections)."""

    list_finished = Signal(object)
    failed = Signal(str)
    settled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _HistoryLoadWorker | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def load_batches(self, database_path: Path | str, filters: HistoryFilters) -> None:
        if self._active:
            self.cancel()
            self.wait_for_idle(2000)
        self._cleanup_thread()
        thread = QThread(self)
        worker = _HistoryLoadWorker(Path(database_path), filters)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.list_finished.emit)
        worker.failed.connect(self.failed.emit)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._active = True
        thread.start()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def wait_for_idle(self, timeout_ms: int = 5000) -> bool:
        thread = self._thread
        if thread is None or not thread.isRunning():
            self._active = False
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
        return True

    def _on_thread_finished(self) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._thread:
            return
        self._active = False
        self._worker = None
        self._thread = None
        self.settled.emit()

    def _cleanup_thread(self) -> None:
        thread = self._thread
        if thread is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                thread.finished.disconnect(self._on_thread_finished)
            if thread.isRunning():
                self.cancel()
                thread.quit()
                thread.wait(2000)
        self._thread = None
        self._worker = None
        self._active = False
