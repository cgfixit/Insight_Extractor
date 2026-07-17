---
description: Methodically scan the Insight_Extractor main branch for code quality, CI hygiene, security posture, dependency-risk (pins/CVEs/accelerate footguns), and maintainability optimization opportunities, then open focused, reviewable pull requests for each.
---

Run a full optimization sweep of Insight_Extractor main and open one draft PR per finding. $ARGUMENTS

## Steps

1. Scan `main` for optimization opportunities across:
   - **Code quality** (ruff rules E/F/I/N/W/UP/B/C4/SIM at line-length 100, mypy --strict, Pydantic v2 models — never bare dicts, small focused functions, pathlib + explicit `encoding="utf-8"` on every file op)
   - **CI hygiene** (four gates: ruff check/format, mypy strict, pytest unit on py3.12+3.13; integration tests gated behind `[run-integration]`; unit tests stub the model via `_model`/`_tokenizer` injection, never download)
   - **Security posture** (gitleaks, pin consistency across requirements.txt/constraints.txt/pyproject.toml, no secrets, config input validation)
   - **Dependency-risk** (transformers `>=4.53.0,<5.0.0` / sentence-transformers / accelerate triangle, known `ModelLoadError: init_empty_weights` and `TorchTensorParallelPlugin` ImportError footguns, CVE surface via pip-audit + `docs/SECURITY_AUDIT.md`)
   - **Maintainability** (lazy ML loading invariant, duplicated sentence-split regex in tokenizer.py + extractor.py, four-step keyword-mutation sync sequence, Windows+Linux dual-platform, state persistence, ChunkedKeywordPattern)

   Read with the Insight_Extractor architecture in mind:
   - **Core invariant**: lazy ML loading — `config.py` / `constants.py` / `models.py` / `exceptions.py` / `utils.py` / `stemmer.py` must remain importable with **zero** torch/transformers/sentence-transformers deps (enforced by `__init__.py` `__getattr__` `_IMPORT_MAP` and the CI smoke test that imports `insight_extractor.constants` on a runtime-only install).
   - Module map: `stemmer.py` (DynamicKeywordStemmer, KeywordPatternRegistry, ChunkedKeywordPattern; `find_matches` returns `list[MatchInfo]`), `tokenizer.py` (lazy AutoTokenizer on `.tokenizer` property), `extractor.py` (orchestrator, lazy model on `.model` property, public defaults `similarity_threshold=0.38` / `top_k=10` / `dynamic_expansion_top_n=15` / `stem_mode=StemMode.STEM`), `__main__.py` (CLI, writes to CWD), Pydantic models in `models.py` (MatchInfo, KeywordStats, SemanticHit, SentenceScore, ExtractResult — timestamps are `str`, never `datetime`).
   - Output contracts: always Markdown report + `insight_extractor_state.json`; regex pipeline must work without BERT.

2. For each distinct opportunity, cut a short-lived `claude/<topic>` branch off latest `main`, make the **smallest reviewable change** (one concern only), and open a **draft** PR titled with conventional-commit prefix (imperative subject ≤72 chars). Body must include:
   - What changed + root cause
   - Why it improves the signal/defect/invariant
   - Risk / verification steps (explicitly report skipped gates + why)

3. Never bundle unrelated concerns into one PR — one concern per PR, per repo convention (minimal diffs, no drive-by reformatting).

Follow `.claude/skills/insight-optimize/SKILL.md` for the full process, ground-truth module map, known non-findings, PR checklist, and verification reporting style.

## Notes

- Controlled-change discipline applies (`CLAUDE.md` §1–4) — the operative test is: "does this polish the portfolio signal, fix a real defect, strengthen an architectural invariant (especially lazy ML loading + ML-free core modules), or reduce CI churn / dependency risk?" New capabilities, public API surface, or enum/seed/regex additions need explicit user justification first.
- Never push directly to `main`; never force-push without sign-off.
- Before any PR touching core files: run the four CI gates locally (`ruff check src/ tests/`, `ruff format --check src/ tests/`, `mypy src/insight_extractor`, `pytest tests/unit/ -v --tb=short`) **or** invoke the `preflight` skill. After changes to `extractor.py`/`stemmer.py`/`tokenizer.py`/`constants.py`/`models.py`, use `verify-no-model` to prove behavior without downloading BERT. For dependency changes, use `deps-security-refresh` + update `docs/SECURITY_AUDIT.md`.
- All optimizations must preserve:
  - Lazy loading (no top-level heavy imports in ML-free modules)
  - Pydantic v2 output schemas (never bare dicts)
  - Windows cmd.exe + Linux CI compatibility
  - Existing fixture behavior (`src/sample_input.txt`, `src/sample_extracted_insights.md`)
