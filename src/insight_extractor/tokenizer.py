"""Sentence tokenization using HuggingFace AutoTokenizer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from insight_extractor.exceptions import ModelLoadError
from insight_extractor.utils import split_sentences

if TYPE_CHECKING:
    from collections.abc import Sequence

    from transformers import PreTrainedTokenizerBase

logger = logging.getLogger("insight_extractor")


class SentenceTokenizer:
    """Sentence-level tokenization using the model's HuggingFace tokenizer."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._tokenizer: PreTrainedTokenizerBase | None = None

    @property
    def tokenizer(self) -> PreTrainedTokenizerBase:
        """Lazy-load the AutoTokenizer on first access."""
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            # transformers>=5 types from_pretrained as `TokenizersBackend | None`; None means
            # the repo ships no tokenizer files, which this pipeline cannot work without.
            loaded = AutoTokenizer.from_pretrained(self.model_name)
            if loaded is None:
                raise ModelLoadError(f"No tokenizer found for model '{self.model_name}'")
            self._tokenizer = loaded
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens for text."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def chunk_text(self, text: str, max_tokens: int = 512, overlap: int = 50) -> list[str]:
        """
        Split text into chunks of max_tokens with sliding window overlap.
        Uses the model's tokenizer for accurate token counting.

        With a fast tokenizer each chunk is the verbatim source span its token
        window covers; a slow tokenizer falls back to decoding the window.

        Raises ValueError unless max_tokens is a positive integer and overlap
        is an integer in [0, max_tokens). Validation never loads the tokenizer.
        """
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if (
            isinstance(overlap, bool)
            or not isinstance(overlap, int)
            or not 0 <= overlap < max_tokens
        ):
            raise ValueError("overlap must be an integer in [0, max_tokens)")
        # decode() of an uncased WordPiece window is not the source text: it lowercases,
        # re-spaces punctuation ("https : / / www"), drops [UNK] glyphs, and can start
        # with "##" pieces. Offsets let fast tokenizers emit the original span instead.
        offsets: Sequence[tuple[int, int]] | None = None
        tokens: list[int] = []
        if getattr(self.tokenizer, "is_fast", False):
            encoding = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
            offsets = encoding["offset_mapping"]
            token_count = len(offsets)
        else:
            tokens = self.tokenizer.encode(text, add_special_tokens=False)
            token_count = len(tokens)
        if token_count <= max_tokens:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < token_count:
            end = min(start + max_tokens, token_count)
            if offsets is not None:
                chunks.append(text[offsets[start][0] : offsets[end - 1][1]])
            else:
                decoded = self.tokenizer.decode(tokens[start:end], skip_special_tokens=True)
                # decode() is typed `str | list[str]`; a single id list always yields one str.
                chunks.append(decoded if isinstance(decoded, str) else " ".join(decoded))
            if end == token_count:
                break
            start = end - overlap
        return chunks

    def tokenize_sentences(self, text: str, max_tokens: int = 512) -> list[str]:
        """
        Split text with utils.split_sentences, then ensure each sentence
        is within the max_tokens budget by chunking oversized sentences.

        Raises ValueError for a nonpositive or non-integer max_tokens, even
        for empty text. Oversized sentences overlap by min(50, max_tokens - 1).
        """
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        raw_sentences = split_sentences(text)
        if not raw_sentences:
            return [text] if text.strip() else []

        result: list[str] = []
        for sentence in raw_sentences:
            if self.count_tokens(sentence) > max_tokens:
                result.extend(
                    self.chunk_text(
                        sentence, max_tokens=max_tokens, overlap=min(50, max_tokens - 1)
                    )
                )
            else:
                result.append(sentence)
        return result
