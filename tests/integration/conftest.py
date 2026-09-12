"""Shared fixtures for optional integration tests (no model download)."""

from __future__ import annotations

from pathlib import Path

import pytest

from insight_extractor.extractor import InsightExtractor
from tests.integration.fakes import attach_fakes


@pytest.fixture
def integration_extractor(temp_dir: Path) -> InsightExtractor:
    """Extractor with seed keywords and offline ML boundaries."""
    extractor = InsightExtractor(
        seed_keywords=["ransomware", "CVE", "exploit", "malware", "BERT", "Conti"],
        output_dir=temp_dir,
        top_k=10,
        similarity_threshold=0.0,
        enable_dynamic_regex=True,
    )
    return attach_fakes(extractor)


@pytest.fixture
def integration_extractor_no_dynamic(temp_dir: Path) -> InsightExtractor:
    """Extractor with dynamic keyword regex disabled."""
    extractor = InsightExtractor(
        seed_keywords=["ransomware", "CVE"],
        output_dir=temp_dir,
        top_k=5,
        similarity_threshold=0.0,
        enable_dynamic_regex=False,
    )
    return attach_fakes(extractor)
