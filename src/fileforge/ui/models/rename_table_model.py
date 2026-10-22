"""Table models for bulk renamer file selection and preview."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from fileforge.services.organizer.paths import relative_display_path
from fileforge.services.renamer import RenameItem, RenameItemStatus

_STATUS_COLORS = {
    RenameItemStatus.READY: QColor("#0F7B3A"),
    RenameItemStatus.UNCHANGED: QColor("#486581"),
    RenameItemStatus.CONFLICT: QColor("#B42318"),
    RenameItemStatus.INVALID: QColor("#B42318"),
    RenameItemStatus.MISSING: QColor("#B54708"),
    RenameItemStatus.STALE: QColor("#B54708"),
    RenameItemStatus.FAILED: QColor("#B42318"),
    RenameItemStatus.SUCCESS: QColor("#0F7B3A"),
    RenameItemStatus.CANCELLED: QColor("#B54708"),
}

FILE_COLUMNS = ("Selected", "Name", "Folder")
PREVIEW_COLUMNS = ("Original", "Proposed", "Folder", "Status", "Notes")


class RenameFileListModel(QAbstractTableModel):
    """Selectable inventory of files under the chosen folder."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._files: list[Path] = []
        self._selected: set[str] = set()  # casefold absolute paths
        self._root: Path | None = None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._files)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(FILE_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(FILE_COLUMNS)
        ):
            return FILE_COLUMNS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._files)):
            return None
        path = self._files[index.row()]
        column = index.column()
        key = str(path).casefold()

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return (
                Qt.CheckState.Checked
                if key in self._selected
                else Qt.CheckState.Unchecked
            )

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return ""
            if column == 1:
                return path.name
            if column == 2:
                return relative_display_path(path.parent, self._root) if self._root else str(path.parent)
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return str(path)

        if role == Qt.ItemDataRole.UserRole:
            return path
        return None

    def setData(  # noqa: N802
        self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid() or index.column() != 0:
            return False
        if role != Qt.ItemDataRole.CheckStateRole:
            return False
        path = self._files[index.row()]
        key = str(path).casefold()
        if value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked:
            self._selected.add(key)
        else:
            self._selected.discard(key)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def set_files(self, files: list[Path], *, root: Path | None = None) -> None:
        self.beginResetModel()
        self._files = list(files)
        self._root = root
        valid = {str(path).casefold() for path in self._files}
        self._selected = {key for key in self._selected if key in valid}
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._files.clear()
        self._selected.clear()
        self._root = None
        self.endResetModel()

    def select_all(self) -> None:
        self._selected = {str(path).casefold() for path in self._files}
        if self._files:
            top = self.index(0, 0)
            bottom = self.index(len(self._files) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])

    def clear_selection(self) -> None:
        self._selected.clear()
        if self._files:
            top = self.index(0, 0)
            bottom = self.index(len(self._files) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])

    def selected_paths(self) -> list[Path]:
        selected: list[Path] = []
        for path in self._files:
            if str(path).casefold() in self._selected:
                selected.append(path)
        return selected

    def selected_count(self) -> int:
        return len(self._selected)


class RenamePreviewModel(QAbstractTableModel):
    """One row per previewed rename item."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[RenameItem] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(PREVIEW_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(PREVIEW_COLUMNS)
        ):
            return PREVIEW_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return item.source.name
            if column == 1:
                return item.proposed_name
            if column == 2:
                return item.relative_folder
            if column == 3:
                return item.status.name.title()
            if column == 4:
                return item.conflict_reason or item.error_message or item.rule_summary
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"Source: {item.source}\n"
                f"Destination: {item.destination}\n"
                f"Status: {item.status.name}\n"
                f"Rules: {item.rule_summary}\n"
                f"{item.conflict_reason or item.error_message or ''}"
            ).strip()

        if role == Qt.ItemDataRole.UserRole:
            return item

        if role == Qt.ItemDataRole.ForegroundRole and column == 3:
            return _STATUS_COLORS.get(item.status)
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def set_items(self, items: list[RenameItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()
