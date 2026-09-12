"""Integration coverage for InsightExtractor orchestration (offline ML doubles)."""

from __future__ import annotations

from pathlib import Path

from insight_extractor.extractor import InsightExtractor
from insight_extractor.models import ExtractResult, KeywordStats
from tests.integration.fakes import attach_fakes


class TestExtract:
    """Core extraction behaviour against the live ExtractResult contract."""

    def test_extract_returns_extract_result(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        result = integration_extractor.extract(sample_text)
        assert isinstance(result, ExtractResult)

    def test_extract_has_timestamp(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        result = integration_extractor.extract(sample_text)
        assert isinstance(result.timestamp, str)
        assert result.timestamp != ""
        assert "T" in result.timestamp or result.timestamp.endswith("Z")

    def test_extract_regex_only(
        self, integration_extractor_no_dynamic: InsightExtractor, sample_text: str
    ) -> None:
        """With dynamic regex disabled, static regex entities should still be found."""
        result = integration_extractor_no_dynamic.extract(sample_text)
        assert isinstance(result, ExtractResult)
        assert isinstance(result.keyword_stats, KeywordStats)
        assert result.dynamic_keyword_matches == {}
        assert "CVE_ID" in result.regex_entities

    def test_keyword_expansion_after_extract(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        """After extraction, top_keywords returns list of (keyword, count) tuples."""
        integration_extractor.extract(sample_text)
        top = integration_extractor.top_keywords(n=20)
        assert isinstance(top, list)
        for item in top:
            assert isinstance(item, tuple)
            assert len(item) == 2
            kw, count = item
            assert isinstance(kw, str)
            assert isinstance(count, int)
        kw_names = [item[0] for item in top]
        assert any(k in kw_names for k in ["ransomware", "CVE"])


class TestPersistence:
    """Save / load state round-trip."""

    def test_save_load_state(
        self,
        integration_extractor: InsightExtractor,
        temp_dir: Path,
        sample_text: str,
    ) -> None:
        integration_extractor.extract(sample_text)
        state_path = temp_dir / "state.json"
        integration_extractor.save_state(state_path)
        assert state_path.exists()

        fresh = InsightExtractor(
            seed_keywords=["ransomware", "CVE"],
            output_dir=temp_dir,
            top_k=5,
            similarity_threshold=0.0,
        )
        attach_fakes(fresh)
        assert fresh.load_state(state_path) is True

        loaded_top = fresh.top_keywords(n=20)
        original_top = integration_extractor.top_keywords(n=20)
        assert {item[0] for item in loaded_top} == {item[0] for item in original_top}


class TestMarkdownOutput:
    """Markdown file generation."""

    def test_save_results_to_markdown(
        self,
        integration_extractor: InsightExtractor,
        sample_text: str,
    ) -> None:
        result = integration_extractor.extract(sample_text, update_keywords=False)
        md_path = integration_extractor.save_results_to_markdown(result, "report.md")
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "# Insight Extraction Results" in content
        assert "## Regex Entities" in content
        assert result.input_hash in content


class TestTopKeywords:
    """Frequency tracking."""

    def test_top_keywords_returns_tuples(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        integration_extractor.extract(sample_text)
        top = integration_extractor.top_keywords(n=3)
        assert len(top) <= 3
        assert isinstance(top, list)
        for item in top:
            assert isinstance(item, tuple)
            kw, count = item
            assert isinstance(kw, str)
            assert isinstance(count, int)

    def test_top_keywords_empty(self, integration_extractor: InsightExtractor) -> None:
        """Before extraction, top_keywords still returns seed keyword frequencies."""
        top = integration_extractor.top_keywords(n=5)
        assert isinstance(top, list)
        assert top


class TestKeywordStats:
    """KeywordStats retrieval."""

    def test_get_keyword_stats(self, integration_extractor: InsightExtractor) -> None:
        stats = integration_extractor.get_keyword_stats()
        assert isinstance(stats, KeywordStats)
        assert stats.total_keywords >= 0
        assert isinstance(stats.category_counts, dict)
        assert isinstance(stats.stem_mode, str)

    def test_keyword_stats_from_extract_result(
        self, integration_extractor: InsightExtractor, sample_text: str
    ) -> None:
        result = integration_extractor.extract(sample_text)
        assert isinstance(result.keyword_stats, KeywordStats)
        assert result.keyword_stats.total_keywords == len(integration_extractor.thread_keywords)


class TestInitCustomSeeds:
    """Custom seed keywords are used at init time."""

    def test_init_custom_seeds(self, temp_dir: Path) -> None:
        ext = attach_fakes(
            InsightExtractor(
                seed_keywords=["custom_seed_1", "custom_seed_2"],
                output_dir=temp_dir,
            )
        )
        kw_names = [kw for kw, _ in ext.top_keywords(n=10)]
        assert "custom_seed_1" in kw_names
        assert "custom_seed_2" in kw_names


class TestDisabledDynamicRegex:
    """When dynamic regex is disabled, dynamic_keyword_matches should be empty."""

    def test_disabled_dynamic_regex(
        self,
        integration_extractor_no_dynamic: InsightExtractor,
        sample_text: str,
    ) -> None:
        result = integration_extractor_no_dynamic.extract(sample_text)
        assert isinstance(result, ExtractResult)
        assert result.dynamic_keyword_matches == {}
