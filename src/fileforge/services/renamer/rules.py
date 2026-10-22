"""Apply rename rules to a filename stem in documented order."""

from __future__ import annotations

from fileforge.services.renamer.models import CaseMode, RenameRules
from fileforge.services.renamer.names import join_filename, split_filename

# Exact rule application order (also shown in the UI):
# 1. Literal search/replace on the stem
# 2. Prefix
# 3. Suffix (inserted before the extension)
# 4. Sequential numbering (appended to stem with separator)
# 5. Case transformation (stem only; extension casing preserved)
RULE_ORDER_DESCRIPTION = (
    "1) search/replace  2) prefix  3) suffix  4) numbering  5) case (stem only)"
)


def apply_case(stem: str, mode: CaseMode) -> str:
    if mode is CaseMode.LOWER:
        return stem.lower()
    if mode is CaseMode.UPPER:
        return stem.upper()
    if mode is CaseMode.TITLE:
        import re

        parts = re.split(r"([_\-\s]+)", stem)
        return "".join(
            part[:1].upper() + part[1:].lower() if part and part[0].isalnum() else part
            for part in parts
        )
    return stem


def apply_rules_to_name(
    original_name: str,
    rules: RenameRules,
    *,
    sequence_number: int | None = None,
) -> str:
    """Return the proposed basename for *original_name* under *rules*.

    The original extension (including casing) is preserved. Only the stem is
    transformed, except that numbering/prefix/suffix/replace operate on the stem.
    """
    stem, extension = split_filename(original_name)

    # 1. Search/replace (literal, stem only)
    if rules.search:
        stem = stem.replace(rules.search, rules.replace)

    # 2. Prefix
    if rules.prefix:
        stem = f"{rules.prefix}{stem}"

    # 3. Suffix (before extension)
    if rules.suffix:
        stem = f"{stem}{rules.suffix}"

    # 4. Sequential numbering
    if rules.numbering_enabled and sequence_number is not None:
        width = max(1, int(rules.number_padding))
        number = f"{sequence_number:0{width}d}"
        sep = rules.number_separator
        stem = f"{stem}{sep}{number}"

    # 5. Case (stem only)
    stem = apply_case(stem, rules.case_mode)

    return join_filename(stem, extension)
