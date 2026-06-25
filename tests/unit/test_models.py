"""Tests for Pydantic v2 data models — verifies the actual field schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from insight_extractor.models import (
    ExtractResult,
    KeywordStats,
    MatchInfo,
    SemanticHit,
    SentenceScore,
)


class TestMatchInfo:
    """MatchInfo represents a single keyword/pattern match in text."""

    def test_match_info_valid(self) -> None:
        mi = MatchInfo(
            match="ransomware",
            keyword="ransomware",
            start=10,
            end=20,
            stemmed=False,
        )
        assert mi.match == "ransomware"
        assert mi.keyword == "ransomware"
        assert mi.start == 10
        assert mi.end == 20
        assert mi.stemmed is False

    def test_match_info_stemmed_flag(self) -> None:
        mi = MatchInfo(match="ransomwares", keyword="ransomware", start=0, end=11, stemmed=True)
        assert mi.stemmed is True

    def test_match_info_invalid_types(self) -> None:
        with pytest.raises(ValidationError):
            MatchInfo(
                match=123,  # type: ignore[arg-type]
                keyword="kw",
                start="not_int",  # type: ignore[arg-type]
                end=5,
                stemmed=False,
            )


class TestKeywordStats:
    """KeywordStats aggregates global keyword frequency and category information."""

    def test_keyword_stats_valid(self) -> None:
        ks = KeywordStats(
            total_keywords=50,
            total_categories=4,
            category_counts={"threat_intel": 20, "osint": 10, "general": 20},
            top_keywords=[("ransomware", 7), ("CVE", 3)],
            stem_mode="stem",
            case_sensitive=False,
            custom_suffixes=("s", "ing", "ed"),
            last_updated="2026-01-01T00:00:00Z",
        )
        assert ks.total_keywords == 50
        assert ks.total_categories == 4
        assert ks.category_counts["threat_intel"] == 20
        assert ("ransomware", 7) in ks.top_keywords
        assert ks.stem_mode == "stem"
        assert ks.case_sensitive is False

    def test_keyword_stats_last_updated_optional(self) -> None:
        ks = KeywordStats(
            total_keywords=1,
            total_categories=1,
            category_counts={"general": 1},
            top_keywords=[("x", 1)],
            stem_mode="exact",
            case_sensitive=True,
            custom_suffixes=(),
        )
        assert ks.last_updated is None


class TestSemanticHit:
    """SemanticHit represents a vector-similarity match."""

    def test_semantic_hit_valid(self) -> None:
        sh = SemanticHit(
            keyword="phishing",
            score=0.9234,
            context="The phishing campaign targeted finance.",
        )
        assert sh.keyword == "phishing"
        assert sh.score == pytest.approx(0.9234)
        assert "phishing" in sh.context

    def test_semantic_hit_invalid_score_type(self) -> None:
        with pytest.raises(ValidationError):
            SemanticHit(
                keyword="x",
                score="high",  # type: ignore[arg-type]
                context="test",
            )


class TestSentenceScore:
    """SentenceScore ranks sentences by relevance."""

    def test_sentence_score_valid(self) -> None:
        ss = SentenceScore(
            sentence="The ransomware attack began at midnight.",
            score=0.87,
        )
        assert ss.sentence == "The ransomware attack began at midnight."
        assert ss.score == pytest.approx(0.87)

    def test_sentence_score_invalid_score(self) -> None:
        with pytest.raises(ValidationError):
            SentenceScore(sentence="s", score="high")  # type: ignore[arg-type]


class TestExtractResult:
    """ExtractResult is the top-level output of the pipeline."""

    def _make_stats(self) -> KeywordStats:
        return KeywordStats(
            total_keywords=2,
            total_categories=1,
            category_counts={"general": 2},
            top_keywords=[("ransomware", 3)],
            stem_mode="stem",
            case_sensitive=False,
            custom_suffixes=("s",),
        )

    def test_extract_result_valid(self) -> None:
        er = ExtractResult(
            timestamp="2026-01-15T10:30:00Z",
            input_hash="a1b2c3d4",
            word_count=42,
            regex_entities={"CVE_ID": ["CVE-2026-1234"]},
            dynamic_keyword_matches={"DYNAMIC_KEYWORD": ["ransomware"]},
            semantic_keywords=[SemanticHit(keyword="exploit", score=0.91, context="exploit used")],
            key_sentences=[SentenceScore(sentence="The exploit was public.", score=0.91)],
            newly_expanded_keywords=["lateral movement"],
            total_tracked_keywords=70,
            keyword_stats=self._make_stats(),
        )
        assert er.input_hash == "a1b2c3d4"
        assert er.word_count == 42
        assert er.regex_entities["CVE_ID"] == ["CVE-2026-1234"]
        assert er.total_tracked_keywords == 70

    def test_extract_result_timestamp_validation(self) -> None:
        er = ExtractResult(
            timestamp="2026-05-11T14:00:00Z",
            input_hash="abc",
            word_count=5,
            regex_entities={},
            dynamic_keyword_matches={},
            semantic_keywords=[],
            key_sentences=[],
            newly_expanded_keywords=[],
            total_tracked_keywords=0,
            keyword_stats=self._make_stats(),
        )
        assert er.timestamp == "2026-05-11T14:00:00Z"

    def test_extract_result_invalid_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            ExtractResult(
                timestamp="not-a-real-timestamp",
                input_hash="abc",
                word_count=5,
                regex_entities={},
                dynamic_keyword_matches={},
                semantic_keywords=[],
                key_sentences=[],
                newly_expanded_keywords=[],
                total_tracked_keywords=0,
                keyword_stats=self._make_stats(),
            )


class TestModelSerialization:
    """Round-trip serialization."""

    def test_match_info_roundtrip(self) -> None:
        mi = MatchInfo(match="CVE-2026-1234", keyword="CVE", start=0, end=13, stemmed=False)
        d = mi.model_dump()
        assert isinstance(d, dict)
        assert d["keyword"] == "CVE"
        assert d["start"] == 0
        assert d["end"] == 13

    def test_match_info_json_roundtrip(self) -> None:
        original = MatchInfo(
            match="ransomware", keyword="ransomware", start=4, end=14, stemmed=True
        )
        restored = MatchInfo.model_validate_json(original.model_dump_json())
        assert restored.match == original.match
        assert restored.stemmed == original.stemmed

    def test_semantic_hit_json_roundtrip(self) -> None:
        original = SemanticHit(keyword="phishing", score=0.75, context="phishing email")
        restored = SemanticHit.model_validate_json(original.model_dump_json())
        assert restored.keyword == original.keyword
        assert restored.score == pytest.approx(original.score)
