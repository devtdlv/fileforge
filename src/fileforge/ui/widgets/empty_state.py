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
        badge: str = "Ready when you are",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SectionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        self._badge_label = QLabel(badge)
        self._badge_label.setObjectName("BadgeLabel")
        self._badge_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._badge_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("EmptyStateTitle")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._body_label = QLabel(body)
        self._body_label.setObjectName("EmptyStateBody")
        self._body_label.setWordWrap(True)
        self._body_label.setMaximumWidth(640)
        layout.addWidget(self._body_label)

        layout.addStretch(1)

    def set_content(self, title: str, body: str, badge: str | None = None) -> None:
        """Update the visible empty-state copy."""
        self._title_label.setText(title)
        self._body_label.setText(body)
        if badge is not None:
            self._badge_label.setText(badge)
