"""InsightExtractor encodes each keyword and sentence unit once, without model weights."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

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


def test_normalized_float32_scores_preserve_rank_threshold_and_zero_rows(tmp_path: Path) -> None:
    high = "The quasar produced a significant amount of light."
    low = "The source produced a relatively weak signal."
    zero = "No meaningful signal was detected in this region."
    vectors = {
        "anchor": [3.0, 0.0],
        "quasar": [4.0, 3.0],
        "noise": [0.0, 0.0],
        high: [4.0, 3.0],
        low: [3.0, 4.0],
        zero: [0.0, 0.0],
    }

    class Float32Model:
        def encode(self, texts: list[str], **_kwargs: Any) -> np.ndarray[Any, np.dtype[np.float32]]:
            return np.array([vectors.get(text, [0.0, 0.0]) for text in texts], dtype=np.float32)

    extractor = InsightExtractor(
        seed_keywords=["anchor", "zero vector"], similarity_threshold=0.75, output_dir=tmp_path
    )
    extractor._model = Float32Model()
    extractor._tokenizer = SentenceSplitTokenizer()
    result = extractor.extract(f"{low} {zero} {high}", update_keywords=False)

    expected = cosine_similarity(
        np.array([vectors[sentence] for sentence in (high, low, zero)], dtype=np.float32),
        np.array([vectors["anchor"]], dtype=np.float32),
    )
    assert [(hit.keyword, hit.context, hit.score) for hit in result.semantic_keywords] == [
        ("anchor", high, round(float(expected[0, 0]), 6))
    ]
    assert [hit.sentence for hit in result.key_sentences] == [high, low, zero]
    np.testing.assert_allclose([hit.score for hit in result.key_sentences], expected[:, 0])
    assert extractor.update_thread_keywords("quasar quasar noise noise") == ["quasar"]
