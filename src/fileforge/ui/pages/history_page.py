"""Operation History page shell (journal foundation only)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader


class HistoryPage(QWidget):
    """Placeholder for reviewing journaled operations and future undo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Operation History",
                "Review recorded file operations. Undo will only appear when "
                "it is safe and verifiable.",
            )
        )
        layout.addWidget(
            EmptyStateWidget(
                title="History browser not available yet",
                body=(
                    "Organization applies are recorded in the local SQLite "
                    "journal (batches and per-file entries). This page does "
                    "not list them yet, and undo is not implemented. A later "
                    "milestone will add review and safe reverse when verifiable."
                ),
                badge="Journaling active; undo later",
            )
        )

        note = QLabel(
            "Reversing operations is intentionally unavailable until journaling "
            "and verification land together."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.setEnabled(False)
        self.undo_button.setToolTip("Undo is not implemented in this milestone")
        self.undo_button.setObjectName("SecondaryButton")
        layout.addWidget(self.undo_button)
        layout.addStretch(1)
