"""Table model and filter proxy for scan results."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from fileforge.services.scanner import (
    EntryKind,
    ScanEntry,
    format_byte_size,
    format_timestamp,
)

_KIND_LABELS = {
    EntryKind.FILE: "File",
    EntryKind.DIRECTORY: "Folder",
    EntryKind.SYMLINK: "Symlink",
    EntryKind.JUNCTION: "Junction",
    EntryKind.OTHER: "Other",
}

COLUMNS = (
    "Name",
    "Type",
    "Extension",
    "Size",
    "Modified",
    "Relative path",
)


class ScanTableModel(QAbstractTableModel):
    """In-memory table of ``ScanEntry`` rows."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[ScanEntry] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._entries)

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
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return None
        entry = self._entries[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return entry.name
            if column == 1:
                return _KIND_LABELS.get(entry.kind, entry.kind.name.title())
            if column == 2:
                return entry.extension or "-"
            if column == 3:
                if entry.kind == EntryKind.FILE:
                    return format_byte_size(entry.size_bytes)
                return "-"
            if column == 4:
                return format_timestamp(entry.modified_at)
            if column == 5:
                return entry.relative_path
            return None

        if role == Qt.ItemDataRole.UserRole:
            # Raw values for sorting.
            if column == 0:
                return entry.name.lower()
            if column == 1:
                return _KIND_LABELS.get(entry.kind, "")
            if column == 2:
                return entry.extension
            if column == 3:
                return entry.size_bytes if entry.kind == EntryKind.FILE else -1
            if column == 4:
                return entry.modified_at.timestamp() if entry.modified_at else 0.0
            if column == 5:
                return entry.relative_path.lower()
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            return str(entry.path)

        if role == Qt.ItemDataRole.TextAlignmentRole and column == 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._entries.clear()
        self.endResetModel()

    def set_entries(self, entries: list[ScanEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entries(self) -> list[ScanEntry]:
        return list(self._entries)


class ScanFilterProxyModel(QSortFilterProxyModel):
    """Filter scan rows by name/path text and optional extension."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._name_query = ""
        self._extension = ""  # empty means all; special "*" for files with any ext
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_name_query(self, query: str) -> None:
        self._name_query = query.strip().lower()
        self.invalidateFilter()

    def set_extension_filter(self, extension: str) -> None:
        self._extension = extension.strip().lower().lstrip(".")
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return False
        index0 = model.index(source_row, 0, source_parent)
        entry_name = str(model.data(index0, Qt.ItemDataRole.DisplayRole) or "")
        relative = str(
            model.data(model.index(source_row, 5, source_parent), Qt.ItemDataRole.DisplayRole)
            or ""
        )
        extension = str(
            model.data(model.index(source_row, 2, source_parent), Qt.ItemDataRole.DisplayRole)
            or ""
        )
        kind = str(
            model.data(model.index(source_row, 1, source_parent), Qt.ItemDataRole.DisplayRole)
            or ""
        )

        if self._name_query:
            haystack = f"{entry_name} {relative}".lower()
            if self._name_query not in haystack:
                return False

        if self._extension:
            if self._extension == "__files__":
                return kind == "File"
            if self._extension == "__folders__":
                return kind == "Folder"
            if extension.lower().lstrip(".") != self._extension:
                return False

        return True
