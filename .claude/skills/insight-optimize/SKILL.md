---
name: insight-optimize
description: >-
  Methodically scan the Insight_Extractor main branch for code quality, CI hygiene,
  security posture, dependency-risk (pins/CVEs/accelerate footguns), and maintainability
  optimization opportunities, then open one focused, reviewable draft PR per finding.
  Use this whenever the user asks to "optimize", "sweep", "audit", "polish", "harden",
  or "find improvements in" the repo, asks for an optimization pass, or invokes
  /insight-optimize — even if they only name one dimension (e.g. "check our deps" or
  "any ruff debt?"), because findings in one dimension usually surface neighbors in
  others. Do NOT use for adding new entity patterns (use add-entity-pattern) or for a
  plain pre-push check (use preflight).
---

# Insight-Optimize — full optimization sweep of Insight_Extractor

Run a methodical, architecture-aware scan of `main` and open **one draft PR per
distinct finding**. This skill encodes what "an optimization" means in *this* repo —
the operative test for every candidate change is:

> Does it polish the portfolio signal, fix a real defect, strengthen an architectural
> invariant (especially lazy ML loading + ML-free core modules), or reduce CI churn /
> dependency risk?

If the answer is no — it's a new capability, new public API surface, or an enum/seed/
regex addition — stop and get explicit user justification first (CLAUDE.md §6).

## The codebase you are scanning (ground truth, verified against source)

Module map with actual sizes and load-bearing symbols:

| Module | LOC | Key symbols | ML imports |
|---|---|---|---|
| `config.py` | 44 | `StemMode`, `KeywordCategory`, `PatternLabel` — all `@final` `StrEnum` | **Zero — keep it that way** |
| `constants.py` | 415 | `THREAD_SEEDS` (69 keywords), `REGEX_PATTERNS` (15 patterns keyed by `PatternLabel`) | **Zero** |
| `models.py` | 54 | Pydantic v2: `MatchInfo`, `KeywordStats`, `SemanticHit`, `SentenceScore`, `ExtractResult` (with `validate_timestamp` field validator — timestamps are `str`, never `datetime`) | **Zero** |
| `exceptions.py` | 25 | `InsightExtractorError` hierarchy; subclasses mix in stdlib bases (`ConfigLoadError` + `ValueError`, `ModelLoadError` + `RuntimeError`) | **Zero** |
| `utils.py` | 42 | `format_timestamp`, `compute_text_hash`, filename helpers | **Zero** |
| `stemmer.py` | 633 | `ChunkedKeywordPattern` (`.search`/`.finditer` over pattern chunks), `DynamicKeywordStemmer` (`generate_pattern`, `compile_keywords`, `compile_keywords_incremental`, `find_matches` → `list[MatchInfo]`), `KeywordPatternRegistry` (`regenerate_dynamic_patterns`, `extract_all`) | Zero |
| `tokenizer.py` | 72 | `SentenceTokenizer` — `AutoTokenizer` loads lazily on `.tokenizer` property; `count_tokens`, `chunk_text`, `tokenize_sentences` | Lazy (property) |
| `extractor.py` | 1043 | `InsightExtractor` — module-level `sentence_transformers` import, model lazy on `.model` property | Yes (module-level import) |
| `__main__.py` | 71 | CLI `python -m insight_extractor [file.txt]` — writes state + markdown to **CWD** | Via extractor |

Constructor defaults that are **public contract** (changing any needs user sign-off):
`similarity_threshold=0.38`, `top_k=10`, `dynamic_expansion_top_n=15`,
`stem_mode=StemMode.STEM`, `enable_dynamic_regex=True`,
`model_name="sentence-transformers/all-MiniLM-L6-v2"`, `output_dir="."`.

`__init__.py` (`__version__ = "2.0.0"`) does top-level imports of the light modules and
routes the four heavy classes (`InsightExtractor`, `DynamicKeywordStemmer`,
`KeywordPatternRegistry`, `SentenceTokenizer`) through a `__getattr__` `_IMPORT_MAP`.
The CI smoke test imports `insight_extractor.constants` on a runtime-only install —
any heavy import creeping into a light module breaks it.

## Step 1 — Scan `main` across five dimensions

Fetch and check out latest `origin/main` first. Then scan, reading actual source (never
the README alone — this repo once shipped a phantom-API test suite, commit `40e81fe`):

1. **Code quality** — ruff families E/F/I/N/W/UP/B/C4/SIM at line-length **100**;
   `mypy --strict`; Pydantic v2 models for every structured return (never bare dicts);
   `pathlib.Path` + explicit `encoding="utf-8"` on every file op (owner develops on
   Windows cmd.exe where default encoding is not UTF-8 — a missing `encoding=` is a
   real bug); `from __future__ import annotations` in every module; keyword-only
   boolean/tuning params after `*`; lazy `%s` logging, never f-strings in log calls.
2. **CI hygiene** — the four gates (ruff check, ruff format --check, mypy strict,
   pytest unit on py3.12 **and** 3.13); integration tests stay gated behind
   `workflow_dispatch` / `[run-integration]`; unit tests never touch network or model
   (stub via `extractor._model = FakeModel()` / `._tokenizer = FakeTokenizer()`
   injection, per `tests/unit/test_extractor.py`); no run artifacts in the tree
   (`insights_extracted.md`, `insight_extractor_state.json`, `junit*.xml`,
   `coverage.xml`, `*.log`, `smoke_results.json`).
3. **Security posture** — gitleaks-safe (no realistic-looking secrets even in fixtures;
   imitate the shape of the existing sample BTC wallet / hashes / emails); pins
   consistent across `requirements.txt` / `constraints.txt` / `pyproject.toml`; input
   validation on config loading (`.toml`/`.yaml`/`.yml`/`.json`, dict-at-top-level).
4. **Dependency-risk** — the transformers/sentence-transformers/accelerate triangle:
   `transformers>=4.53.0,<5.0.0` (floor clears 18 CVEs per `docs/SECURITY_AUDIT.md`);
   `accelerate` is load-bearing despite zero imports (sentence-transformers needs it —
   `ModelLoadError: name 'init_empty_weights' is not defined` without it); the known
   broken pin `transformers==4.53.0` + `accelerate==0.34.2` →
   `ImportError: cannot import name 'TorchTensorParallelPlugin'` (fixing the pin is
   ask-first); `pip-audit` surface with reachability verdicts in
   `docs/SECURITY_AUDIT.md`.
5. **Maintainability** — the lazy-loading invariant above; the duplicated sentence-split
   regex `r"(?<=[.!?])\s+"` in `tokenizer.tokenize_sentences` **and**
   `extractor.extract_key_sentences` (which also drops sentences ≤30 chars — change
   both or deliberately consolidate); the four-step keyword-mutation sequence
   (`stemmer.set_keywords` → `registry.regenerate_dynamic_patterns` →
   `_recompute_keyword_embeddings` → `_auto_categorize_keywords`, canonical in
   `update_thread_keywords` / `load_state`); Windows+Linux dual-platform; state
   persistence semantics (`load_state`/`save_state` round-trip
   `similarity_threshold`); `PORT_NUMBER` being the only capture-group pattern
   (findall returns `"4444"`, not `"port 4444"`).

Known non-findings — do not report these as problems:
- `seed_keywords=[]` loading all 69 `THREAD_SEEDS` is documented behavior (§4.2).
- `StrEnum` keys comparing equal to plain strings in result dicts is by design (§4.14).
- The constructor silently swallowing `ConfigLoadError` is by design (§4.12).
- The SARIF upload failure on this private repo is expected and `continue-on-error`.

## Step 2 — One draft PR per finding

For each distinct opportunity:

1. Cut a short-lived branch `claude/<topic>` off latest `main`.
2. Make the **smallest reviewable change** — one concern only. No drive-by
   reformatting, no opportunistic refactors, no bundling.
3. Verify: run the four gates locally, or invoke the `preflight` skill. For anything
   touching `extractor.py`/`stemmer.py`/`tokenizer.py`/`constants.py`/`models.py`,
   also use `verify-no-model` to prove end-to-end behavior without downloading BERT.
   For dependency changes, use `deps-security-refresh` and update
   `docs/SECURITY_AUDIT.md`.
4. Commit in house style: conventional prefix + imperative subject ≤72 chars; body
   bullets each carry a **root cause** (see commits `40e81fe`, `c3fef9b`, `9e5f8ff`).
5. Open a **draft** PR into `main`. Body must include:
   - What changed + root cause
   - Why it improves the signal / fixes the defect / strengthens the invariant
   - Risk + verification steps, **explicitly reporting any skipped gates and why**
     (e.g. "integration tests skipped — no model download in this environment")

## Hard limits

- Never push to `main` directly; never force-push shared branches.
- Never loosen a gate (`[tool.ruff]`, `[tool.mypy]`, pytest config, `ci.yml`,
  `gitleaks.yml`) to get green. Fix the code or stop and ask.
- Preserve, in every PR: lazy loading (no top-level heavy imports in the five
  ML-free modules), Pydantic v2 output schemas, Windows cmd.exe + Linux CI
  compatibility, and the checked-in fixtures (`sample_input.txt`,
  `sample_extracted_insights.md`) byte-for-byte.
- Behavior changes to public defaults (`similarity_threshold`, `stem_mode`, `top_k`,
  suffix tuple, `THREAD_SEEDS`, `REGEX_PATTERNS` semantics) or output file formats
  (`insights_extracted.md` structure, state JSON schema) are ask-first, with 2–3
  concrete options and a recommendation.
- If a gate fails for reasons unrelated to your change: at most two focused fix
  attempts, then deliver what's verifiable and report the literal error. A truthful
  partial result beats a green lie.
