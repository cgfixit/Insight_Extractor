"""Fast unit coverage for InsightExtractor without downloading model weights."""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import insight_extractor.__main__ as cli
from insight_extractor.config import KeywordCategory, StemMode
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


def test_regex_extracts_urls_uuids_and_ai_domains(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    task = "https://www.perplexity.ai/computer/tasks/9a2f15b7-2c91-4cbb-b8a7-52def899cfce"
    text = (
        f"| 1 | Thread | {task}\n"
        f"| 2 | Repeat | {task}\n"
        "Pattern: https://www.perplexity.ai/computer/tasks/{uuid} and [docs](https://x.com/a?b=1).\n"
        "Payload at hxxp://evil[.]example/drop.bin, then hxxps[:]//bad[.]ru/x?a=1)\n"
        "GUID 0ECC0E47-2574-4541-BCEB-D22677E84E32.\n"
        "Not URLs: mailto:a@b.co, http:// nothing.\n"
        "Not domains: cloud-infra.md graph.py Safari.app\n"
        "Not UUIDs: 9a2f15b7-2c91-4cbb-b8a7 and 9a2f15b7-2c91-4cbb-b8a7-52def899cfcee"
    )

    result = extractor.extract_regex_entities(text)

    assert result["URL"] == [
        task,
        "https://www.perplexity.ai/computer/tasks/{uuid}",
        "https://x.com/a?b=1",
        "hxxp://evil[.]example/drop.bin",
        "hxxps[:]//bad[.]ru/x?a=1",
    ]
    assert result["UUID"] == [
        "9a2f15b7-2c91-4cbb-b8a7-52def899cfce",
        "0ECC0E47-2574-4541-BCEB-D22677E84E32",
    ]
    # "b.co" comes from the email address, as DOMAIN already matched before this change.
    assert result["DOMAIN"] == ["www.perplexity.ai", "x.com", "b.co"]


def test_domain_never_reports_a_prefix_of_a_longer_host(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    text = (
        "Phish at paypal.com.secure-login.ru and www.bbc.co.uk; docs on "
        "discuss.ai.google.dev; real hosts opentools.ai, x.paypal.com, and example.com."
    )

    assert extractor.extract_regex_entities(text)["DOMAIN"] == [
        "opentools.ai",
        "x.paypal.com",
        "example.com",
    ]


def test_domain_and_email_scale_linearly_on_dotted_runs(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    dotted = "a." * 20000 + " " + "-".join(f"{i % 256:02X}" for i in range(10000))

    started = time.perf_counter()
    result = extractor.extract_regex_entities(dotted)

    # Generous budget: the bounded patterns take ~0.6 s here, the quadratic ones ~30 s.
    assert time.perf_counter() - started < 3.0
    assert "DOMAIN" not in result and "EMAIL" not in result


def test_domain_and_email_keep_unicode_word_boundaries(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    # Cyrillic homoglyphs, an IDN label, an SRV name, and non-ASCII before an email.
    text = (
        "micr\u043esoft.com p\u0430ypal.com b\u00fccher.example.com "
        "_ldap._tcp.dc.corp.net foo_bar.com -evil.com \u00e9user@corp.com .admin@corp.com"
    )

    result = extractor.extract_regex_entities(text)

    assert result["DOMAIN"] == ["example.com", "dc.corp.net", "evil.com", "corp.com"]
    assert result["EMAIL"] == ["admin@corp.com"]


def test_static_pattern_regressions_under_ignorecase(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    text = (
        "Wallets 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf8C, 1OIlOIlOIlOIlOIlOIlOIlOIlOIlOIl, and "
        "3b4c5d6e7f8a9b1c1d2e3f4a5b6c7d8e. Demanded $1.5 million, later $2.5B, paid "
        "$100 bitcoin and $500, then $1,200,000. Affected IP 10.0.0.1 Port: 4444, "
        "port=8080, ports 80. Stole 8 terabytes and 500 gigabytes (8 TB)."
    )

    result = extractor.extract_regex_entities(text)
    combined = extractor.pattern_registry.extract_all(text)

    assert result["BTC_WALLET"] == ["1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf8C"]
    assert result["RANSOM_AMOUNT"] == ["$1.5 million", "$2.5B", "$100", "$500", "$1,200,000"]
    assert combined["RANSOM_AMOUNT"] == result["RANSOM_AMOUNT"]
    assert result["PORT_NUMBER"] == ["4444", "8080", "80"]
    assert result["TB_GB_DATA"] == ["8 terabytes", "500 gigabytes", "8 TB"]


def test_regex_entities_reuse_compiled_patterns(tmp_path: Path) -> None:
    extractor = InsightExtractor(seed_keywords=["ransomware"], output_dir=tmp_path)
    text = "Ransomware references CVE-2026-9999."

    first = extractor.extract_regex_entities(text)
    compiled = extractor._compiled_regex_patterns

    assert extractor.extract_regex_entities(text) == first
    assert extractor._compiled_regex_patterns is compiled
    assert compiled


@pytest.mark.parametrize("enable_dynamic", [False, True])
def test_static_case_policy_and_dynamic_result_labels(tmp_path: Path, enable_dynamic: bool) -> None:
    extractor = InsightExtractor(
        seed_keywords=["ransomware"],
        enable_dynamic_regex=enable_dynamic,
        output_dir=tmp_path,
    )
    text = "Ransomwares CVE-2026-1234 cve-2026-5678 PORT 4444 Report.EXE Example.COM"

    static = extractor.extract_regex_entities(text)
    combined = extractor.pattern_registry.extract_all(text)
    dynamic = extractor.extract_dynamic_entities(text)

    assert static["CVE_ID"] == ["CVE-2026-1234", "cve-2026-5678"]
    assert static["PORT_NUMBER"] == ["4444"]
    assert static["FILE_EXTENSION"] == [".EXE"]
    assert static["DOMAIN"] == ["Example.COM"]
    assert {
        label: matches for label, matches in combined.items() if label != "DYNAMIC_KEYWORD"
    } == static
    assert dynamic == ({"DYNAMIC_KEYWORD": ["Ransomwares"]} if enable_dynamic else {})
    assert extractor.extract_dynamic_entities("cve-2026-5678") == {}
    assert extractor._model is None
    assert extractor._tokenizer is None


def test_full_result_separates_static_and_dynamic_matches(tmp_path: Path) -> None:
    extractor = build_extractor(tmp_path)

    result = extractor.extract("Ransomware exploited cve-2026-5678.", update_keywords=False)

    assert result.regex_entities["CVE_ID"] == ["cve-2026-5678"]
    assert set(result.dynamic_keyword_matches) == {"DYNAMIC_KEYWORD"}
    assert "Ransomware" in result.dynamic_keyword_matches["DYNAMIC_KEYWORD"]


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
    yaml_extractor = InsightExtractor(config_path=yaml_file)
    assert "yamlkw" in yaml_extractor.thread_keywords
    assert yaml_extractor.keyword_freq["yamlkw"] == 1

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


def test_load_state_restores_runtime_settings_lazily(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "thread_keywords": ["ransomware"],
                "keyword_freq": {"ransomware": 2},
                "keyword_categories": {"ransomware": "threat_intel"},
                "stem_mode": "exact",
                "similarity_threshold": 0.12,
                "model_name": "sentence-transformers/alternate-mini",
            }
        ),
        encoding="utf-8",
    )

    def unexpected_model_load(_model_name: str) -> object:
        raise AssertionError("load_state should not load the model eagerly")

    monkeypatch.setattr("insight_extractor.extractor.SentenceTransformer", unexpected_model_load)
    restored = InsightExtractor(
        model_name="sentence-transformers/original-mini",
        seed_keywords=[],
        output_dir=tmp_path,
    )
    restored._model = FakeModel()
    restored._tokenizer = FakeTokenizer()

    assert restored.load_state(state_file) is True
    assert restored.model_name == "sentence-transformers/alternate-mini"
    assert restored.stem_mode is StemMode.EXACT
    assert restored.stemmer.stem_mode is StemMode.EXACT
    assert restored._model is None
    assert restored._tokenizer is None
    assert restored._keyword_embeddings is None

    restored._model = FakeModel()
    restored._tokenizer = FakeTokenizer()
    assert restored.extract_dynamic_entities("ransomware")["DYNAMIC_KEYWORD"] == ["ransomware"]
    assert restored.extract_semantic_keywords("ransomware incident response details")


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        [],
        42,
        "state",
        True,
        {"thread_keywords": "replacement"},
        {"thread_keywords": {"replacement": 1}},
        {"thread_keywords": [42]},
        {"thread_keywords": [None]},
        {"keyword_freq": []},
        {"keyword_freq": None},
        {"keyword_freq": {"replacement": "2"}},
        {"keyword_freq": {"replacement": 2.5}},
        {"keyword_freq": {"replacement": True}},
        {"keyword_freq": {"replacement": -1}},
        {"keyword_categories": []},
        {"keyword_categories": None},
        {"keyword_categories": {"replacement": "invalid"}},
        {"keyword_categories": {"replacement": []}},
        {"stem_mode": "invalid"},
        {"stem_mode": None},
        {"stem_mode": []},
        {"similarity_threshold": "invalid"},
        {"similarity_threshold": "0.2"},
        {"similarity_threshold": None},
        {"similarity_threshold": True},
        {"similarity_threshold": []},
        {"similarity_threshold": float("nan")},
        {"similarity_threshold": float("inf")},
        {"similarity_threshold": -float("inf")},
        {"model_name": 42},
        {"model_name": None},
        {"model_name": ""},
        {"model_name": []},
        {"stem_mode": "regex", "thread_keywords": ["["]},
        {"stem_mode": "regex", "thread_keywords": ["a{999999999999999999999999999}"]},
        b"{not json",
        b"\xff",
    ],
)
def test_load_state_failure_preserves_live_state(tmp_path: Path, invalid: object) -> None:
    extractor = build_extractor(tmp_path)
    extractor._keyword_embeddings = np.array([[1.0, 0.0]] * len(extractor.thread_keywords))
    extractor._keyword_embeddings_dirty = False
    original_matches = extractor.extract_dynamic_entities("Ransomware exploit")
    extractor.extract_regex_entities("CVE-2026-1234")
    original_attributes = extractor.__dict__.copy()
    original_keywords = list(extractor.thread_keywords)
    original_frequencies = extractor.keyword_freq.copy()
    original_categories = extractor.keyword_categories.copy()
    original_embeddings = extractor._keyword_embeddings.copy()
    original_patterns = extractor._compiled_regex_patterns.copy()
    original_stem_keywords = list(extractor.stemmer._keywords)
    original_dynamic_patterns = extractor.pattern_registry.all_patterns
    state_file = tmp_path / "invalid.json"
    if isinstance(invalid, bytes):
        document = invalid
    else:
        raw = (
            {
                "thread_keywords": ["replacement"],
                "keyword_freq": {"replacement": 7},
                "keyword_categories": {"replacement": "general"},
                "stem_mode": "exact",
                "similarity_threshold": 0.12,
                "model_name": "different/model",
                **invalid,
            }
            if isinstance(invalid, dict)
            else invalid
        )
        document = json.dumps(raw).encode("utf-8")
    state_file.write_bytes(document)

    with pytest.raises(StateLoadError, match="Failed to load state"):
        extractor.load_state(state_file)

    assert extractor.__dict__.keys() == original_attributes.keys()
    assert all(extractor.__dict__[key] is value for key, value in original_attributes.items())
    assert extractor.thread_keywords == original_keywords
    assert extractor.keyword_freq == original_frequencies
    assert extractor.keyword_categories == original_categories
    np.testing.assert_array_equal(extractor._keyword_embeddings, original_embeddings)
    assert extractor._compiled_regex_patterns == original_patterns
    assert extractor.stemmer._keywords == original_stem_keywords
    assert extractor.pattern_registry.all_patterns == original_dynamic_patterns
    assert extractor.extract_dynamic_entities("Ransomware exploit") == original_matches
    assert state_file.read_bytes() == document


def test_load_state_read_error_is_controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    extractor = build_extractor(tmp_path)
    original_attributes = extractor.__dict__.copy()

    def unreadable(*_args: Any, **_kwargs: Any) -> str:
        raise PermissionError("synthetic read failure")

    monkeypatch.setattr(Path, "read_text", unreadable)
    with pytest.raises(StateLoadError, match="synthetic read failure"):
        extractor.load_state(state_file)
    assert all(extractor.__dict__[key] is value for key, value in original_attributes.items())


def test_load_state_preserves_same_model_and_empty_bank_lazily(tmp_path: Path) -> None:
    extractor = build_extractor(tmp_path)
    model, tokenizer = extractor._model, extractor._tokenizer
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "thread_keywords": ["détection"],
                "keyword_freq": {"détection": 2},
                "keyword_categories": {"détection": "child_safety"},
            }
        ),
        encoding="utf-8",
    )

    assert extractor.load_state(state_file)
    assert extractor.thread_keywords == ["détection"]
    assert extractor.keyword_categories == {"détection": KeywordCategory.AI_SAFETY}
    assert extractor._model is model
    assert extractor._tokenizer is tokenizer
    assert extractor._keyword_embeddings is None
    assert extractor._keyword_embeddings_dirty is True
    assert extractor.extract_dynamic_entities("détections")["DYNAMIC_KEYWORD"] == ["détections"]

    state_file.write_text("{}", encoding="utf-8")
    assert extractor.load_state(state_file)
    assert extractor.thread_keywords == []
    assert extractor.keyword_freq == {}
    assert extractor.keyword_categories == {}
    assert extractor._keyword_embeddings is None
    assert extractor._keyword_embeddings_dirty is False
    assert extractor._model is model
    assert extractor._tokenizer is tokenizer
    assert extractor.extract_dynamic_entities("détection") == {}


def test_cli_reports_invalid_state_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "insight_extractor_state.json"
    document = '{"thread_keywords":["replacement"],"keyword_categories":{"replacement":"invalid"}}'
    state_file.write_text(document, encoding="utf-8")

    assert cli.main([]) == 1
    captured = capsys.readouterr()
    assert "error: Failed to load state" in captured.err
    assert "Traceback" not in captured.err
    assert not captured.out
    assert state_file.read_text(encoding="utf-8") == document
    assert not (tmp_path / "insights_extracted.md").exists()


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


def test_keyword_expansion_preserves_tfidf_tie_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("insight_extractor.extractor.THREAD_SEEDS", [])
    extractor = InsightExtractor(seed_keywords=[], dynamic_expansion_top_n=1, output_dir=tmp_path)

    assert extractor.update_thread_keywords("theta zeta") == ["zeta"]


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


def test_cli_reports_missing_input_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    missing = tmp_path / "missing.txt"
    monkeypatch.chdir(tmp_path)

    assert cli.main([str(missing)]) == 1
    assert "failed to read input file" in capsys.readouterr().err


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
