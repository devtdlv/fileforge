"""Safety architecture principles for Junction file operations.

These principles define hard boundaries for Junction. Undo and duplicate
deletion are not implemented yet. Future milestones must honor these rules
before expanding filesystem-changing behavior.
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

# Concise highlights for the dashboard; full list remains in SAFETY_PRINCIPLES.
SAFETY_HIGHLIGHTS: Final[tuple[str, ...]] = (
    "Preview first: scanning never changes files.",
    "No silent overwrites or automatic duplicate deletion.",
    "Explicit confirmation before any filesystem change.",
    "Undo only when safe, verified, and journaled.",
)


def format_safety_principles() -> str:
    """Return a numbered, human-readable list of safety principles."""
    lines = [f"{index}. {principle}" for index, principle in enumerate(SAFETY_PRINCIPLES, start=1)]
    return "\n".join(lines)
