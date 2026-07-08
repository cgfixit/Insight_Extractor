---
name: deps-security-refresh
description: Bump or audit dependencies safely — keep requirements.txt, constraints.txt, and pyproject.toml in sync, verify the transformers/sentence-transformers/accelerate compatibility triangle, run pip-audit and bandit, and update docs/SECURITY_AUDIT.md with reachability verdicts. Use for any dependency upgrade, new CVE report, Dependabot-style alert, or scheduled security refresh.
---

# deps-security-refresh — dependency bump + CVE audit

Dependencies here are not routine: a wrong combination produces a runtime crash
(`ModelLoadError: name 'init_empty_weights' is not defined`), and the pins encode a
deliberate CVE posture documented in `docs/SECURITY_AUDIT.md`. This skill keeps all of
that consistent.

## Non-negotiables (from CLAUDE.md)

- Version bounds live in **three files** that must move together:
  1. `requirements.txt` — ranges + explanatory comments
  2. `constraints.txt` — exact `==` pins (the reproducible known-good set)
  3. `pyproject.toml` `[project] dependencies` — ranges (keep identical to
     `requirements.txt`)
- `accelerate` is **load-bearing**: nothing imports it, but sentence-transformers'
  model loading needs it at runtime. Removing it reintroduces the
  `init_empty_weights` crash. Never "clean it up" as unused.
- `transformers` floor is `>=4.53.0` — below that, 18 fixed CVEs reopen (ReDoS + RCE
  batches, see the audit doc). Ceiling `<5.0.0` — untested major.
- `sentence-transformers` stays `>=3.4.1,<4.0.0` unless the task is explicitly a major
  migration (that's an ask-first change).
- Bumping pins beyond what the task explicitly requires is an **ask-first** action.

## Step 1 — Establish scope

Identify exactly which packages the task requires changing and why (new CVE, feature
need, upstream fix). Everything else stays pinned. Write the list down; it becomes the
commit body.

## Step 2 — Edit the three files together

For each package: update the range in `requirements.txt` **and** `pyproject.toml`
(identically), and the exact pin in `constraints.txt`. Update the affected comments —
the comments are maintained documentation here (they carry the crash signatures and CVE
rationale), not decoration. If a comment's claim is no longer true after your bump
(e.g. "4.53.0 clears all fixable CVEs"), fix the comment.

## Step 3 — Verify the install and the compatibility triangle

In a clean venv (Python 3.12):

```bash
python -m venv /tmp/depcheck && . /tmp/depcheck/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install -e .
```

Then the triangle check — the historical failure mode is
transformers/sentence-transformers/accelerate drifting apart:

```bash
python - << 'EOF'
import accelerate, sentence_transformers, transformers
print("transformers", transformers.__version__)
print("sentence-transformers", sentence_transformers.__version__)
print("accelerate", accelerate.__version__)
from accelerate import init_empty_weights  # the symbol whose absence caused ModelLoadError
from sentence_transformers import SentenceTransformer  # import path intact
print("triangle OK")
EOF
```

If the environment allows a model download, also instantiate
`SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` once — that is the
actual crash site. If not possible, say so in the report (skips are reported, never
hidden).

Known failure this check catches (verified 2026-07, Linux/py3.12): the current
constraints set `transformers==4.53.0` + `accelerate==0.34.2` fails at import with
`ImportError: cannot import name 'TorchTensorParallelPlugin'` — transformers 4.53's
trainer needs `accelerate>=1.3.0`. CI masks it by installing without constraints.

## Step 4 — Scan

```bash
python -m pip install pip-audit bandit
pip-audit -r requirements.txt
bandit -r src/ -q
```

For every `pip-audit` finding, produce a **reachability verdict** in the established
format (see `docs/SECURITY_AUDIT.md`): is the vulnerable code path imported/called by
this project's inference-only usage of `all-MiniLM-L6-v2`? Verdicts are `UNREACHABLE`
(with the rationale naming the vulnerable component) or reachable → the bump must fix
it or the task escalates to the owner.

Known accepted findings (do not re-litigate, do not "fix"):
- bandit B615 (unpinned HF model revision in `tokenizer.py`) — accepted for dev,
  documented in the audit.
- CVE-2025-1492x family (checkpoint-conversion scripts) — UNREACHABLE, no upstream fix,
  review date recorded in the audit doc.

## Step 5 — Update `docs/SECURITY_AUDIT.md`

Keep the existing document structure (it's the template): date + tools header, executive
summary table, CVE tables split into *resolved by upgrade* / *no upstream fix — accepted
risk*, reachability rationale, and the diff of manifest changes. Update:

- [ ] the **Date** and scanner tool list
- [ ] executive-summary counts
- [ ] CVE tables — move entries between resolved/accepted as appropriate, add new ones
      with OSV links in the same `[CVE-…](https://osv.dev/vulnerability/…)` style
- [ ] the "Hardened Manifest Changes Applied" diff block to reflect this bump
- [ ] the review date for accepted risks

## Step 6 — Verify nothing else broke

```bash
ruff check src/ tests/ && ruff format --check src/ tests/
mypy src/insight_extractor
pytest tests/unit/ -v --tb=short
```

Also re-read the README **"Known Issue — ModelLoadError"** section: it documents
specific versions as the fix. If your bump changes which versions are correct, update
that section and the install snippets.

## Step 7 — Commit

```
chore: bump <pkg> <old> -> <new>, refresh security audit

- <pkg>: <why — CVE id / upstream fix>, verdict per pip-audit: <summary>
- requirements.txt / constraints.txt / pyproject.toml updated in sync
- SECURITY_AUDIT.md: <counts> refreshed, review date <date>
- skipped: <anything not verifiable in this environment>
```

## Full checklist

- [ ] three manifest files updated identically
- [ ] comments in manifests still true
- [ ] clean-venv install succeeds with constraints
- [ ] triangle check passes (`init_empty_weights` importable)
- [ ] `pip-audit` clean or every finding has a written reachability verdict
- [ ] `docs/SECURITY_AUDIT.md` fully refreshed (all five bullets in Step 5)
- [ ] README Known-Issue section still accurate
- [ ] four CI gates green
- [ ] out-of-scope pins untouched
