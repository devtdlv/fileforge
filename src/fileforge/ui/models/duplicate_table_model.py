"""Table models for duplicate groups and member files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from fileforge.services.duplicates import DuplicateFile, DuplicateGroup
from fileforge.services.scanner import format_byte_size

GROUP_COLUMNS = ("Copies", "Size", "Potential savings", "SHA-256", "Example path")
MEMBER_COLUMNS = ("Path", "Physical file", "Size")


class DuplicateGroupModel(QAbstractTableModel):
    """One row per duplicate content group."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._groups: list[DuplicateGroup] = []
        self._root: Path | None = None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._groups)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(GROUP_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(GROUP_COLUMNS)
        ):
            return GROUP_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._groups)):
            return None
        group = self._groups[index.row()]
        column = index.column()
        example = group.files[0].relative_path if group.files else ""

        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return str(group.path_count)
            if column == 1:
                return format_byte_size(group.size_bytes)
            if column == 2:
                return format_byte_size(group.potential_savings_bytes)
            if column == 3:
                return f"{group.sha256[:12]}…"
            if column == 4:
                return example
            return None

        if role == Qt.ItemDataRole.UserRole:
            if column == 0:
                return group.path_count
            if column == 1:
                return group.size_bytes
            if column == 2:
                return group.potential_savings_bytes
            if column == 3:
                return group.sha256
            if column == 4:
                return example.lower()
            return group

        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"SHA-256: {group.sha256}\n"
                f"Copies (paths): {group.path_count}\n"
                f"Unique physical files: {group.unique_physical_count}\n"
                f"Size: {format_byte_size(group.size_bytes)}\n"
                f"Theoretical potential savings: "
                f"{format_byte_size(group.potential_savings_bytes)}\n"
                "(Savings assume keeping one physical copy; nothing is deleted.)"
            )

        if role == Qt.ItemDataRole.TextAlignmentRole and column in {0, 1, 2}:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._groups.clear()
        self._root = None
        self.endResetModel()

    def set_groups(self, groups: list[DuplicateGroup], *, root: Path | None = None) -> None:
        self.beginResetModel()
        self._groups = list(groups)
        self._root = root
        self.endResetModel()

    def group_at(self, row: int) -> DuplicateGroup | None:
        if 0 <= row < len(self._groups):
            return self._groups[row]
        return None


class DuplicateMemberModel(QAbstractTableModel):
    """Files belonging to the selected duplicate group."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._files: list[DuplicateFile] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self._files)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(MEMBER_COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(MEMBER_COLUMNS)
        ):
            return MEMBER_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._files)):
            return None
        item = self._files[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return item.relative_path
            if column == 1:
                return f"{item.device}:{item.inode}"
            if column == 2:
                return format_byte_size(item.size_bytes)
            return None
        if role == Qt.ItemDataRole.UserRole and column == 0:
            return str(item.path)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"Full path:\n{item.path}"
        if role == Qt.ItemDataRole.AccessibleTextRole and column == 0:
            return f"{item.relative_path}; full path {item.path}"
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._files.clear()
        self.endResetModel()

    def set_files(self, files: list[DuplicateFile]) -> None:
        self.beginResetModel()
        self._files = list(files)
        self.endResetModel()


class DuplicateGroupFilterProxy(QSortFilterProxyModel):
    """Filter groups by example path / hash text."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._query = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_query(self, query: str) -> None:
        self._query = query.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._query:
            return True
        model = self.sourceModel()
        if not isinstance(model, DuplicateGroupModel):
            return False
        group = model.group_at(source_row)
        if group is None:
            return False
        if self._query in group.sha256.lower():
            return True
        for file in group.files:
            if (
                self._query in file.relative_path.lower()
                or self._query in str(file.path).lower()
            ):
                return True
        return False
