"""Organizer page shell (rules-based organization arrives later)."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader


class OrganizerPage(QWidget):
    """Placeholder for preview-first file organization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Organizer",
                "Propose destination folders with a full preview before any "
                "files are moved.",
            )
        )
        layout.addWidget(
            EmptyStateWidget(
                title="Organization tools are not available yet",
                body=(
                    "Future milestones will generate move plans you can review "
                    "line by line. No silent overwrites. Applying changes will "
                    "always require explicit confirmation."
                ),
            )
        )

        self.apply_plan_button = QPushButton("Apply Organization Plan")
        self.apply_plan_button.setEnabled(False)
        self.apply_plan_button.setToolTip("Available in a later milestone")
        self.apply_plan_button.setObjectName("SecondaryButton")
        layout.addWidget(self.apply_plan_button)
        layout.addStretch(1)
