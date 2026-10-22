"""Unit tests for rename rule application and filename validation."""

from __future__ import annotations

from fileforge.services.renamer import CaseMode, RenameRules, apply_rules_to_name
from fileforge.services.renamer.names import (
    join_filename,
    split_filename,
    validate_windows_filename,
)


def test_split_and_join_multidot_and_dotfile() -> None:
    assert split_filename("archive.tar.gz") == ("archive.tar", ".gz")
    assert join_filename("archive.tar", ".gz") == "archive.tar.gz"
    assert split_filename("README") == ("README", "")
    assert split_filename(".gitignore") == (".gitignore", "")
    assert split_filename(".env.local") == (".env", ".local")


def test_prefix_suffix_preserve_extension_case() -> None:
    rules = RenameRules(prefix="holiday_", suffix="_final")
    assert apply_rules_to_name("photo.JPG", rules) == "holiday_photo_final.JPG"
    assert apply_rules_to_name("report.pdf", rules) == "holiday_report_final.pdf"


def test_search_replace_literal() -> None:
    rules = RenameRules(search="IMG", replace="PHOTO")
    assert apply_rules_to_name("IMG_2026_001.jpg", rules) == "PHOTO_2026_001.jpg"


def test_numbering_padding_and_separator() -> None:
    rules = RenameRules(
        numbering_enabled=True,
        number_start=1,
        number_padding=3,
        number_separator="_",
    )
    assert apply_rules_to_name("photo.jpg", rules, sequence_number=1) == "photo_001.jpg"
    assert apply_rules_to_name("image.jpg", rules, sequence_number=2) == "image_002.jpg"


def test_case_transforms_stem_only() -> None:
    assert (
        apply_rules_to_name("Photo.JPG", RenameRules(case_mode=CaseMode.LOWER))
        == "photo.JPG"
    )
    assert (
        apply_rules_to_name("Photo.JPG", RenameRules(case_mode=CaseMode.UPPER))
        == "PHOTO.JPG"
    )
    assert (
        apply_rules_to_name("holiday_photo.JPG", RenameRules(case_mode=CaseMode.TITLE))
        == "Holiday_Photo.JPG"
    )


def test_combined_rules_documented_order() -> None:
    # Order: replace → prefix → suffix → numbering → case
    rules = RenameRules(
        search="IMG",
        replace="Holiday",
        suffix="_edited",
        case_mode=CaseMode.LOWER,
    )
    assert apply_rules_to_name("IMG_001.JPG", rules) == "holiday_001_edited.JPG"


def test_unicode_and_extensionless() -> None:
    rules = RenameRules(prefix="新_")
    assert apply_rules_to_name("文件.txt", rules) == "新_文件.txt"
    assert apply_rules_to_name("README", RenameRules(suffix="_v2")) == "README_v2"


def test_validate_windows_filename() -> None:
    assert validate_windows_filename("ok.txt") is None
    assert validate_windows_filename("") is not None
    assert validate_windows_filename("bad:name.txt") is not None
    assert validate_windows_filename("NUL.txt") is not None
    assert validate_windows_filename("trailing.txt.") is not None
    assert validate_windows_filename("space ") is not None
