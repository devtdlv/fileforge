"""Data models for read-only duplicate detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class DuplicateStatus(Enum):
    """Terminal status of a duplicate scan."""

    COMPLETED = auto()
    CANCELLED = auto()
    PARTIAL = auto()
    FAILED = auto()
    EMPTY = auto()


@dataclass(frozen=True, slots=True)
class DuplicateFile:
    """One path belonging to a duplicate group."""

    path: Path
    relative_path: str
    size_bytes: int
    device: int
    inode: int

    @property
    def identity(self) -> tuple[int, int]:
        """Physical file identity used for hard-link collapse."""
        return (self.device, self.inode)


@dataclass(slots=True)
class DuplicateGroup:
    """Files that share the same content hash and size."""

    size_bytes: int
    sha256: str
    files: list[DuplicateFile] = field(default_factory=list)

    @property
    def path_count(self) -> int:
        return len(self.files)

    @property
    def unique_physical_count(self) -> int:
        return len({file.identity for file in self.files})

    @property
    def potential_savings_bytes(self) -> int:
        """Theoretical reclaimable bytes if all but one physical copy were removed.

        Hard-linked paths to the same inode count as one physical copy so savings
        are not overstated.
        """
        unique = self.unique_physical_count
        if unique <= 1:
            return 0
        return (unique - 1) * self.size_bytes


@dataclass(frozen=True, slots=True)
class DuplicateError:
    """A non-fatal problem while scanning or hashing."""

    path: str
    message: str


@dataclass(frozen=True, slots=True)
class DuplicateProgress:
    """Indeterminate progress (counts only; no fabricated percentages)."""

    phase: str
    files_seen: int = 0
    size_candidates: int = 0
    hashed: int = 0
    groups_found: int = 0
    current_path: str = ""


@dataclass(slots=True)
class DuplicateResult:
    """Aggregate outcome of a duplicate detection run."""

    root: Path
    recursive: bool
    status: DuplicateStatus
    groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[DuplicateError] = field(default_factory=list)
    files_scanned: int = 0
    unique_sizes: int = 0
    hashed_files: int = 0
    message: str = ""

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def duplicate_copy_count(self) -> int:
        """Count of paths that participate in a duplicate group."""
        return sum(group.path_count for group in self.groups)

    @property
    def potential_savings_bytes(self) -> int:
        return sum(group.potential_savings_bytes for group in self.groups)
