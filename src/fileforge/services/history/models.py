"""Data models for read-only operation history queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HistoryOperationType(Enum):
    """Known batch operation types stored in operation_batches."""

    ALL = "all"
    ORGANIZE_MOVE = "organize_move"
    BULK_RENAME = "bulk_rename"


class HistoryBatchStatus(Enum):
    """Known batch status values written by Organizer and Bulk Renamer."""

    ALL = "all"
    PENDING = "pending"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


OPERATION_TYPE_LABELS: dict[str, str] = {
    "organize_move": "Organizer",
    "bulk_rename": "Bulk Renamer",
}

BATCH_STATUS_LABELS: dict[str, str] = {
    "pending": "Pending",
    "completed": "Completed",
    "partial": "Partial",
    "cancelled": "Cancelled",
    "failed": "Failed",
}

ENTRY_STATUS_LABELS: dict[str, str] = {
    "pending": "Pending",
    "success": "Succeeded",
    "failed": "Failed",
}

ENTRY_OPERATION_LABELS: dict[str, str] = {
    "move": "Move",
    "rename": "Rename",
}


def label_operation_type(value: str) -> str:
    return OPERATION_TYPE_LABELS.get(value, value or "(unknown)")


def label_batch_status(value: str) -> str:
    return BATCH_STATUS_LABELS.get(value, value or "(unknown)")


def label_entry_status(value: str) -> str:
    return ENTRY_STATUS_LABELS.get(value, value or "(unknown)")


def label_entry_operation(value: str) -> str:
    return ENTRY_OPERATION_LABELS.get(value, value or "(unknown)")


@dataclass(frozen=True, slots=True)
class HistoryFilters:
    """Combined filter/search/sort options for listing batches."""

    operation_type: HistoryOperationType = HistoryOperationType.ALL
    batch_status: HistoryBatchStatus = HistoryBatchStatus.ALL
    search: str = ""
    newest_first: bool = True
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class BatchSummary:
    """One operation batch with aggregated entry counts from the journal."""

    batch_id: str
    operation_type: str
    status: str
    summary: str
    source_root: str
    destination_root: str
    mode: str
    created_at: str
    completed_at: str
    entry_total: int
    entry_success: int
    entry_failed: int
    entry_pending: int

    @property
    def operation_label(self) -> str:
        return label_operation_type(self.operation_type)

    @property
    def status_label(self) -> str:
        return label_batch_status(self.status)


@dataclass(frozen=True, slots=True)
class EntrySummary:
    """One per-file journal entry within a batch."""

    entry_id: int
    batch_id: str
    operation_type: str
    source_path: str
    destination_path: str
    status: str
    error_details: str
    created_at: str
    completed_at: str

    @property
    def status_label(self) -> str:
        return label_entry_status(self.status)

    @property
    def operation_label(self) -> str:
        return label_entry_operation(self.operation_type)


@dataclass(frozen=True, slots=True)
class HistoryTotals:
    """Aggregate batch counts for the current filter (not paginated)."""

    matching_batches: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    partial: int = 0
    pending: int = 0
    # Unfiltered database totals for the summary strip.
    all_batches: int = 0
    all_completed: int = 0
    all_failed: int = 0
    all_cancelled: int = 0
    all_partial: int = 0


@dataclass(slots=True)
class BatchListResult:
    """Paginated batch listing plus totals."""

    batches: list[BatchSummary] = field(default_factory=list)
    totals: HistoryTotals = field(default_factory=HistoryTotals)
    filters: HistoryFilters = field(default_factory=HistoryFilters)
    message: str = ""
    error: str = ""
