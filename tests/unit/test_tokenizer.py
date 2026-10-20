"""Tests for SentenceTokenizer without downloading HuggingFace assets."""

from __future__ import annotations

import pytest

import insight_extractor
from insight_extractor.exceptions import ModelLoadError
from insight_extractor.stemmer import DynamicKeywordStemmer
from insight_extractor.tokenizer import SentenceTokenizer


class FakeTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        del add_special_tokens
        return list(range(len(text.split())))

    def decode(self, tokens: list[int], *, skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return " ".join(f"tok{i}" for i in tokens)


def test_lazy_root_imports() -> None:
    assert insight_extractor.DynamicKeywordStemmer is DynamicKeywordStemmer
    missing = "MissingThing"
    with pytest.raises(AttributeError):
        getattr(insight_extractor, missing)


def test_count_tokens_uses_loaded_tokenizer() -> None:
    tokenizer = SentenceTokenizer()
    tokenizer._tokenizer = FakeTokenizer()

    assert tokenizer.count_tokens("one two three") == 3


def test_chunk_text_short_and_long() -> None:
    tokenizer = SentenceTokenizer()
    tokenizer._tokenizer = FakeTokenizer()

    assert tokenizer.chunk_text("one two", max_tokens=5, overlap=1) == ["one two"]
    assert tokenizer.chunk_text("one two three four five six", max_tokens=3, overlap=1) == [
        "tok0 tok1 tok2",
        "tok2 tok3 tok4",
        "tok4 tok5",
    ]


def test_tokenize_sentences_and_empty_text() -> None:
    tokenizer = SentenceTokenizer()
    tokenizer._tokenizer = FakeTokenizer()

    assert tokenizer.tokenize_sentences("") == []
    assert tokenizer.tokenize_sentences("No punctuation") == ["No punctuation"]
    assert tokenizer.tokenize_sentences("First sentence. Second sentence!") == [
        "First sentence.",
        "Second sentence!",
    ]


def test_tokenize_sentences_splits_markdown_lines_but_joins_wrapped_prose() -> None:
    tokenizer = SentenceTokenizer()
    tokenizer._tokenizer = FakeTokenizer()
    text = (
        "## Findings\n"
        "| 1 | Can Grok allow firewall changes? (research) |\n"
        "The actor reused a builder\n"
        "to target ESXi. Then it spread."
    )

    assert tokenizer.tokenize_sentences(text) == [
        "## Findings",
        "1 | Can Grok allow firewall changes? (research)",
        "The actor reused a builder to target ESXi.",
        "Then it spread.",
    ]


def test_tokenizer_property_raises_when_no_tokenizer_files(monkeypatch: pytest.MonkeyPatch) -> None:
    import transformers

    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", lambda *_a, **_k: None)
    tokenizer = SentenceTokenizer("no/tokenizer-here")

    with pytest.raises(ModelLoadError, match="No tokenizer found"):
        _ = tokenizer.tokenizer


class BoundedTokenizer(FakeTokenizer):
    """Record token slices and fail safely if chunking stops making progress."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.slices: list[list[int]] = []

    def decode(self, tokens: list[int], *, skip_special_tokens: bool = True) -> str:
        if len(self.slices) >= self.max_calls:
            raise AssertionError("chunking exceeded the bounded decode budget")
        self.slices.append(tokens)
        return super().decode(tokens, skip_special_tokens=skip_special_tokens)


@pytest.mark.parametrize("token_count", [3, 6, 7])
@pytest.mark.parametrize("overlap", [0, 1, 2])
def test_chunk_text_preserves_ordered_token_coverage(token_count: int, overlap: int) -> None:
    text = " ".join(f"tok{i}" for i in range(token_count))
    tokenizer = SentenceTokenizer()
    fake = BoundedTokenizer(max_calls=token_count)
    tokenizer._tokenizer = fake

    chunks = tokenizer.chunk_text(text, max_tokens=3, overlap=overlap)

    actual = [[int(word[3:]) for word in chunk.split()] for chunk in chunks]
    assert actual[0][0] == 0
    assert all(len(chunk) == 3 for chunk in actual[:-1])
    assert 0 < len(actual[-1]) <= 3
    recovered = list(actual[0])
    for previous, current in zip(actual, actual[1:], strict=False):
        assert previous[-1] < token_count - 1
        assert current[0] == previous[-1] + 1 - overlap
        if overlap:
            assert current[:overlap] == previous[-overlap:]
        recovered.extend(current[overlap:])
    assert recovered == list(range(token_count))


@pytest.mark.parametrize("budget", [1, 2, 49, 50, 51, 512])
def test_oversized_sentence_terminates_with_small_budgets(budget: int) -> None:
    token_count = budget + 3
    tokenizer = SentenceTokenizer()
    fake = BoundedTokenizer(max_calls=token_count)
    tokenizer._tokenizer = fake

    chunks = tokenizer.tokenize_sentences(" ".join(["word"] * token_count), max_tokens=budget)

    assert chunks
    assert all(0 < len(tokens) <= budget for tokens in fake.slices)
    assert fake.slices[0][0] == 0
    assert fake.slices[-1][-1] == token_count - 1
    overlap = min(50, budget - 1)
    for previous, current in zip(fake.slices, fake.slices[1:], strict=False):
        assert current[0] == previous[-1] + 1 - overlap


@pytest.mark.parametrize("text", ["", "short", "one two three four"])
@pytest.mark.parametrize("budget", [0, -1, 1.5, "3", True, None])
def test_invalid_budget_rejected_before_tokenizer_loading(text: str, budget: object) -> None:
    tokenizer = SentenceTokenizer()

    with pytest.raises(ValueError, match="max_tokens"):
        tokenizer.chunk_text(text, max_tokens=budget, overlap=0)
    with pytest.raises(ValueError, match="max_tokens"):
        tokenizer.tokenize_sentences(text, max_tokens=budget)
    assert tokenizer._tokenizer is None


@pytest.mark.parametrize("text", ["", "short", "one two three four"])
@pytest.mark.parametrize("overlap", [-1, 3, 4, 0.5, "1", True, None])
def test_invalid_overlap_rejected_before_tokenizer_loading(text: str, overlap: object) -> None:
    tokenizer = SentenceTokenizer()

    with pytest.raises(ValueError, match="overlap"):
        tokenizer.chunk_text(text, max_tokens=3, overlap=overlap)
    assert tokenizer._tokenizer is None
