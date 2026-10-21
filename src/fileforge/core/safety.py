"""Safety architecture principles for future file operations.

These principles define hard boundaries for FileForge. Milestone 1 does not
implement organize, rename, delete, or undo. Future milestones must honor
these rules before touching the filesystem.
"""

from __future__ import annotations

from typing import Final

SAFETY_PRINCIPLES: Final[tuple[str, ...]] = (
    "Preview before applying changes.",
    "No silent file overwrites.",
    "No automatic deletion of duplicates.",
    "Explicit user confirmation before modifying files.",
    "Operation journaling and recovery.",
    "Undo only when safe and verifiable.",
    "No filesystem changes during scanning or preview.",
    "Tests must use temporary directories rather than personal files.",
)


def format_safety_principles() -> str:
    """Return a numbered, human-readable list of safety principles."""
    lines = [f"{index}. {principle}" for index, principle in enumerate(SAFETY_PRINCIPLES, start=1)]
    return "\n".join(lines)
