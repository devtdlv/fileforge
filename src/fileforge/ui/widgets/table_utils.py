"""Shared table view helpers for readable, resizable result panes."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QSizePolicy, QTableView


def configure_result_table(
    table: QTableView,
    *,
    min_height: int = 160,
    stretch: bool = True,
) -> None:
    """Apply consistent sizing and interaction defaults for result tables."""
    table.setMinimumHeight(min_height)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(28)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setMinimumSectionSize(64)
    if stretch:
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)


def set_stretch_columns(table: QTableView, stretch_indexes: list[int]) -> None:
    """Stretch selected columns; size others to contents."""
    header = table.horizontalHeader()
    for index in range(table.model().columnCount() if table.model() else 0):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if index in stretch_indexes
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(index, mode)
