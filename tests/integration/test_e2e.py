"""End-to-end pipeline checks with offline model/tokenizer doubles."""

from __future__ import annotations

from pathlib import Path

from insight_extractor.extractor import InsightExtractor
from insight_extractor.models import ExtractResult, KeywordStats, SemanticHit, SentenceScore
from tests.integration.fakes import attach_fakes


class TestFullPipeline:
    """Run the complete extraction pipeline end-to-end."""

    def test_full_pipeline(self, integration_extractor: InsightExtractor, sample_text: str) -> None:
        """extract() on sample_text produces a valid ExtractResult."""
        result = integration_extractor.extract(sample_text)

        assert isinstance(result, ExtractResult)
        assert result.input_hash != ""
        assert isinstance(result.input_hash, str)
        assert result.word_count > 0
        assert isinstance(result.regex_entities, dict)
        assert isinstance(result.dynamic_keyword_matches, dict)
        assert isinstance(result.semantic_keywords, list)
        assert isinstance(result.key_sentences, list)
        assert isinstance(result.newly_expanded_keywords, list)
        assert isinstance(result.total_tracked_keywords, int)
        assert isinstance(result.keyword_stats, KeywordStats)
        assert isinstance(result.timestamp, str)
        assert "T" in result.timestamp or result.timestamp.endswith("Z")

        assert "CVE_ID" in result.regex_entities
        assert result.dynamic_keyword_matches
        assert result.semantic_keywords
        assert all(isinstance(hit, SemanticHit) for hit in result.semantic_keywords)
        if result.key_sentences:
            assert isinstance(result.key_sentences[0], SentenceScore)
            assert result.key_sentences[0].sentence
            assert 0.0 <= result.key_sentences[0].score <= 1.0

        assert result.keyword_stats.total_keywords == result.total_tracked_keywords
        assert result.total_tracked_keywords == len(integration_extractor.thread_keywords)

    def test_dynamic_keyword_matches_present(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        """Seed keywords present in the text appear under DYNAMIC_KEYWORD matches."""
        result = integration_extractor.extract(sample_text)
        assert result.dynamic_keyword_matches, "Expected at least one dynamic keyword match"
        assert "DYNAMIC_KEYWORD" in result.dynamic_keyword_matches
        matched = " ".join(result.dynamic_keyword_matches["DYNAMIC_KEYWORD"]).lower()
        assert any(
            keyword in matched
            for keyword in ("ransomware", "cve", "bert", "conti", "exploit", "malware")
        )


class TestMarkdownOutput:
    """Markdown report generation end-to-end."""

    def test_markdown_output(
        self,
        integration_extractor: InsightExtractor,
        sample_text: str,
    ) -> None:
        result = integration_extractor.extract(sample_text)
        md_path = integration_extractor.save_results_to_markdown(result, "e2e_report.md")

        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert content.startswith("# ")
        assert result.input_hash in content
        assert "## Regex Entities" in content
        assert "## Dynamic Keyword Matches" in content
        assert "## Semantic Keywords" in content
        assert "## Key Sentences" in content


class TestStatePersistence:
    """Save + load preserves keywords end-to-end."""

    def test_state_persistence(
        self,
        integration_extractor: InsightExtractor,
        temp_dir: Path,
        sample_text: str,
    ) -> None:
        integration_extractor.extract(sample_text)
        pre_keywords = set(integration_extractor.top_keywords(n=50))
        assert pre_keywords, "Expected some keywords before saving"

        state_path = temp_dir / "e2e_state.json"
        integration_extractor.save_state(state_path)
        assert state_path.exists()

        fresh = InsightExtractor(
            seed_keywords=["ransomware", "CVE"],
            output_dir=temp_dir,
            top_k=10,
            similarity_threshold=0.0,
        )
        attach_fakes(fresh)
        assert fresh.load_state(state_path) is True

        post_keywords = set(fresh.top_keywords(n=50))
        assert post_keywords == pre_keywords

    def test_multiple_extractions_accumulate(
        self,
        integration_extractor: InsightExtractor,
        sample_text: str,
        short_text: str,
    ) -> None:
        """Running extract multiple times keeps a queryable keyword bank."""
        r1 = integration_extractor.extract(sample_text)
        r2 = integration_extractor.extract(short_text)

        assert isinstance(r1, ExtractResult)
        assert isinstance(r2, ExtractResult)
        assert r1.word_count > 0
        assert r2.word_count > 0
        assert r2.total_tracked_keywords >= r1.total_tracked_keywords

        top = integration_extractor.top_keywords(n=5)
        assert isinstance(top, list)
        assert top
