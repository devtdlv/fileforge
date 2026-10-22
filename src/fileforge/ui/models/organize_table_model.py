"""Table model for organization preview / result rows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from fileforge.services.organizer import PlanItem, PlanItemStatus
from fileforge.services.organizer.paths import relative_display_path

COLUMNS = ("Status", "Source", "Destination", "Rule", "Notes")

_STATUS_LABELS = {
    PlanItemStatus.READY: "Ready",
    PlanItemStatus.CONFLICT: "Conflict",
    PlanItemStatus.SKIPPED: "Skipped",
    PlanItemStatus.INVALID: "Invalid",
    PlanItemStatus.SUCCESS: "Moved",
    PlanItemStatus.FAILED: "Failed",
    PlanItemStatus.CANCELLED: "Cancelled",
}

_STATUS_COLORS = {
    PlanItemStatus.READY: QColor("#0F7B3A"),
    PlanItemStatus.SUCCESS: QColor("#0F7B3A"),
    PlanItemStatus.CONFLICT: QColor("#B42318"),
    PlanItemStatus.INVALID: QColor("#B42318"),
    PlanItemStatus.FAILED: QColor("#B42318"),
    PlanItemStatus.SKIPPED: QColor("#486581"),
    PlanItemStatus.CANCELLED: QColor("#B54708"),
}


class OrganizeTableModel(QAbstractTableModel):
    """Displays planned or executed organization items.

    Source/Destination columns show paths relative to the selected roots.
    Absolute paths remain on each ``PlanItem`` and are exposed via tooltips
    and ``Qt.ItemDataRole.UserRole``.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[PlanItem] = []
        self._source_root: Path | None = None
        self._destination_root: Path | None = None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(COLUMNS)
        ):
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return _STATUS_LABELS.get(item.status, item.status.name.title())
            if column == 1:
                return relative_display_path(item.source, self._source_root)
            if column == 2:
                return relative_display_path(item.destination, self._destination_root)
            if column == 3:
                return item.rule
            if column == 4:
                return item.error_message or item.conflict_reason
            return None

        if role == Qt.ItemDataRole.UserRole:
            if column == 1:
                return str(item.source)
            if column == 2:
                return str(item.destination)
            if column == 0:
                return item.status.name
            return None

        if role == Qt.ItemDataRole.ForegroundRole and column == 0:
            return _STATUS_COLORS.get(item.status)

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 1:
                return f"Full source path:\n{item.source}"
            if column == 2:
                return f"Full destination path:\n{item.destination}"
            note = item.error_message or item.conflict_reason or item.rule
            return (
                f"Source: {item.source}\n"
                f"Destination: {item.destination}\n"
                f"{note}"
            )

        if role == Qt.ItemDataRole.AccessibleTextRole:
            if column == 1:
                return (
                    f"Source {relative_display_path(item.source, self._source_root)}; "
                    f"full path {item.source}"
                )
            if column == 2:
                return (
                    f"Destination {relative_display_path(item.destination, self._destination_root)}; "
                    f"full path {item.destination}"
                )
            return None

        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self._source_root = None
        self._destination_root = None
        self.endResetModel()

    def set_items(
        self,
        items: list[PlanItem],
        *,
        source_root: Path | str | None = None,
        destination_root: Path | str | None = None,
    ) -> None:
        self.beginResetModel()
        self._items = list(items)
        self._source_root = Path(source_root) if source_root is not None else None
        self._destination_root = (
            Path(destination_root) if destination_root is not None else None
        )
        self.endResetModel()

    def items(self) -> list[PlanItem]:
        """Return the underlying plan items (absolute paths unchanged)."""
        return list(self._items)
