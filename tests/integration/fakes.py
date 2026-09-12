"""Offline model/tokenizer doubles for optional integration tests."""

from __future__ import annotations

from typing import Any

import numpy as np

from insight_extractor.extractor import InsightExtractor


class FakeModel:
    """Deterministic encode stub sized for cosine-similarity orchestration."""

    def encode(
        self,
        texts: str | list[str],
        *_args: Any,
        **_kwargs: Any,
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        items = [texts] if isinstance(texts, str) else list(texts)
        rows = [[float(index), 1.0, 0.5, 0.25] for index, _ in enumerate(items, start=1)]
        return np.array(rows, dtype=np.float64)


class FakeTokenizer:
    """Sentence splitter that never loads HuggingFace weights."""

    def tokenize_sentences(self, text: str, *, max_tokens: int = 512) -> list[str]:
        del max_tokens
        return [part.strip() for part in text.split(".") if len(part.strip()) > 10]


def attach_fakes(extractor: InsightExtractor) -> InsightExtractor:
    """Inject model/tokenizer doubles so lazy loaders never run."""
    extractor._model = FakeModel()
    extractor._tokenizer = FakeTokenizer()
    return extractor
