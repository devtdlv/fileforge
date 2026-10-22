"""Data models for preview-first file organization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class OrganizeMode(Enum):
    """Supported destination layout strategies."""

    EXTENSION = "extension"
    CATEGORY = "category"
    YEAR_MONTH = "year_month"


class PlanItemStatus(Enum):
    """Status of one planned move before or after execution."""

    READY = auto()
    CONFLICT = auto()
    SKIPPED = auto()
    INVALID = auto()
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()


class PlanStatus(Enum):
    """Aggregate status of an organization plan or execution run."""

    READY = auto()
    BLOCKED = auto()  # conflicts or validation errors prevent apply
    EMPTY = auto()
    COMPLETED = auto()
    PARTIAL = auto()
    CANCELLED = auto()
    FAILED = auto()


@dataclass(frozen=True, slots=True)
class PlanItem:
    """One planned file move with validation metadata."""

    source: Path
    destination: Path
    rule: str
    status: PlanItemStatus
    conflict_reason: str = ""
    source_size: int = 0
    source_mtime_ns: int = 0
    error_message: str = ""


@dataclass(slots=True)
class OrganizePlan:
    """Dry-run organization plan generated without touching the filesystem."""

    source_root: Path
    destination_root: Path
    mode: OrganizeMode
    recursive: bool
    items: list[PlanItem] = field(default_factory=list)
    message: str = ""
    status: PlanStatus = PlanStatus.EMPTY

    @property
    def ready_items(self) -> list[PlanItem]:
        return [item for item in self.items if item.status == PlanItemStatus.READY]

    @property
    def conflict_items(self) -> list[PlanItem]:
        return [
            item
            for item in self.items
            if item.status in {PlanItemStatus.CONFLICT, PlanItemStatus.INVALID}
        ]

    @property
    def can_apply(self) -> bool:
        return self.status == PlanStatus.READY and bool(self.ready_items)


@dataclass(frozen=True, slots=True)
class ExecutionProgress:
    """Progress while applying an approved plan."""

    completed: int
    total: int
    succeeded: int
    failed: int
    current_source: str = ""


@dataclass(slots=True)
class ExecutionResult:
    """Outcome of applying an organization plan."""

    plan: OrganizePlan
    batch_id: str
    status: PlanStatus
    items: list[PlanItem] = field(default_factory=list)
    message: str = ""
    journaled: bool = True
