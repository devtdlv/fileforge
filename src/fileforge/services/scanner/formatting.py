"""Presentation helpers for scanner metadata (UI-agnostic)."""

from __future__ import annotations

from datetime import datetime


def format_byte_size(num_bytes: int) -> str:
    """Return a human-readable binary size string."""
    if num_bytes < 0:
        return "-"
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def format_timestamp(value: datetime | None) -> str:
    """Return a local timestamp string, or '-' when missing."""
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
