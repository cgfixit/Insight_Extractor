"""Integration tests for InsightExtractor with mocked ML dependencies."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from insight_extractor.extractor import InsightExtractor
from insight_extractor.models import ExtractResult, KeywordStats

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_model() -> MagicMock:
    """Return a mock SentenceTransformer-like model."""
    mock = MagicMock()
    mock.encode = MagicMock(return_value=np.random.rand(10, 384).astype(np.float32))
    return mock


@pytest.fixture
def mock_tokenizer() -> MagicMock:
    """Return a mock HuggingFace tokenizer."""
    mock = MagicMock()
    mock.encode = MagicMock(
        side_effect=lambda text, **kw: list(range(max(1, len(text.split()) * 2)))
    )
    mock.decode = MagicMock(side_effect=lambda tokens, **kw: " ".join(["word"] * len(tokens)))
    return mock


@pytest.fixture
def extractor(mock_model: MagicMock, mock_tokenizer: MagicMock) -> InsightExtractor:
    """Return an InsightExtractor with mocked heavy dependencies."""
    with (
        patch(
            "insight_extractor.extractor.SentenceTransformer",
            return_value=mock_model,
        ),
        patch(
            "insight_extractor.tokenizer.AutoTokenizer.from_pretrained",
            return_value=mock_tokenizer,
        ),
    ):
        ext = InsightExtractor(
            model_name="all-MiniLM-L6-v2",
            config_path=None,
            seed_keywords=["ransomware", "CVE"],
            top_k=5,
            similarity_threshold=0.5,
            enable_dynamic_regex=True,
        )
    return ext


@pytest.fixture
def extractor_no_dynamic(mock_model: MagicMock, mock_tokenizer: MagicMock) -> InsightExtractor:
    """Return an extractor with dynamic regex disabled."""
    with (
        patch(
            "insight_extractor.extractor.SentenceTransformer",
            return_value=mock_model,
        ),
        patch(
            "insight_extractor.tokenizer.AutoTokenizer.from_pretrained",
            return_value=mock_tokenizer,
        ),
    ):
        ext = InsightExtractor(
            model_name="all-MiniLM-L6-v2",
            config_path=None,
            seed_keywords=["ransomware", "CVE"],
            top_k=5,
            similarity_threshold=0.5,
            enable_dynamic_regex=False,
        )
    return ext


# ── Tests ────────────────────────────────────────────────────────────────────


class TestExtract:
    """Core extraction behaviour."""

    def test_extract_returns_extract_result(
        self, extractor: InsightExtractor, sample_text: str
    ) -> None:
        result = extractor.extract(sample_text)
        assert isinstance(result, ExtractResult)

    def test_extract_has_timestamp(self, extractor: InsightExtractor, sample_text: str) -> None:
        result = extractor.extract(sample_text)
        assert isinstance(result.timestamp, str)
        assert result.timestamp != ""

    def test_extract_regex_only(
        self, extractor_no_dynamic: InsightExtractor, sample_text: str
    ) -> None:
        """With dynamic regex disabled, static regex entities should still be found."""
        result = extractor_no_dynamic.extract(sample_text)
        assert isinstance(result, ExtractResult)
        # keyword_stats is a KeywordStats object, not a list
        assert isinstance(result.keyword_stats, KeywordStats)
        assert result.dynamic_keyword_matches == {}

    def test_keyword_expansion_after_extract(
        self, extractor: InsightExtractor, sample_text: str
    ) -> None:
        """After extraction, top_keywords returns list of (keyword, count) tuples."""
        extractor.extract(sample_text)
        top = extractor.top_keywords(n=20)
        assert isinstance(top, list)
        # Each element is a (keyword, count) tuple
        for item in top:
            assert isinstance(item, tuple)
            assert len(item) == 2
            kw, count = item
            assert isinstance(kw, str)
            assert isinstance(count, int)
        # At least one seed keyword should appear
        kw_names = [item[0] for item in top]
        assert any(k in kw_names for k in ["ransomware", "CVE"])


class TestPersistence:
    """Save / load state round-trip."""

    def test_save_load_state(
        self,
        extractor: InsightExtractor,
        temp_dir: Path,
        sample_text: str,
    ) -> None:
        extractor.extract(sample_text)
        state_path = temp_dir / "state.json"
        extractor.save_state(state_path)
        assert state_path.exists()

        # Load into a fresh extractor
        with (
            patch(
                "insight_extractor.extractor.SentenceTransformer",
                return_value=extractor._model,
            ),
            patch(
                "insight_extractor.tokenizer.AutoTokenizer.from_pretrained",
                return_value=MagicMock(),
            ),
        ):
            fresh = InsightExtractor(
                model_name="all-MiniLM-L6-v2",
                config_path=None,
                seed_keywords=[],
                top_k=5,
                similarity_threshold=0.5,
            )
            fresh.load_state(state_path)

        loaded_top = fresh.top_keywords(n=20)
        original_top = extractor.top_keywords(n=20)
        assert isinstance(loaded_top, list)
        # Keyword names should be preserved across save/load
        loaded_kws = {item[0] for item in loaded_top}
        original_kws = {item[0] for item in original_top}
        assert loaded_kws == original_kws


class TestMarkdownOutput:
    """Markdown file generation."""

    def test_save_results_to_markdown(
        self,
        extractor: InsightExtractor,
        temp_dir: Path,
        sample_text: str,
    ) -> None:
        extractor_with_dir = InsightExtractor(
            seed_keywords=["ransomware", "CVE"],
            output_dir=temp_dir,
        )
        result = extractor_with_dir.extract(sample_text, update_keywords=False)
        md_path = extractor_with_dir.save_results_to_markdown(result, "report.md")
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "# Insight Extraction Results" in content
        assert len(content) > 0


class TestTopKeywords:
    """Frequency tracking."""

    def test_top_keywords_returns_tuples(
        self, extractor: InsightExtractor, sample_text: str
    ) -> None:
        extractor.extract(sample_text)
        top = extractor.top_keywords(n=3)
        assert len(top) <= 3
        assert isinstance(top, list)
        for item in top:
            assert isinstance(item, tuple)
            kw, count = item
            assert isinstance(kw, str)
            assert isinstance(count, int)

    def test_top_keywords_empty(self, extractor: InsightExtractor) -> None:
        """Before extraction, top_keywords returns seed keywords."""
        top = extractor.top_keywords(n=5)
        assert isinstance(top, list)


class TestKeywordStats:
    """KeywordStats retrieval."""

    def test_get_keyword_stats(self, extractor: InsightExtractor) -> None:
        stats = extractor.get_keyword_stats()
        assert isinstance(stats, KeywordStats)
        assert isinstance(stats.total_keywords, int)
        assert stats.total_keywords >= 0
        assert isinstance(stats.category_counts, dict)
        assert isinstance(stats.stem_mode, str)

    def test_keyword_stats_from_extract_result(
        self, extractor: InsightExtractor, sample_text: str
    ) -> None:
        result = extractor.extract(sample_text)
        assert isinstance(result.keyword_stats, KeywordStats)
        assert result.keyword_stats.total_keywords == len(extractor.thread_keywords)


class TestInitCustomSeeds:
    """Custom seed keywords are used at init time."""

    def test_init_custom_seeds(self) -> None:
        ext = InsightExtractor(
            model_name="all-MiniLM-L6-v2",
            seed_keywords=["custom_seed_1", "custom_seed_2"],
        )
        kw_names = [kw for kw, _ in ext.top_keywords(n=10)]
        assert "custom_seed_1" in kw_names or "custom_seed_2" in kw_names


class TestDisabledDynamicRegex:
    """When dynamic regex is disabled, dynamic_keyword_matches should be empty."""

    def test_disabled_dynamic_regex(
        self,
        extractor_no_dynamic: InsightExtractor,
        sample_text: str,
    ) -> None:
        result = extractor_no_dynamic.extract(sample_text)
        assert isinstance(result, ExtractResult)
        assert result.dynamic_keyword_matches == {}
