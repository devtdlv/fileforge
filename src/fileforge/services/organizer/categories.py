"""Broad file-category mapping used by the category organization mode."""

from __future__ import annotations

from typing import Final

CATEGORY_EXTENSIONS: Final[dict[str, frozenset[str]]] = {
    "Images": frozenset(
        {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
            "webp",
            "tif",
            "tiff",
            "svg",
            "heic",
            "heif",
            "ico",
            "raw",
        }
    ),
    "Documents": frozenset(
        {
            "pdf",
            "doc",
            "docx",
            "txt",
            "md",
            "rtf",
            "odt",
            "xls",
            "xlsx",
            "csv",
            "ppt",
            "pptx",
            "ods",
            "odp",
            "epub",
        }
    ),
    "Videos": frozenset(
        {
            "mp4",
            "mkv",
            "avi",
            "mov",
            "wmv",
            "webm",
            "m4v",
            "flv",
            "mpeg",
            "mpg",
        }
    ),
    "Audio": frozenset(
        {
            "mp3",
            "wav",
            "flac",
            "aac",
            "ogg",
            "m4a",
            "wma",
            "aiff",
            "opus",
        }
    ),
    "Archives": frozenset(
        {
            "zip",
            "rar",
            "7z",
            "tar",
            "gz",
            "bz2",
            "xz",
            "tgz",
        }
    ),
}

CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "Images",
    "Documents",
    "Videos",
    "Audio",
    "Archives",
    "Other",
)


def category_for_extension(extension: str) -> str:
    """Return the broad category name for a file extension."""
    ext = extension.lower().lstrip(".")
    if not ext:
        return "Other"
    for category in CATEGORY_ORDER:
        if category == "Other":
            continue
        if ext in CATEGORY_EXTENSIONS[category]:
            return category
    return "Other"
