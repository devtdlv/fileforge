"""Clean empty / coming-soon state panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class EmptyStateWidget(QFrame):
    """Communicates that a feature area is intentionally empty or upcoming."""

    def __init__(
        self,
        title: str,
        body: str,
        badge: str = "Coming in a later milestone",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        badge_label = QLabel(badge)
        badge_label.setObjectName("BadgeLabel")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(badge_label, alignment=Qt.AlignmentFlag.AlignLeft)

        title_label = QLabel(title)
        title_label.setObjectName("EmptyStateTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setObjectName("EmptyStateBody")
        body_label.setWordWrap(True)
        body_label.setMaximumWidth(640)
        layout.addWidget(body_label)

        layout.addStretch(1)
