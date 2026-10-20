"""InsightExtractor encodes each keyword and sentence unit once, without model weights."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from insight_extractor.extractor import InsightExtractor


class TextModel:
    """Embeds each text independently of its batch position, like the real model."""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def encode(
        self,
        texts: str | list[str],
        *_args: Any,
        **_kwargs: Any,
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        items = [texts] if isinstance(texts, str) else list(texts)
        self.batches.append(items)
        return np.array(
            [[float(len(item)), float(sum(map(ord, item)) % 97), 1.0] for item in items]
        )


class SentenceSplitTokenizer:
    def tokenize_sentences(self, text: str, *, max_tokens: int = 512) -> list[str]:
        del max_tokens
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def test_keyword_expansion_encodes_only_new_keywords(tmp_path: Path) -> None:
    extractor = InsightExtractor(
        seed_keywords=["anchor", "known"], similarity_threshold=0.0, output_dir=tmp_path
    )
    model = TextModel()
    extractor._model = model

    added = extractor.update_thread_keywords("quasar quasar photometry telescope observatory")
    incremental = extractor._keyword_embeddings
    extractor._recompute_keyword_embeddings()

    assert added
    assert model.batches[0] == ["anchor", "known"]
    assert model.batches[2] == added
    assert incremental is not None and extractor._keyword_embeddings is not None
    np.testing.assert_allclose(incremental, extractor._keyword_embeddings)


def test_extract_encodes_each_sentence_unit_once(tmp_path: Path) -> None:
    extractor = InsightExtractor(
        seed_keywords=["ransomware", "exploit"], similarity_threshold=0.0, output_dir=tmp_path
    )
    model = TextModel()
    extractor._model = model
    extractor._tokenizer = SentenceSplitTokenizer()
    text = (
        "Ransomware operators exploited a CVE in the VPN gateway. "
        "The exploit chain then reached the domain controller."
    )

    result = extractor.extract(text, update_keywords=False)

    encoded = [unit for batch in model.batches[1:] for unit in batch]
    assert len(encoded) == len(set(encoded)) == 2
    assert extractor._unit_embeddings is None
    standalone = extractor.extract_key_sentences(text, top_n=extractor.top_k)
    assert result.key_sentences == standalone
