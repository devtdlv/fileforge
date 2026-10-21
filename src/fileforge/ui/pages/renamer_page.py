"""Bulk Renamer page shell."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader


class RenamerPage(QWidget):
    """Placeholder for preview-first bulk renaming."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Bulk Renamer",
                "Build rename patterns and review every proposed name before "
                "anything is written to disk.",
            )
        )
        layout.addWidget(
            EmptyStateWidget(
                title="Bulk renaming is not available yet",
                body=(
                    "Future milestones will show a side-by-side preview of "
                    "current and proposed names. Conflicts and overwrites will "
                    "be blocked unless you confirm a safe resolution."
                ),
            )
        )

        self.apply_rename_button = QPushButton("Apply Rename Plan")
        self.apply_rename_button.setEnabled(False)
        self.apply_rename_button.setToolTip("Available in a later milestone")
        self.apply_rename_button.setObjectName("SecondaryButton")
        layout.addWidget(self.apply_rename_button)
        layout.addStretch(1)
