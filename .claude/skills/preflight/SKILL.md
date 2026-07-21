---
name: preflight
description: Run this repo's full CI gauntlet locally (ruff check, ruff format, mypy strict, unit tests, smoke-test logic, artifact check) and fix failures before committing or pushing. Use before every commit/push, when the user says "check CI", "preflight", "is this ready to push", or after any multi-file edit.
---

# preflight — local CI gauntlet for Insight_Extractor

Reproduce every required CI gate locally, in CI order, and fix what fails. CI's
`ci-pass` gate requires **lint + typecheck + unit-tests + smoke-test** all green;
gitleaks runs in parallel. Three separate commits in this repo's history exist only to
mop up CI failures that this checklist would have caught (`9e5f8ff`: 41 ruff violations;
`c3fef9b`: 12 mypy errors + 9 test failures; `9de30c7`: one E501). Don't add a fourth.

## Step 0 — Ensure the environment is installed

```bash
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install -e ".[dev]"
```

If already installed this session, skip. If torch download is impossible in this
environment, run gates 1–2 anyway (they only need ruff), attempt 3–4, and explicitly
report anything skipped in the commit/PR body — that reporting is a repo convention.

## Gate 1 — ruff lint

```bash
ruff check src/ tests/
```

Fix findings by hand (or `ruff check --fix` for safe autofixes, then re-read the diff).
Historical offenders in this repo and their fixes:

| Rule | Meaning | Fix |
|---|---|---|
| E501 | line > 100 chars (repo uses 100, not 88/120) | wrap; for strings use implicit concat or parens |
| B904 | `raise` in `except` without `from` | `raise NewError(...) from exc` (or `from None` to suppress) |
| B905 | `zip()` without `strict=` | add `strict=False` (or `True` when lengths must match) |
| UP017 | `timezone.utc` | use `datetime.UTC` |
| F401 | unused import | delete it — don't `# noqa` |
| B033 | duplicate item in set literal | delete the duplicate |
| I001 | unsorted imports | `ruff check --fix` handles it |
| SIM300 | yoda condition | put the variable on the left |

## Gate 2 — ruff format

```bash
ruff format --check src/ tests/
```

If anything "would be reformatted": run `ruff format src/ tests/`, then **re-run Gate 1**
(formatting can change line lengths).

## Gate 3 — mypy strict

```bash
mypy src/insight_extractor
```

Strict mode; tests are not type-checked, `src/` is. Known traps and sanctioned fixes:

- `sklearn.*` / `yaml` imports: `# type: ignore[import-untyped]` on the import line.
- `AutoTokenizer.from_pretrained(...)`: `# type: ignore[no-untyped-call]`; calls to
  `.encode`/`.decode` on it: `# type: ignore[attr-defined]` (match `tokenizer.py`).
- Conditionally forwarding keyword-only args: **never** `**({...} if x else {})` —
  mypy reads it as a positional arg and errors (commit `114b00a`). Write two explicit
  call branches.
- Fields typed `tuple[str, ...]` (e.g. `KeywordStats.custom_suffixes`): build with
  `tuple(...)`, not `list(...)`.
- Never fix a mypy error by widening a type to `Any` or removing an annotation; never
  add a bare `# type: ignore` without a bracketed code.

## Gate 4 — unit tests

```bash
pytest tests/unit/ -v --tb=short
```

- Must pass with **no network** and no model download. If a test hangs or tries to
  download `all-MiniLM-L6-v2`, a real model/tokenizer property is being touched — stub
  it via `extractor._model = FakeModel()` / `extractor._tokenizer = FakeTokenizer()`
  (pattern at the top of `tests/unit/test_extractor.py`).
- Never mark a failing test skip/xfail to pass this gate. If the test asserts phantom
  behavior, verify against the source + `docs/SPEC.md`, fix the test, and say so in the commit
  body.
- If both 3.12 and 3.13 are available locally, run both (CI matrixes both); otherwise
  note the single version tested.

## Gate 5 — smoke-test logic (only when relevant)

Run this when the change touches `constants.py` (patterns/seeds), the packaging config,
or any import path of `config`/`constants`/`models`/`exceptions`/`utils`:

```bash
python -c "
import re
from insight_extractor.constants import REGEX_PATTERNS, THREAD_SEEDS
text = 'Ransomware exploited CVE-2026-12345 via port 4444 at 192.168.1.254.'
found = {label: re.findall(p, text, re.IGNORECASE) for label, p in REGEX_PATTERNS.items()}
assert found['CVE_ID'], found
print('smoke logic OK:', {k: v for k, v in found.items() if v})
"
```

This mirrors what `.github/workflows/ci.yml` smoke-test does on a **runtime-only
install**: if your change makes `insight_extractor.constants` import torch/transformers
(directly or transitively), the CI job breaks even though everything above passed.

## Gate 6 — staging hygiene

```bash
git status --short
git diff --cached --stat
```

Confirm none of these are staged (deny-list — one JUnit file was committed to `main`
once, commit `2d2113e`):

`insights_extracted.md` · `insight_extractor_state.json` · `junit*.xml` ·
`coverage.xml` · `.coverage` · `smoke_results.json` · `*.log` · venvs/caches ·
anything under `~/.cache/huggingface`

(`sample_extracted_insights.md` is a checked-in fixture and is allowed.)

Also scan the staged diff for anything secret-shaped — gitleaks scans every push and a
realistic-looking fake token will block the PR.

## Step 7 — commit

Format (house style — see `git log` commits `40e81fe`, `c3fef9b`):

```
<type>: <imperative subject ≤72 chars>

- <change>: <root cause / why>
- <change>: <root cause / why>
```

Types used here: `fix:`, `feat:`, `chore:`, `docs:`. Stage named files explicitly
(`git add path1 path2`), not `git add -A`.

## Exit report

End with a one-line status per gate, e.g.:

```
ruff check ✓ | ruff format ✓ | mypy ✓ | unit 3.12 ✓ (48 passed) | smoke n/a | staging clean ✓
```

Anything not run gets `SKIPPED: <reason>` — and that same line goes in the PR body.
