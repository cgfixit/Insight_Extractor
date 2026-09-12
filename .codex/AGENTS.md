# AGENTS.md

Guidance for AI coding agents working in `Insight_Extractor`.

Read this file before edits. Use the source code as the behavioral authority, then
`docs/SPEC.md`, then `README.md`. The detailed operating manual is `CLAUDE.md`; the
security audit is `docs/SECURITY_AUDIT.md`.

## Project

`Insight_Extractor` is a Python 3.12+ src-layout library for threat-intelligence, OSINT, and security text. It combines:

- static regex extraction;
- dynamic keyword stemming and pattern compilation;
- optional BERT semantic scoring through `sentence-transformers`;
- Pydantic v2 result models;
- Markdown reports and JSON state persistence.

Important paths:

- `src/insight_extractor/` — package code;
- `tests/unit/` — model-free unit tests;
- `tests/integration/` — optional orchestration tests with injected fake ML boundaries;
- `.github/workflows/ci.yml` — required lint, type, unit, and smoke gates;
- `requirements.txt`, `constraints.txt`, `pyproject.toml` — dependency declarations and pins;
- `.codex/` — Codex instructions and workflow references;
- `.agents/skills/` — discoverable, repository-specific skill entrypoints;
- `.claude/skills/` — existing detailed implementation checklists.

## Setup and validation

Use a Python 3.12+ virtual environment when possible:

```powershell
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install -e ".[dev]" -c constraints.txt
```

Required gates:

```powershell
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
python -m mypy src/insight_extractor
python -m pytest tests/unit/ -v --tb=short
```

The CI smoke path uses fake BERT boundaries and production CLI orchestration.
Optional integration CI runs on workflow dispatch or a qualifying push head commit
containing `[run-integration]`; a PR commit message alone does not enable it.
Those tests inject fake model/tokenizer objects and exercise the live public API
without downloading BERT weights.

Historical manual corrections: the live constraints already include the accelerate compatibility fix; `load_state()` invalidates embeddings lazily rather than recomputing them. Check current source and manifests before following historical sequences in `CLAUDE.md`.

## Non-negotiable invariants

- Keep model and tokenizer loading lazy. `config.py`, `constants.py`, `models.py`, `exceptions.py`, and `utils.py` must remain importable without heavy ML dependencies.
- Unit tests must not access the network or download HuggingFace models. Inject fake model/tokenizer objects when testing semantic orchestration.
- If changing a regex entity, keep `PatternLabel`, `REGEX_PATTERNS`, tests, and the README table synchronized.
- Dependency changes update `requirements.txt`, `constraints.txt`, and `pyproject.toml` together; `accelerate` is load-bearing.
- Preserve output files and state schema: `insights_extracted.md` and `insight_extractor_state.json`.
- Do not commit generated reports, state files, JUnit/coverage artifacts, logs, model caches, secrets, or tokens.
- Use explicit UTF-8 file I/O and pathlib for new Python code.
- Do not weaken Ruff, mypy, pytest, Gitleaks, or workflow gates to make CI green.

## Git and PR workflow

- Branch from `main`; target `main`; never force-push shared branches.
- Keep docs/skill changes separate from runtime changes.
- Stage named files only.
- Run the narrowest applicable gates and report skipped checks with reasons.
- Use conventional commit prefixes (`docs:`, `feat:`, `fix:`, `chore:`) and keep PRs focused.

## Codex dispatch

Read `.codex/README.md` and `.codex/codex_custom_instructions.md`, then use the relevant skill:

- `insight-preflight` — before commit/push;
- `insight-verify-no-model` — validate pipeline changes without downloading BERT;
- `insight-add-entity-pattern` — add a static regex entity end to end;
- `insight-optimize` — measured, minimal optimization of a real hot path.
- `insight-tokenizer-check` — bounded chunking, overlap, token coverage, and lazy-loading checks;
- `insight-state-contract` — malformed state, rollback, path semantics, and lazy restoration.

For fuller implementation checklists, consult the matching file under `.claude/skills/`.
