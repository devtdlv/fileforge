"""Background folder-scan worker using QObject + QThread."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from fileforge.services.scanner import (
    FolderScanner,
    ScanProgress,
    ScanResult,
    ScanStatus,
)


class _ScanWorker(QObject):
    """Runs ``FolderScanner`` off the GUI thread."""

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
        scanner = FolderScanner()
        try:
            result = scanner.scan(
                self._root,
                recursive=self._recursive,
                cancel_check=lambda: self._cancel_requested,
                progress_callback=self._emit_progress,
            )
        except Exception as exc:  # noqa: BLE001 - surface unexpected failures to UI
            self.failed.emit(f"Unexpected scan failure: {exc}")
            return
        self.finished.emit(result)

    def _emit_progress(self, progress: ScanProgress) -> None:
        self.progress.emit(progress)


class ScanWorkerController(QObject):
    """Owns the worker thread lifecycle for a single scan job."""

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    started = Signal()
    settled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _ScanWorker | None = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self, root: Path | str, *, recursive: bool = True) -> None:
        """Start a scan. Raises ``RuntimeError`` if a scan is already active."""
        if self._active:
            raise RuntimeError("A scan is already in progress.")

        self._cleanup_thread()
        thread = QThread(self)
        worker = _ScanWorker(Path(root), recursive)
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
        """Request cooperative cancellation of the active scan."""
        if self._worker is not None:
            self._worker.request_cancel()

    def wait_for_idle(self, timeout_ms: int = 5000) -> bool:
        """Wait until the worker thread finishes (for shutdown).

        Processes Qt events while waiting so queued worker signals can settle
        on the GUI thread without deadlocking.
        """
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

    def _on_finished(self, result: ScanResult) -> None:
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


def summarize_scan_result(result: ScanResult) -> str:
    """Build a short human-readable summary for dashboard/status use."""
    status_labels = {
        ScanStatus.COMPLETED: "Completed",
        ScanStatus.CANCELLED: "Cancelled",
        ScanStatus.PARTIAL: "Completed with issues",
        ScanStatus.FAILED: "Failed",
    }
    label = status_labels.get(result.status, result.status.name.title())
    return (
        f"{label}: {result.file_count} file(s), "
        f"{result.directory_count} folder(s), "
        f"{len(result.errors)} issue(s) under {result.root}"
    )
