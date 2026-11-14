"""Static data invariants for insight_extractor.constants."""

from __future__ import annotations

from collections import Counter

from insight_extractor.constants import THREAD_SEEDS


def test_thread_seeds_are_unique_ignoring_case_and_spacing() -> None:
    # A repeated seed doubled its frequency, topping every report's Top Keywords, and
    # produced two identical semantic-hit rows ("vulnerability" was listed twice).
    counts = Counter(" ".join(seed.casefold().split()) for seed in THREAD_SEEDS)

    assert [seed for seed, count in counts.items() if count > 1] == []
