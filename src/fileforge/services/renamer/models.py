"""Data models for preview-first bulk renaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class CaseMode(Enum):
    """Stem-only case transformation."""

    NONE = "none"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"


class RenameItemStatus(Enum):
    """Status of one planned rename before or after execution."""

    READY = auto()
    UNCHANGED = auto()
    CONFLICT = auto()
    INVALID = auto()
    MISSING = auto()
    STALE = auto()
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()


class RenamePlanStatus(Enum):
    """Aggregate status of a rename plan or execution run."""

    READY = auto()
    BLOCKED = auto()
    EMPTY = auto()
    COMPLETED = auto()
    PARTIAL = auto()
    CANCELLED = auto()
    FAILED = auto()


@dataclass(frozen=True, slots=True)
class RenameRules:
    """User-configured rename rules applied in a fixed documented order."""

    prefix: str = ""
    suffix: str = ""
    search: str = ""
    replace: str = ""
    numbering_enabled: bool = False
    number_start: int = 1
    number_padding: int = 3
    number_separator: str = "_"
    case_mode: CaseMode = CaseMode.NONE

    def describe(self) -> str:
        """Human-readable summary of active rules in application order."""
        parts: list[str] = []
        if self.search:
            parts.append(f"replace '{self.search}' → '{self.replace}'")
        if self.prefix:
            parts.append(f"prefix '{self.prefix}'")
        if self.suffix:
            parts.append(f"suffix '{self.suffix}'")
        if self.numbering_enabled:
            parts.append(
                f"number from {self.number_start} "
                f"(pad {self.number_padding}, sep '{self.number_separator}')"
            )
        if self.case_mode is not CaseMode.NONE:
            parts.append(f"case {self.case_mode.value}")
        return "; ".join(parts) if parts else "(no rules)"

    def is_effectively_empty(self) -> bool:
        return (
            not self.prefix
            and not self.suffix
            and not self.search
            and not self.numbering_enabled
            and self.case_mode is CaseMode.NONE
        )


@dataclass(frozen=True, slots=True)
class RenameItem:
    """One planned file rename with validation metadata."""

    source: Path
    proposed_name: str
    destination: Path
    relative_folder: str
    rule_summary: str
    status: RenameItemStatus
    conflict_reason: str = ""
    source_size: int = 0
    source_mtime_ns: int = 0
    error_message: str = ""
    sequence_number: int | None = None


@dataclass(slots=True)
class RenamePlan:
    """Dry-run rename plan generated without touching the filesystem."""

    root: Path
    recursive: bool
    rules: RenameRules
    items: list[RenameItem] = field(default_factory=list)
    message: str = ""
    status: RenamePlanStatus = RenamePlanStatus.EMPTY

    @property
    def ready_items(self) -> list[RenameItem]:
        return [item for item in self.items if item.status == RenameItemStatus.READY]

    @property
    def conflict_items(self) -> list[RenameItem]:
        return [
            item
            for item in self.items
            if item.status
            in {
                RenameItemStatus.CONFLICT,
                RenameItemStatus.INVALID,
                RenameItemStatus.MISSING,
                RenameItemStatus.STALE,
            }
        ]

    @property
    def unchanged_count(self) -> int:
        return sum(1 for item in self.items if item.status == RenameItemStatus.UNCHANGED)

    @property
    def can_apply(self) -> bool:
        return self.status == RenamePlanStatus.READY and bool(self.ready_items)


@dataclass(frozen=True, slots=True)
class RenameProgress:
    """Progress while planning or applying renames."""

    phase: str
    completed: int = 0
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    current_path: str = ""


@dataclass(slots=True)
class RenameExecutionResult:
    """Outcome of applying a rename plan."""

    plan: RenamePlan
    batch_id: str
    status: RenamePlanStatus
    items: list[RenameItem] = field(default_factory=list)
    message: str = ""
    journaled: bool = True
