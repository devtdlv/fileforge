"""Data models for read-only folder scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path


class EntryKind(Enum):
    """Classification of a discovered filesystem entry."""

    FILE = auto()
    DIRECTORY = auto()
    SYMLINK = auto()
    JUNCTION = auto()
    OTHER = auto()


class ScanStatus(Enum):
    """Terminal status of a scan operation."""

    COMPLETED = auto()
    CANCELLED = auto()
    PARTIAL = auto()  # finished walking, but one or more errors occurred
    FAILED = auto()  # could not begin or aborted due to a fatal root error


@dataclass(frozen=True, slots=True)
class ScanEntry:
    """Metadata for one filesystem entry discovered during a scan."""

    name: str
    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    modified_at: datetime | None
    parent_directory: str
    kind: EntryKind


@dataclass(frozen=True, slots=True)
class ScanError:
    """A non-fatal problem encountered while scanning."""

    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ScanProgress:
    """Indeterminate progress snapshot (counts only; no fabricated percentages)."""

    files_seen: int
    directories_seen: int
    errors_seen: int
    current_path: str = ""


@dataclass(slots=True)
class ScanResult:
    """Aggregate outcome of a folder scan."""

    root: Path
    recursive: bool
    status: ScanStatus
    entries: list[ScanEntry] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str = ""

    @property
    def file_count(self) -> int:
        return sum(1 for entry in self.entries if entry.kind == EntryKind.FILE)

    @property
    def directory_count(self) -> int:
        return sum(1 for entry in self.entries if entry.kind == EntryKind.DIRECTORY)

    @property
    def skipped_count(self) -> int:
        return sum(
            1
            for entry in self.entries
            if entry.kind in {EntryKind.SYMLINK, EntryKind.JUNCTION, EntryKind.OTHER}
        )

    @property
    def total_size_bytes(self) -> int:
        return sum(
            entry.size_bytes for entry in self.entries if entry.kind == EntryKind.FILE
        )
