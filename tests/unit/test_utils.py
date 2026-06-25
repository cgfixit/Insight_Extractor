"""Unit tests for insight_extractor.utils — previously untested module."""

from __future__ import annotations

from datetime import UTC, datetime

from insight_extractor.utils import (
    compute_text_hash,
    format_timestamp,
    sanitize_filename,
    truncate_text,
)


class TestTruncateText:
    """truncate_text keeps short strings intact and trims long ones."""

    def test_short_string_unchanged(self) -> None:
        assert truncate_text("hello", max_length=120) == "hello"

    def test_exactly_max_length(self) -> None:
        s = "x" * 120
        assert truncate_text(s, max_length=120) == s

    def test_long_string_truncated(self) -> None:
        s = "a" * 200
        result = truncate_text(s, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_custom_suffix(self) -> None:
        result = truncate_text("hello world", max_length=8, suffix="…")
        assert result.endswith("…")
        assert len(result) == 8

    def test_empty_string(self) -> None:
        assert truncate_text("", max_length=10) == ""


class TestSanitizeFilename:
    """sanitize_filename strips characters unsafe in file paths."""

    def test_alphanumeric_unchanged(self) -> None:
        assert sanitize_filename("report2026") == "report2026"

    def test_spaces_become_underscores(self) -> None:
        assert sanitize_filename("my report") == "my_report"

    def test_special_chars_removed(self) -> None:
        result = sanitize_filename("foo/bar:baz*qux")
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result

    def test_leading_trailing_whitespace_stripped(self) -> None:
        result = sanitize_filename("  report  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_empty_string(self) -> None:
        assert sanitize_filename("") == ""


class TestFormatTimestamp:
    """format_timestamp returns ISO 8601 UTC strings ending in Z."""

    def test_returns_string(self) -> None:
        ts = format_timestamp()
        assert isinstance(ts, str)

    def test_ends_with_z(self) -> None:
        ts = format_timestamp()
        assert ts.endswith("Z")

    def test_parses_as_iso(self) -> None:
        ts = format_timestamp()
        # Should round-trip through fromisoformat
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_explicit_datetime(self) -> None:
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        ts = format_timestamp(dt)
        assert "2026-01-15" in ts
        assert ts.endswith("Z")

    def test_none_uses_now(self) -> None:
        before = datetime.now(UTC)
        ts = format_timestamp(None)
        after = datetime.now(UTC)
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert before <= parsed <= after


class TestComputeTextHash:
    """compute_text_hash produces stable, truncated SHA-256 hex digests."""

    def test_returns_string(self) -> None:
        h = compute_text_hash("hello")
        assert isinstance(h, str)

    def test_default_length_16(self) -> None:
        h = compute_text_hash("hello")
        assert len(h) == 16

    def test_custom_length(self) -> None:
        h = compute_text_hash("hello", length=8)
        assert len(h) == 8

    def test_deterministic(self) -> None:
        assert compute_text_hash("same input") == compute_text_hash("same input")

    def test_different_inputs_differ(self) -> None:
        assert compute_text_hash("input A") != compute_text_hash("input B")

    def test_empty_string(self) -> None:
        h = compute_text_hash("")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)
