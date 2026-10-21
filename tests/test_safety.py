"""Safety architecture documentation tests."""

from __future__ import annotations

from fileforge.core.safety import (
    SAFETY_HIGHLIGHTS,
    SAFETY_PRINCIPLES,
    format_safety_principles,
)


def test_safety_principles_cover_required_rules() -> None:
    text = " ".join(SAFETY_PRINCIPLES).lower()
    assert len(SAFETY_PRINCIPLES) >= 8
    assert "preview" in text
    assert "overwrite" in text
    assert "deletion" in text or "delete" in text
    assert "confirmation" in text
    assert "journal" in text
    assert "undo" in text
    assert "scanning" in text or "preview" in text
    assert "temporary" in text


def test_safety_highlights_are_concise() -> None:
    assert 3 <= len(SAFETY_HIGHLIGHTS) <= 5
    joined = " ".join(SAFETY_HIGHLIGHTS).lower()
    assert "preview" in joined
    assert "confirmation" in joined or "confirm" in joined
    assert "undo" in joined


def test_format_safety_principles_is_numbered() -> None:
    formatted = format_safety_principles()
    assert formatted.startswith("1. ")
    assert "8. " in formatted
