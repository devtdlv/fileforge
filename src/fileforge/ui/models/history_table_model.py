"""Table models for Operation History batches and entries."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from fileforge.services.history import BatchSummary, EntrySummary

BATCH_COLUMNS = (
    "When",
    "Type",
    "Status",
    "Files",
    "Succeeded",
    "Failed",
    "Pending",
    "Source",
    "Destination",
)

ENTRY_COLUMNS = (
    "Original",
    "Destination",
    "Operation",
    "Outcome",
    "Error",
    "Completed",
)


def _format_local_timestamp(value: str) -> str:
    """Format an ISO UTC timestamp for local display; pass through if unparsable."""
    if not value:
        return ""
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            # Journal writes UTC ISO timestamps; treat naive values as UTC.
            dt = dt.replace(tzinfo=UTC)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return value


def _short_path(path: str, max_len: int = 48) -> str:
    if not path:
        return ""
    if len(path) <= max_len:
        return path
    name = Path(path).name
    if name and len(name) < max_len - 3:
        return f"…/{name}"
    return "…" + path[-(max_len - 1) :]


class HistoryBatchModel(QAbstractTableModel):
    """One row per operation batch."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._batches: list[BatchSummary] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._batches)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(BATCH_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(BATCH_COLUMNS)
        ):
            return BATCH_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._batches)):
            return None
        batch = self._batches[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return _format_local_timestamp(batch.created_at)
            if column == 1:
                return batch.operation_label
            if column == 2:
                return batch.status_label
            if column == 3:
                return str(batch.entry_total)
            if column == 4:
                return str(batch.entry_success)
            if column == 5:
                return str(batch.entry_failed)
            if column == 6:
                return str(batch.entry_pending)
            if column == 7:
                return _short_path(batch.source_root)
            if column == 8:
                return _short_path(batch.destination_root)
            return None

        if role == Qt.ItemDataRole.UserRole:
            if column == 0:
                return batch.created_at
            if column in {3, 4, 5, 6}:
                return (
                    batch.entry_total,
                    batch.entry_success,
                    batch.entry_failed,
                    batch.entry_pending,
                )[column - 3]
            return batch

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"Batch ID: {batch.batch_id}\n"
                f"When: {_format_local_timestamp(batch.created_at)}\n"
                f"Completed: {_format_local_timestamp(batch.completed_at) or '(n/a)'}\n"
                f"Type: {batch.operation_label} ({batch.operation_type})\n"
                f"Status: {batch.status_label}\n"
                f"Mode: {batch.mode or '(n/a)'}\n"
                f"Summary: {batch.summary or '(none)'}\n"
                f"Source: {batch.source_root or '(none)'}\n"
                f"Destination: {batch.destination_root or '(none)'}\n"
                f"Entries: {batch.entry_total} "
                f"(succeeded {batch.entry_success}, failed {batch.entry_failed}, "
                f"pending {batch.entry_pending})"
            )

        if role == Qt.ItemDataRole.TextAlignmentRole and column in {3, 4, 5, 6}:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._batches.clear()
        self.endResetModel()

    def set_batches(self, batches: list[BatchSummary]) -> None:
        self.beginResetModel()
        self._batches = list(batches)
        self.endResetModel()

    def batch_at(self, row: int) -> BatchSummary | None:
        if 0 <= row < len(self._batches):
            return self._batches[row]
        return None


class HistoryEntryModel(QAbstractTableModel):
    """One row per journal entry in the selected batch."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[EntrySummary] = []
        self._source_root: str = ""
        self._destination_root: str = ""

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(ENTRY_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(ENTRY_COLUMNS)
        ):
            return ENTRY_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        entry = self._entries[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return self._relative_or_name(entry.source_path, self._source_root)
            if column == 1:
                return self._relative_or_name(
                    entry.destination_path, self._destination_root or self._source_root
                )
            if column == 2:
                return entry.operation_label
            if column == 3:
                return entry.status_label
            if column == 4:
                return entry.error_details
            if column == 5:
                return _format_local_timestamp(entry.completed_at or entry.created_at)
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"Source: {entry.source_path}\n"
                f"Destination: {entry.destination_path}\n"
                f"Operation: {entry.operation_label}\n"
                f"Outcome: {entry.status_label}\n"
                f"Error: {entry.error_details or '(none)'}\n"
                f"Created: {_format_local_timestamp(entry.created_at)}\n"
                f"Completed: {_format_local_timestamp(entry.completed_at) or '(n/a)'}"
            )

        if role == Qt.ItemDataRole.UserRole:
            return entry
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._entries.clear()
        self._source_root = ""
        self._destination_root = ""
        self.endResetModel()

    def set_entries(
        self,
        entries: list[EntrySummary],
        *,
        source_root: str = "",
        destination_root: str = "",
    ) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self._source_root = source_root
        self._destination_root = destination_root
        self.endResetModel()

    @staticmethod
    def _relative_or_name(path: str, root: str) -> str:
        if not path:
            return ""
        try:
            if root:
                rel = Path(path)
                try:
                    return rel.relative_to(Path(root)).as_posix()
                except ValueError:
                    pass
        except (OSError, TypeError, ValueError):
            pass
        return Path(path).name or path
