"""CLI entry point for insight_extractor."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from insight_extractor.exceptions import ModelLoadError, StateLoadError
from insight_extractor.extractor import InsightExtractor
from insight_extractor.utils import setup_logging

SAMPLE_TEXT = """
        On May 11 2026, the Nitrogen ransomware group claimed to have stolen 8 terabytes
        of data from Foxconn North American facilities including Mount Pleasant Wisconsin.
        The group used leaked Conti 2 builder code targeting VMware ESXi environments.
        Coveware found a critical coding bug in the ESXi encryptor: files are encrypted
        with the wrong public key, making recovery impossible even after paying the ransom.
        Ryan Montgomery demonstrated live OSINT on Tucker Carlson, retrieving SSN and
        driver license number from the National Public Data breach of 2.9 billion records.
        He also showed how Roblox age-verified accounts can be purchased on eBay for
        a few dollars, bypassing facial biometric verification entirely.
        PsyClaw uses BERT embeddings with ChromaDB and BM25 hybrid retrieval via RRF fusion.
        CVE-2026-48710 affects the Starlette framework used in millions of AI agent pipelines.
        """


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Extract insights from a UTF-8 text file.")
    parser.add_argument("input_path", nargs="?", type=Path, help="UTF-8 text file to analyze")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    setup_logging()
    extractor = InsightExtractor()
    state_path = Path("insight_extractor_state.json")
    try:
        extractor.load_state(state_path)
    except StateLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.input_path is not None:
        try:
            text = args.input_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"error: failed to read input file '{args.input_path}': {exc}", file=sys.stderr)
            return 1
    else:
        text = SAMPLE_TEXT

    try:
        results = extractor.extract(text)
    except ModelLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("\n=== REGEX ENTITIES ===")
    for etype, vals in results.regex_entities.items():
        print(f"  {etype}: {vals}")

    print("\n=== DYNAMIC KEYWORD MATCHES ===")
    for etype, vals in results.dynamic_keyword_matches.items():
        print(f"  {etype}: {vals[:10]}{' ...' if len(vals) > 10 else ''}")

    print("\n=== SEMANTIC KEYWORD HITS (top 10) ===")
    for hit in results.semantic_keywords[:10]:
        context = " ".join(hit.context.split())
        print(f"  [{hit.score:.3f}] {hit.keyword}")
        print(f"           ...{context[:80]}...")

    print("\n=== KEY SENTENCES ===")
    for s in results.key_sentences:
        sentence = " ".join(s.sentence.split())
        print(f"  [{s.score:.3f}] {sentence[:120]}")

    print(f"\n=== DYNAMIC EXPANSION: +{len(results.newly_expanded_keywords)} new keywords ===")
    if results.newly_expanded_keywords:
        print(f"  {results.newly_expanded_keywords}")

    print(f"\nTotal tracked keywords: {results.total_tracked_keywords}")

    md_path = extractor.save_results_to_markdown(results)
    print(f"\nResults saved to: {md_path}")

    stats = results.keyword_stats
    print("\n=== KEYWORD STATS ===")
    print(f"  Categories: {stats.category_counts}")
    print(f"  Stem mode: {stats.stem_mode}")

    extractor.save_state(state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
