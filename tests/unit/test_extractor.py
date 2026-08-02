"""Fast unit coverage for InsightExtractor without downloading model weights."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from insight_extractor.config import KeywordCategory
from insight_extractor.exceptions import ConfigLoadError, ModelLoadError, StateLoadError
from insight_extractor.extractor import InsightExtractor, _compile_word_pattern
from insight_extractor.models import ExtractResult, KeywordStats, SemanticHit, SentenceScore


class FakeModel:
    def encode(
        self,
        texts: str | list[str],
        *_args: Any,
        **_kwargs: Any,
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        items = [texts] if isinstance(texts, str) else texts
        rows = []
        for idx, _item in enumerate(items, start=1):
            rows.append([float(idx), 1.0, 0.5, 0.25])
        return np.array(rows, dtype=np.float64)


class FakeTokenizer:
    def tokenize_sentences(self, text: str, *, max_tokens: int = 512) -> list[str]:
        del max_tokens
        return [part.strip() for part in text.split(".") if len(part.strip()) > 10]


class SelectiveModel:
    def encode(
        self,
        texts: str | list[str],
        *_args: Any,
        **_kwargs: Any,
    ) -> np.ndarray[Any, np.dtype[np.float64]]:
        items = [texts] if isinstance(texts, str) else texts
        return np.array(
            [[1.0, 0.0] if item in {"anchor", "known"} else [0.0, 1.0] for item in items]
        )


def build_extractor(tmp_path: Path) -> InsightExtractor:
    extractor = InsightExtractor(
        seed_keywords=["ransomware", "CVE", "exploit"],
        output_dir=tmp_path,
        similarity_threshold=0.0,
        dynamic_expansion_top_n=3,
    )
    extractor._model = FakeModel()
    extractor._tokenizer = FakeTokenizer()
    return extractor


def test_full_pipeline_with_fake_model(tmp_path: Path) -> None:
    extractor = build_extractor(tmp_path)
    text = (
        "Ransomware operators exploited CVE-2026-1234 during a phishing campaign. "
        "The exploit chain touched 192.168.1.10 and ransom@example.com."
    )

    result = extractor.extract(text)

    assert result.word_count > 0
    assert "CVE_ID" in result.regex_entities
    assert "IP_ADDRESS" in result.regex_entities
    assert result.dynamic_keyword_matches
    assert result.semantic_keywords
    assert result.key_sentences
    assert result.keyword_stats.total_keywords == result.total_tracked_keywords

    md_path = extractor.save_results_to_markdown(result)
    assert md_path.exists()
    assert "Insight Extraction Results" in md_path.read_text(encoding="utf-8")


def test_markdown_report_preserves_and_escapes_result_text(tmp_path: Path) -> None:
    payload = (
        "<script>alert(1)</script>\r\n## Injected Heading\n| injected | table | row | **bold**"
    )
    context = f"{'c' * 121} CONTEXTTAIL {payload}"
    sentence = f"{'s' * 201} SENTENCETAIL {payload}"
    result = ExtractResult(
        timestamp="2026-08-01T00:00:00Z",
        input_hash=payload,
        word_count=2,
        regex_entities={payload: [payload]},
        dynamic_keyword_matches={payload: [payload]},
        semantic_keywords=[SemanticHit(keyword=payload, score=0.9, context=context)],
        key_sentences=[SentenceScore(sentence=sentence, score=0.8)],
        newly_expanded_keywords=[payload],
        total_tracked_keywords=1,
        keyword_stats=KeywordStats(
            total_keywords=1,
            total_categories=1,
            category_counts={payload: 1},
            top_keywords=[(payload, 2)],
            stem_mode=payload,
            case_sensitive=False,
            custom_suffixes=(),
            last_updated="2026-08-01T00:00:00Z",
        ),
    )
    extractor = InsightExtractor(seed_keywords=["seed"], output_dir=tmp_path)

    report = extractor.save_results_to_markdown(result).read_text(encoding="utf-8")

    assert "CONTEXTTAIL" in report
    assert "SENTENCETAIL" in report
    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "\n## Injected Heading" not in report
    assert "\n| injected |" not in report
    assert "\\| injected \\| table \\| row \\|" in report


def test_regex_and_dynamic_can_run_without_model(tmp_path: Path) -> None:
    extractor = InsightExtractor(
        seed_keywords=["ransomware"],
        enable_dynamic_regex=True,
        output_dir=tmp_path,
    )
    text = "Ransomware at 10.0.0.1 references CVE-2026-9999 and port 4444."

    assert extractor.extract_regex_entities(text)["CVE_ID"] == ["CVE-2026-9999"]
    assert extractor.extract_regex_entities(text)["PORT_NUMBER"] == ["4444"]
    assert extractor.extract_dynamic_entities(text)


def test_regex_entities_reuse_compiled_patterns(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    text = "Ransomware references CVE-2026-9999."

    first = extractor.extract_regex_entities(text)
    compiled = extractor._compiled_regex_patterns

    assert extractor.extract_regex_entities(text) == first
    assert extractor._compiled_regex_patterns is compiled
    assert compiled


def test_keyword_positions_resolve_stemmed_matches(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)

    assert extractor.extract_keywords_with_positions("Ransomwares") == [
        {
            "keyword": "ransomware",
            "match": "Ransomwares",
            "start": 0,
            "end": 11,
            "category": "threat_intel",
        }
    ]


def test_config_loads_supported_formats(tmp_path: Path) -> None:
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('seed_keywords = ["tomlkw"]\nsimilarity_threshold = 0.25\n')
    assert InsightExtractor(config_path=toml_file).similarity_threshold == 0.25

    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("seed_keywords:\n  - yamlkw\nstem_mode: exact\n")
    assert "yamlkw" in InsightExtractor(config_path=yaml_file).thread_keywords

    json_file = tmp_path / "config.json"
    json_file.write_text(json.dumps({"seed_keywords": ["jsonkw"]}))
    assert "jsonkw" in InsightExtractor(config_path=json_file).thread_keywords


def test_bad_config_format_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.ini"
    config_file.write_text("seed_keywords=bad")

    with pytest.raises(ConfigLoadError):
        InsightExtractor._load_config(config_file)


def test_state_roundtrip_and_bad_state(tmp_path: Path) -> None:
    extractor = build_extractor(tmp_path)
    state_file = tmp_path / "state.json"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        extractor.save_state(state_file)
        restored = InsightExtractor(seed_keywords=[], output_dir=tmp_path)
        restored._model = FakeModel()
        assert restored.load_state(state_file) is True

    assert not [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]
    assert "ransomware" in restored.thread_keywords

    bad_state = tmp_path / "bad.json"
    bad_state.write_text("{not json")
    with pytest.raises(StateLoadError):
        restored.load_state(bad_state)


def test_empty_paths_return_empty_results(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=[], enable_dynamic_regex=False, output_dir=tmp_path)

    assert extractor.extract_dynamic_entities("anything") == {}
    assert extractor.extract_semantic_keywords("anything") == []
    assert extractor.extract_key_sentences("short") == []
    assert extractor.update_thread_keywords("plain text", auto_expand=False) == []
    assert extractor.load_state(tmp_path / "missing.json") is False


def test_keyword_expansion_uses_latest_input(tmp_path: Path) -> None:
    extractor = InsightExtractor(
        seed_keywords=["anchor"],
        similarity_threshold=0.0,
        dynamic_expansion_top_n=5,
        output_dir=tmp_path,
    )
    extractor._model = FakeModel()
    legacy_text = " ".join(f"legacyterm{i}" for i in range(250))
    for _ in range(3):
        assert extractor.update_thread_keywords(legacy_text, auto_expand=False) == []

    added = extractor.update_thread_keywords("quasar quasar photometry telescope observatory")

    assert any("quasar" in keyword for keyword in added)
    assert not any("legacyterm" in keyword for keyword in added)


def test_keyword_expansion_uses_one_fallback_for_a_new_domain(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["anchor"], output_dir=tmp_path)
    extractor._model = SelectiveModel()
    text = ("mycorrhizal " * 10) + "fungal ecology nutrient exchange watershed biodiversity"

    added = extractor.update_thread_keywords(text)

    assert added == ["mycorrhizal"]
    assert extractor.extract_dynamic_entities(text)["DYNAMIC_KEYWORD"] == ["mycorrhizal"]


def test_keyword_expansion_skips_fallback_when_a_known_candidate_qualifies(
    tmp_path: Path,
) -> None:
    extractor = InsightExtractor(seed_keywords=["anchor", "known"], output_dir=tmp_path)
    extractor._model = SelectiveModel()
    text = ("known " * 10) + "mycorrhizal fungal ecology nutrient exchange"

    assert extractor.update_thread_keywords(text) == []
    assert extractor.thread_keywords == ["anchor", "known"]


def test_model_load_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail_load(_model_name: str) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr("insight_extractor.extractor.SentenceTransformer", fail_load)
    extractor = InsightExtractor(seed_keywords=[], output_dir=tmp_path)

    with pytest.raises(ModelLoadError):
        _ = extractor.model


class TestAutoCategorization:
    def test_ai_safety_terms_map_to_ai_safety(self, tmp_path: Path) -> None:
        extractor = InsightExtractor(seed_keywords=["alignment", "jailbreak"], output_dir=tmp_path)
        assert extractor.keyword_categories["alignment"] is KeywordCategory.AI_SAFETY
        assert extractor.keyword_categories["jailbreak"] is KeywordCategory.AI_SAFETY

    def test_secops_terms_map_to_infosec(self, tmp_path: Path) -> None:
        extractor = InsightExtractor(
            seed_keywords=["incident response", "siem"], output_dir=tmp_path
        )
        assert extractor.keyword_categories["incident response"] is KeywordCategory.INFOSEC
        assert extractor.keyword_categories["siem"] is KeywordCategory.INFOSEC

    def test_no_category_is_child_safety(self, tmp_path: Path) -> None:
        assert not hasattr(KeywordCategory, "CHILD_SAFETY")
        assert "child_safety" not in [c.value for c in KeywordCategory]

    def test_substring_false_positives_stay_general(self, tmp_path: Path) -> None:
        # Regression: bare substring matching filed "legislation" under the safety
        # bucket (contains "sla") and "despair" under ai_infra (contains "ai").
        extractor = InsightExtractor(
            seed_keywords=["legislation", "despair", "homelessness"], output_dir=tmp_path
        )
        assert extractor.keyword_categories["legislation"] is KeywordCategory.GENERAL
        assert extractor.keyword_categories["despair"] is KeywordCategory.GENERAL
        assert extractor.keyword_categories["homelessness"] is KeywordCategory.GENERAL

    def test_whole_word_containment_still_matches(self, tmp_path: Path) -> None:
        extractor = InsightExtractor(seed_keywords=["confirmation bias"], output_dir=tmp_path)
        assert extractor.keyword_categories["confirmation bias"] is KeywordCategory.AI_SAFETY

    def test_unrelated_keyword_skips_boundary_regex_checks(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def unexpected_word_contains(_needle: str, _haystack: str) -> bool:
            pytest.fail("unrelated text should not require a boundary regex")

        monkeypatch.setattr(
            InsightExtractor,
            "_word_contains",
            staticmethod(unexpected_word_contains),
        )
        extractor = InsightExtractor(seed_keywords=["zzqvwx"], output_dir=tmp_path)

        assert extractor.keyword_categories["zzqvwx"] is KeywordCategory.GENERAL

    def test_word_contains_reuses_compiled_pattern(self) -> None:
        _compile_word_pattern.cache_clear()
        assert InsightExtractor._word_contains("war", "war room")
        assert not InsightExtractor._word_contains("war", "malware")
        assert _compile_word_pattern.cache_info().hits == 1

    def test_load_state_remaps_legacy_child_safety(self, tmp_path: Path) -> None:
        state_file = tmp_path / "legacy_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "thread_keywords": ["safety"],
                    "keyword_freq": {"safety": 3},
                    "keyword_categories": {"safety": "child_safety"},
                }
            ),
            encoding="utf-8",
        )
        extractor = InsightExtractor(seed_keywords=["safety"], output_dir=tmp_path)
        extractor._model = FakeModel()
        assert extractor.load_state(state_file) is True
        assert extractor.keyword_categories["safety"] is KeywordCategory.AI_SAFETY
