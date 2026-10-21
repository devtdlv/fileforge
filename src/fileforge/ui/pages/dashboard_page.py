"""Dashboard: product purpose and guidance toward Folder Scanner."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fileforge.core.safety import SAFETY_HIGHLIGHTS
from fileforge.ui.widgets.page_header import PageHeader


class DashboardPage(QWidget):
    """Landing page that explains FileForge and routes users to the scanner."""

    open_scanner_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(22)

        layout.addWidget(
            PageHeader(
                "Welcome to FileForge",
                "Organize files, find duplicates, and rename in bulk on your "
                "own PC. Changes are previewed first and never applied silently.",
            )
        )

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(14)

        hero_kicker = QLabel("Start here")
        hero_kicker.setObjectName("SectionKicker")
        hero_layout.addWidget(hero_kicker)

        hero_title = QLabel("Open the Folder Scanner")
        hero_title.setObjectName("HeroTitle")
        hero_title.setWordWrap(True)
        hero_layout.addWidget(hero_title)

        hero_body = QLabel(
            "The Folder Scanner will become your read-only entry point for "
            "inventory and storage review. Scanning is not implemented yet, "
            "and FileForge will not touch personal files until you review and "
            "confirm a plan in a later milestone."
        )
        hero_body.setObjectName("BodyLabel")
        hero_body.setWordWrap(True)
        hero_layout.addWidget(hero_body)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.setContentsMargins(0, 4, 0, 0)

        self.open_scanner_button = QPushButton("Open Folder Scanner")
        self.open_scanner_button.setObjectName("PrimaryButton")
        self.open_scanner_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_scanner_button.setToolTip("Go to the Folder Scanner page (Ctrl+2)")
        self.open_scanner_button.setDefault(True)
        self.open_scanner_button.setAutoDefault(True)
        self.open_scanner_button.clicked.connect(self.open_scanner_requested.emit)
        actions.addWidget(self.open_scanner_button)
        actions.addStretch(1)
        hero_layout.addLayout(actions)
        layout.addWidget(hero)

        safety = QFrame()
        safety.setObjectName("SectionCard")
        safety_layout = QVBoxLayout(safety)
        safety_layout.setContentsMargins(24, 22, 24, 22)
        safety_layout.setSpacing(10)

        safety_kicker = QLabel("Safety overview")
        safety_kicker.setObjectName("SectionKicker")
        safety_layout.addWidget(safety_kicker)

        safety_title = QLabel("Built for careful file work")
        safety_title.setObjectName("EmptyStateTitle")
        safety_layout.addWidget(safety_title)

        safety_intro = QLabel(
            "FileForge keeps destructive actions behind preview and confirmation. "
            "The full safety checklist lives in the project documentation."
        )
        safety_intro.setObjectName("BodyLabel")
        safety_intro.setWordWrap(True)
        safety_layout.addWidget(safety_intro)

        for highlight in SAFETY_HIGHLIGHTS:
            row = QLabel(f"•  {highlight}")
            row.setObjectName("MutedLabel")
            row.setWordWrap(True)
            safety_layout.addWidget(row)

        layout.addWidget(safety)

        note = QLabel(
            "No fabricated storage metrics are shown here. Feature pages that "
            "are still in progress use clear empty states instead of fake data."
        )
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
