"""Background worker for read-only duplicate detection."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from fileforge.services.duplicates import DuplicateFinder, DuplicateStatus


class _DuplicateWorker(QObject):
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
        finder = DuplicateFinder()
        try:
            result = finder.find(
                self._root,
                recursive=self._recursive,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=lambda progress: self.progress.emit(progress),
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unexpected duplicate scan failure: {exc}")
            return
        self.finished.emit(result)


class DuplicateWorkerController(QObject):
    """Owns the duplicate-detection worker thread lifecycle."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    started = Signal()
    settled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _DuplicateWorker | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self, root: Path | str, *, recursive: bool = True) -> None:
        if self._active:
            raise RuntimeError("A duplicate scan is already in progress.")
        self._cleanup_thread()
        thread = QThread(self)
        worker = _DuplicateWorker(Path(root), recursive)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress.emit)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._active = True
        self.started.emit()
        thread.start()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def wait_for_idle(self, timeout_ms: int = 8000) -> bool:
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

    def _on_finished(self, result) -> None:
        self.finished.emit(result)

    def _on_failed(self, message: str) -> None:
        self.failed.emit(message)

    def _on_thread_finished(self) -> None:
        self._active = False
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


def summarize_duplicate_result(result) -> str:
    status_labels = {
        DuplicateStatus.COMPLETED: "Completed",
        DuplicateStatus.CANCELLED: "Cancelled",
        DuplicateStatus.PARTIAL: "Completed with issues",
        DuplicateStatus.FAILED: "Failed",
        DuplicateStatus.EMPTY: "No duplicates",
    }
    label = status_labels.get(result.status, result.status.name.title())
    return (
        f"{label}: {result.group_count} group(s), "
        f"{result.duplicate_copy_count} path(s) under {result.root}"
    )
