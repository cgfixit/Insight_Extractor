# Codex setup review

Reviewed 2026-09-06 against origin/main at
`8097406` (before this documentation-only setup change).

## Architecture and scope

The packaged application is `src/insight_extractor`, installed with hatchling and
exposed through `insight-extract` and `python -m insight_extractor`.
The review covered package modules, unit and integration tests, README, SPEC,
dependency manifests, CI/security workflows, and every `.codex` file.
`docs/insight_extractor.py` is a separate legacy script with working-directory
inputs; its Porter-like logic is not the packaged stemmer implementation.

- `__init__` lazily exposes classes; lightweight models/config/constants/utilities
  remain usable without importing torch. `extractor.py` itself imports ML libraries.
- The stemmer generates regexes, compiles growing keyword banks incrementally,
  resolves original keywords, and maintains match spans. Registry regeneration is
  explicit; it is not an observer of arbitrary stemmer mutations.
- `extract()` expands keywords with TF-IDF, prepares embeddings, then combines
  static/dynamic regex, semantic hits, sentence scores, and keyword statistics.
- Reports escape Markdown and HTML. State loading restores settings and invalidates
  embeddings lazily; changing the saved model name also clears model/tokenizer objects.

## Setup corrections

- Added four `insight-` skill entrypoints under `.agents/skills`, linking to existing
  `.codex/skills` workflows. This preserves maintained references and avoids collisions
  with generic personal skills. Repository discovery is documented in the
  [official Codex skills guide](https://developers.openai.com/codex/skills/).
- Gave the extended optimizer a distinct name and closed its unfinished code fence.
- Corrected offline verification around state restoration and clarified that the
  lightweight regex check does not reproduce the production CLI smoke job.
- Documented optional integration trigger limitations and stale test fixtures.
- Kept constraints on the editable development install in Codex onboarding.

The root AGENTS entrypoint already delegates to `.codex/AGENTS.md`. No project
config file or additional plugin installation is needed for these workflows.
Existing Ponytail JSON is reference metadata, not an installed plugin declaration.
Open a new task if its skill catalog does not show the new entrypoints.

## Follow-up findings

1. **Tokenizer termination and coverage:** `SentenceTokenizer.chunk_text` advances
   by `max_tokens - overlap` without validating either argument. A long input with
   equal budget/overlap never advances; `tokenize_sentences` fixes overlap at 50,
   so small caller budgets also need review. Existing tokenizer tests cover normal
   chunking but do not cover invalid budget/overlap combinations.
   Add a bounded fake-tokenizer regression, then define validation and test normal,
   zero, negative, and oversized overlap without downloading a model.
2. **Integration fixtures have drifted:** both integration files patch
   `insight_extractor.tokenizer.AutoTokenizer`, which is only imported under
   `TYPE_CHECKING` at module scope. `test_e2e.py` additionally uses unsupported
   constructor flags and obsolete result fields. Some extraction occurs after
   patch contexts exit. Repair fixtures against current signatures, use correctly
   sized deterministic vectors, and distinguish offline orchestration from any
   deliberate real-model test. A passing required CI gate does not certify this suite.
3. **State validation deserves a separate fix:** syntactically valid JSON with a
   non-object root or invalid enum values can escape `StateLoadError`; field-by-field
   assignment can leave partially changed state. Validate before mutation and test
   failure atomicity while retaining lazy loading and the legacy category mapping.
4. **Documentation debt:** README advertises Porter/lemmatization and character-error
   fuzzy matching, while the packaged stemmer uses suffix expansion and substring
   regex matching. It also references a missing LICENSE. Packaging URLs use a hyphen
   instead of the actual repository underscore. Historical CLAUDE/SPEC details and
   security-audit conclusions require rechecking against current source/advisories.
   This review is not a fresh dependency vulnerability audit.

## Suggested next skills

- `insight-tokenizer-check`: reproduce chunk-budget/overlap failures with an injected
  tokenizer, enforce termination and token preservation, and verify lazy imports.
- `insight-state-contract`: validate state round trips, malformed schema handling,
  failure atomicity, legacy categories, relative-path behavior, and model invalidation.

These are proposals for separate changes, not newly implemented runtime behavior.

## Local validation

The editable package was installed in `.venv` with system packages disabled and
`-c constraints.txt`. The available interpreter is Windows Python 3.12.0rc3;
this is not evidence of a clean stable-Python 3.13 installation or real-model inference.

- `pip check`: no broken requirements.
- Ruff lint and format: passed.
- Strict mypy: passed, 10 source files.
- Offline unit tests: 118 passed.
- Optional E2E diagnostic (`pytest tests/integration/test_e2e.py -x -q --tb=short`):
  fails at fixture setup with `AttributeError: module 'insight_extractor.tokenizer'
  has no attribute 'AutoTokenizer'`; stopped after the first failure. No real-model
  download was attempted. The optional suite remains a separate repair task.
- Production CI smoke Python body, extracted from `ci.yml` and run in an ignored
  scratch directory: passed (console, escaped Markdown, keyword expansion, state).
- Four new skill entrypoints: metadata validation passed; every workflow link resolves.
- Lightweight root import resolves to this checkout and does not import torch.
- `git diff --check`: passed.

The local Codex CLI is 0.153.4. Its sandbox diagnostic uses a separate sandbox home;
missing credentials and `TERM=dumb` there are not evidence of broken desktop auth.
The GitHub connector successfully resolved this repository and its access permissions.
