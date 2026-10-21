"""Duplicate Finder page shell."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader


class DuplicatesPage(QWidget):
    """Placeholder for duplicate detection without automatic deletion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Duplicate Finder",
                "Locate likely duplicate files and decide what to keep. "
                "Nothing is deleted automatically.",
            )
        )
        layout.addWidget(
            EmptyStateWidget(
                title="Duplicate detection is not available yet",
                body=(
                    "A later milestone will compare files safely and present "
                    "groups for review. FileForge will never auto-delete "
                    "duplicates."
                ),
            )
        )

        self.delete_selected_button = QPushButton("Delete Selected Duplicates")
        self.delete_selected_button.setEnabled(False)
        self.delete_selected_button.setToolTip(
            "Unavailable — automatic and bulk deletion ship later with confirmation"
        )
        self.delete_selected_button.setObjectName("SecondaryButton")
        layout.addWidget(self.delete_selected_button)
        layout.addStretch(1)
