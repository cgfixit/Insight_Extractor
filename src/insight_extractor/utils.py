"""Utility functions for insight_extractor."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_HAS_WORD = re.compile(r"\w")
# Headings and table / box-drawing rows are one unit each; splitting a row on "?" or "."
# strands its trailing cells as fake sentences.
_ATOMIC_LINE = re.compile(r"#{1,6}\s|[|│┃║]")
# A pipe-table delimiter row ("--|--", "|:---|---:|"). Other lines count as table rows
# only next to one, so prose with shell pipelines ("| base64 -d | bash") stays prose.
_TABLE_RULE = re.compile(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?")
# List items and quotes start a paragraph that wrapped continuation lines may join.
_BLOCK_START = re.compile(r"[-*+]\s|\d{1,3}[.)]\s|>")
# A punctuation split must not end on a list ordinal ("> 4.") or a common abbreviation;
# "U.S. government" otherwise became the top-ranked fragment "government and ...".
_LIST_ORDINAL = re.compile(r"(?:[>#*+-] *)*\d{1,3}\.")
# Titles are case-sensitive so "every 500 ms. The operator ..." still splits.
_NO_BREAK_AFTER = re.compile(
    r"(?<![\w.])(?:vs|e\.g|i\.e|cf|approx)\.$"
    r"|(?<![\w.])(?-i:Mrs?|Ms|Dr|St|Fig)\.$",
    re.IGNORECASE,
)
# "U.S."/"U.K." often end a sentence, so they join only a lowercase continuation.
_COUNTRY_ABBREVIATION = re.compile(r"(?<![\w.])U\.[SK]\.$")
# "approx." is the longest suffix to check.
_ABBREVIATION_TAIL = 7
_FRAME_CHARS = " \t|│┃║"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the package logger; other loggers stay at WARNING."""
    # A root logger at INFO also enabled third-party INFO records: one CLI run logged every
    # Hugging Face HTTP request during model loading (~13 KB of stderr).
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("insight_extractor")
    logger.setLevel(level)
    return logger


def truncate_text(text: str, max_length: int = 120, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def _table_row_indexes(lines: list[str]) -> set[int]:
    """Indexes of the header and body rows around each pipe-table delimiter row."""
    rows: set[int] = set()
    in_table = False
    for i, line in enumerate(lines):
        if "|" not in line:
            in_table = False
            continue
        if in_table:
            rows.add(i)
        if _TABLE_RULE.fullmatch(line):
            if i and "|" in lines[i - 1]:
                rows.add(i - 1)
            in_table = True
    return rows


def split_sentences(text: str) -> list[str]:
    """Split text into whitespace-normalised sentences without merging Markdown lines.

    Hard-wrapped prose lines are joined before splitting on terminal punctuation. Blank
    lines end a paragraph; list items and quotes start one; headings and table rows (a
    leading pipe or box-drawing bar, or rows attached to a pipe-table delimiter row) are
    single units with their outer frame removed. Lines without any word character
    (rules, borders) are dropped.
    """
    units: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            fragments: list[str] = []
            for piece in _SENTENCE_END.split(" ".join(paragraph)):
                if fragments:
                    previous = fragments[-1]
                    tail = max(0, len(previous) - _ABBREVIATION_TAIL)
                    if (
                        _NO_BREAK_AFTER.search(previous, tail)
                        or (_COUNTRY_ABBREVIATION.search(previous, tail) and piece[:1].islower())
                        or (len(fragments) == 1 and _LIST_ORDINAL.fullmatch(previous))
                    ):
                        fragments.append(piece)
                        continue
                    units.append(" ".join(fragments))
                fragments = [piece] if piece else []
            if fragments:
                units.append(" ".join(fragments))
            paragraph.clear()

    lines = [" ".join(line.split()) for line in text.splitlines()]
    table_rows = _table_row_indexes(lines)
    for i, stripped in enumerate(lines):
        if not _HAS_WORD.search(stripped):
            flush()
        elif i in table_rows or _ATOMIC_LINE.match(stripped):
            flush()
            units.append(stripped.strip(_FRAME_CHARS))
        else:
            if _BLOCK_START.match(stripped):
                flush()
            paragraph.append(stripped)
    flush()
    return units


def format_timestamp(dt: datetime | None = None) -> str:
    """Return ISO 8601 UTC timestamp string."""
    if dt is None:
        dt = datetime.now(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def compute_text_hash(text: str, length: int = 16) -> str:
    """Return a truncated SHA-256 hash of text."""
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()[:length]
