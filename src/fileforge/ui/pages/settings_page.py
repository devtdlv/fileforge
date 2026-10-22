"""Settings page with durable preferences and database path visibility."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fileforge.database.settings_store import SettingsStore
from fileforge.ui.widgets.page_header import PageHeader

SETTING_CONFIRM_EXIT = "confirm_exit"
SETTING_DISPLAY_NAME = "display_name"


class SettingsPage(QWidget):
    """Persist a small set of real settings; show database location."""

    def __init__(
        self,
        settings: SettingsStore,
        database_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._database_path = database_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        layout.addWidget(
            PageHeader(
                "Settings",
                "Preferences are stored in your local Junction database. "
                "They never leave this machine.",
            )
        )

        card = QFrame()
        card.setObjectName("SectionCard")
        form = QFormLayout(card)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("Optional label for this installation")
        self.display_name_edit.setClearButtonEnabled(True)
        form.addRow("Display name", self.display_name_edit)

        self.confirm_exit_check = QCheckBox("Ask for confirmation before exiting")
        form.addRow("", self.confirm_exit_check)

        path_label = QLabel(str(database_path))
        path_label.setObjectName("MutedLabel")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setWordWrap(True)
        form.addRow("Database path", path_label)

        layout.addWidget(card)

        self.save_button = QPushButton("Save Settings")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setToolTip("Write these preferences to the local database")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        hint = QLabel(
            "Only settings shown here are stored today. Cloud sync, themes, and "
            "telemetry are intentionally not offered. Destructive actions elsewhere "
            "in the app stay disabled until implemented."
        )
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

        self.load_settings()

    def load_settings(self) -> None:
        """Load settings from the database into the form."""
        self.display_name_edit.setText(self._settings.get(SETTING_DISPLAY_NAME, "") or "")
        confirm = self._settings.get(SETTING_CONFIRM_EXIT, "1")
        self.confirm_exit_check.setChecked(confirm != "0")

    def save_settings(self) -> None:
        """Persist the form values with parameterized SQL via SettingsStore."""
        self._settings.set(SETTING_DISPLAY_NAME, self.display_name_edit.text().strip())
        self._settings.set(
            SETTING_CONFIRM_EXIT,
            "1" if self.confirm_exit_check.isChecked() else "0",
        )
        QMessageBox.information(
            self,
            "Settings saved",
            "Your preferences were written to the local Junction database.",
        )

    @property
    def database_path(self) -> Path:
        return self._database_path
