"""Keyboard-accessible sidebar navigation."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fileforge import __app_name__


@dataclass(frozen=True, slots=True)
class NavItem:
    """A navigable destination in the main window."""

    page_id: str
    label: str
    shortcut: str | None = None
    icon: QStyle.StandardPixmap | None = None


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Dashboard", "Ctrl+1", QStyle.StandardPixmap.SP_DirHomeIcon),
    NavItem(
        "scanner",
        "Folder Scanner",
        "Ctrl+2",
        QStyle.StandardPixmap.SP_DirIcon,
    ),
    NavItem(
        "organizer",
        "Organizer",
        "Ctrl+3",
        QStyle.StandardPixmap.SP_FileDialogContentsView,
    ),
    NavItem(
        "duplicates",
        "Duplicate Finder",
        "Ctrl+4",
        QStyle.StandardPixmap.SP_FileDialogDetailedView,
    ),
    NavItem(
        "renamer",
        "Bulk Renamer",
        "Ctrl+5",
        QStyle.StandardPixmap.SP_FileDialogListView,
    ),
    NavItem(
        "history",
        "Operation History",
        "Ctrl+6",
        QStyle.StandardPixmap.SP_BrowserReload,
    ),
    NavItem(
        "settings",
        "Settings",
        "Ctrl+7",
        QStyle.StandardPixmap.SP_FileDialogInfoView,
    ),
)


class Sidebar(QWidget):
    """Brand strip plus list-based navigation with keyboard shortcuts."""

    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel(__app_name__)
        brand.setObjectName("SidebarBrand")
        layout.addWidget(brand)

        tagline = QLabel("Local-first file toolkit")
        tagline.setObjectName("SidebarTagline")
        layout.addWidget(tagline)

        self._list = QListWidget()
        self._list.setObjectName("NavList")
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setIconSize(QSize(18, 18))
        self._list.setSpacing(2)
        self._list.setAccessibleName("Main navigation")
        self._list.setUniformItemSizes(True)

        style = QApplication.style()
        self._index_by_id: dict[str, int] = {}
        for index, item in enumerate(NAV_ITEMS):
            list_item = QListWidgetItem(item.label)
            list_item.setData(Qt.ItemDataRole.UserRole, item.page_id)
            list_item.setToolTip(
                f"{item.label}" + (f" ({item.shortcut})" if item.shortcut else "")
            )
            if item.icon is not None and style is not None:
                list_item.setIcon(style.standardIcon(item.icon))
            self._list.addItem(list_item)
            self._index_by_id[item.page_id] = index
            if item.shortcut:
                shortcut = QShortcut(QKeySequence(item.shortcut), self)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                shortcut.activated.connect(
                    lambda page_id=item.page_id: self.select_page(page_id)
                )

        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, stretch=1)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def page_ids(self) -> list[str]:
        """Return navigation page identifiers in display order."""
        return [item.page_id for item in NAV_ITEMS]

    def current_page_id(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def select_page(self, page_id: str) -> None:
        """Select a page by id, emitting ``page_selected`` when the row changes."""
        index = self._index_by_id.get(page_id)
        if index is None:
            return
        if self._list.currentRow() == index:
            self.page_selected.emit(page_id)
            return
        self._list.setCurrentRow(index)

    def _on_row_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self._list.item(row)
        if item is None:
            return
        page_id = item.data(Qt.ItemDataRole.UserRole)
        if page_id is not None:
            self.page_selected.emit(str(page_id))
