"""Dashboard: product purpose and guidance toward Folder Scanner."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from fileforge.core.safety import SAFETY_PRINCIPLES
from fileforge.ui.widgets.page_header import PageHeader


class DashboardPage(QWidget):
    """Landing page that explains FileForge and routes users to the scanner."""

    open_scanner_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        layout.addWidget(
            PageHeader(
                "Welcome to FileForge",
                "A local-first Windows toolkit for organizing files, finding "
                "duplicates, bulk renaming, and reviewing storage safely, "
                "with clear previews before any change.",
            )
        )

        intro = QFrame()
        intro.setObjectName("SectionCard")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(20, 20, 20, 20)
        intro_layout.setSpacing(12)

        purpose = QLabel(
            "Start by opening the Folder Scanner. Scanning and preview never "
            "modify your files. Organization, rename, and recovery tools arrive "
            "in later milestones and will require explicit confirmation."
        )
        purpose.setObjectName("BodyLabel")
        purpose.setWordWrap(True)
        intro_layout.addWidget(purpose)

        self.open_scanner_button = QPushButton("Open Folder Scanner")
        self.open_scanner_button.setToolTip("Go to the Folder Scanner page (Ctrl+2)")
        self.open_scanner_button.clicked.connect(self.open_scanner_requested.emit)
        intro_layout.addWidget(self.open_scanner_button)
        layout.addWidget(intro)

        safety = QFrame()
        safety.setObjectName("SectionCard")
        safety_layout = QVBoxLayout(safety)
        safety_layout.setContentsMargins(20, 20, 20, 20)
        safety_layout.setSpacing(8)

        safety_title = QLabel("Safety principles")
        safety_title.setObjectName("EmptyStateTitle")
        safety_layout.addWidget(safety_title)

        for index, principle in enumerate(SAFETY_PRINCIPLES, start=1):
            item = QLabel(f"{index}. {principle}")
            item.setObjectName("MutedLabel")
            item.setWordWrap(True)
            safety_layout.addWidget(item)

        layout.addWidget(safety)
        layout.addStretch(1)
