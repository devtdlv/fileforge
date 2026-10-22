"""Read-only duplicate file detection."""

from fileforge.services.duplicates.engine import DuplicateFinder
from fileforge.services.duplicates.hasher import sha256_file
from fileforge.services.duplicates.models import (
    DuplicateError,
    DuplicateFile,
    DuplicateGroup,
    DuplicateProgress,
    DuplicateResult,
    DuplicateStatus,
)

__all__ = [
    "DuplicateError",
    "DuplicateFile",
    "DuplicateFinder",
    "DuplicateGroup",
    "DuplicateProgress",
    "DuplicateResult",
    "DuplicateStatus",
    "sha256_file",
]
