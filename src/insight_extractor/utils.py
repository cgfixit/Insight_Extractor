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
# List items and quotes start a paragraph that wrapped continuation lines may join.
_BLOCK_START = re.compile(r"[-*+]\s|\d{1,3}[.)]\s|>")
# A punctuation split must not end on a list ordinal ("> 4.") or a common abbreviation;
# "U.S. government" otherwise became the top-ranked fragment "government and ...".
_NO_BREAK_AFTER = re.compile(
    r"^(?:[>#*+-]\s*)*\d{1,3}\.$|(?<![\w.])(?:vs|e\.g|i\.e|cf|u\.s|u\.k|mrs?|ms|dr|st|fig|approx)\.$",
    re.IGNORECASE,
)
_FRAME_CHARS = " \t|│┃║"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the package logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("insight_extractor")


def truncate_text(text: str, max_length: int = 120, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def split_sentences(text: str) -> list[str]:
    """Split text into whitespace-normalised sentences without merging Markdown lines.

    Hard-wrapped prose lines are joined before splitting on terminal punctuation. Blank
    lines end a paragraph; list items and quotes start one; headings and table rows (two
    or more pipes, or a leading pipe / box-drawing bar) are single units with their outer
    frame removed. Lines without any word character (rules, borders) are dropped.
    """
    units: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            pieces: list[str] = []
            for piece in _SENTENCE_END.split(" ".join(paragraph)):
                if pieces and _NO_BREAK_AFTER.search(pieces[-1]):
                    pieces[-1] = f"{pieces[-1]} {piece}"
                elif piece:
                    pieces.append(piece)
            units.extend(pieces)
            paragraph.clear()

    for line in text.splitlines():
        stripped = " ".join(line.split())
        if not _HAS_WORD.search(stripped):
            flush()
        elif _ATOMIC_LINE.match(stripped) or stripped.count("|") >= 2:
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
