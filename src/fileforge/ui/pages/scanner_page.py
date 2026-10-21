"""Folder Scanner page shell (scanning arrives in a later milestone)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from fileforge.ui.widgets.empty_state import EmptyStateWidget
from fileforge.ui.widgets.page_header import PageHeader


class ScannerPage(QWidget):
    """Placeholder for folder inventory and storage review."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Folder Scanner",
                "Inventory folders and review storage information without "
                "changing any files.",
            )
        )

        layout.addWidget(
            EmptyStateWidget(
                title="Folder scanning is not available yet",
                body=(
                    "A later milestone will let you choose a folder, preview "
                    "file counts and sizes, and build an inventory. Scanning "
                    "will never move, rename, or delete files."
                ),
            )
        )

        note = QLabel(
            "No personal folders are scanned in this milestone. Actions that "
            "are not ready remain disabled."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.choose_folder_button = QPushButton("Choose Folder…")
        self.choose_folder_button.setEnabled(False)
        self.choose_folder_button.setToolTip("Available in a later milestone")
        layout.addWidget(self.choose_folder_button)

        layout.addStretch(1)
