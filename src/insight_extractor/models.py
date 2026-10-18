from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StrictStr, field_validator

from insight_extractor.config import KeywordCategory, StemMode


class _SavedState(BaseModel):
    """Validate persisted fields without coercing malformed JSON containers or scalars."""

    thread_keywords: list[StrictStr] = Field(default_factory=list)
    keyword_freq: dict[str, Annotated[int, Field(strict=True, ge=0)]] = Field(default_factory=dict)
    keyword_categories: dict[str, KeywordCategory] = Field(default_factory=dict)
    stem_mode: StemMode
    similarity_threshold: Annotated[float, Field(strict=True, allow_inf_nan=False)]
    model_name: Annotated[str, Field(strict=True, min_length=1)]

    @field_validator("keyword_categories", mode="before")
    @classmethod
    def remap_legacy_categories(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: KeywordCategory.AI_SAFETY.value if category == "child_safety" else category
                for key, category in value.items()
            }
        return value


class MatchInfo(BaseModel):
    match: str
    keyword: str
    start: int
    end: int
    stemmed: bool


class KeywordStats(BaseModel):
    total_keywords: int
    total_categories: int
    category_counts: dict[str, int]
    top_keywords: list[tuple[str, int]]
    stem_mode: str
    case_sensitive: bool
    custom_suffixes: tuple[str, ...]
    last_updated: str | None = None


class SemanticHit(BaseModel):
    keyword: str
    score: float
    context: str


class SentenceScore(BaseModel):
    sentence: str
    score: float


class ExtractResult(BaseModel):
    timestamp: str
    input_hash: str
    word_count: int
    regex_entities: dict[str, list[str]]
    dynamic_keyword_matches: dict[str, list[str]]
    semantic_keywords: list[SemanticHit]
    key_sentences: list[SentenceScore]
    newly_expanded_keywords: list[str]
    total_tracked_keywords: int
    keyword_stats: KeywordStats

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v
