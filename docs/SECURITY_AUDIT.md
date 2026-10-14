# Security Audit Report — insight-extractor v2.0.0
**Date:** 2026-06-24 (accelerate compatibility addendum: 2026-07-08; pip-audit triage addendum: 2026-10-14)
**Scanner tools:** pip-audit, bandit, detect-secrets  
**Scope:** `src/`, `requirements.txt`, `constraints.txt`, `.github/workflows/`

---

## Executive Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | — |
| High | 0 | — |
| Medium (SAST) | 1 | Accepted risk — see B615 below |
| CVE — Reachable | 0 | — |
| CVE — Unreachable | 11 | Documented below (8 conversion-script CVEs + 3 triaged 2026-10-14) |
| CVE — Fixed by upgrade | 18 | Resolved: pin transformers>=4.53.0 |
| Hardcoded secrets | 0 | Clean |
| Unpinned GH Actions | 0 | All pinned to @vN |

**Bottom line:** No reachable RCE or credential exposure. One SAST medium (HuggingFace model revision unpinned), 8 upstream CVEs with no fix in checkpoint-conversion utilities, and 3 advisories triaged 2026-10-14 (path-traversal / unconsented-write classes) — none exercised by this project's inference path.

---

## CVE Findings

### Resolved by upgrading transformers → 4.53.0 (18 CVEs)

| CVE | CVSS | Type | Fixed In |
|-----|------|------|----------|
| [CVE-2024-11392](https://osv.dev/vulnerability/GHSA-qxrp-vhvm-j765) | High | RCE — MobileViTV2 deserialization | 4.48.0 |
| [CVE-2024-11393](https://osv.dev/vulnerability/GHSA-wrfc-pvp9-mr9g) | High | RCE — MaskFormer deserialization | 4.48.0 |
| [CVE-2024-11394](https://osv.dev/vulnerability/GHSA-hxxf-235m-72v3) | High | RCE — Trax model deserialization | 4.48.0 |
| [CVE-2024-12720](https://osv.dev/vulnerability/GHSA-6rvg-6v2m-4j46) | Medium | ReDoS — tokenization_nougat_fast | 4.48.0 |
| [CVE-2025-2099](https://osv.dev/vulnerability/GHSA-qq3j-4f4f-9583) | Medium | ReDoS — preprocess_string() | 4.49.0 |
| [CVE-2025-1194](https://osv.dev/vulnerability/GHSA-fpwr-67px-3qhx) | Medium | ReDoS — GPT-NeoX-Japanese tokenizer | 4.50.0 |
| [CVE-2025-3263](https://osv.dev/vulnerability/GHSA-q2wp-rjmx-x6x9) | Medium | ReDoS — get_configuration_file() | 4.51.0 |
| [CVE-2025-3264](https://osv.dev/vulnerability/GHSA-jjph-296x-mrcr) | Medium | ReDoS — get_imports() | 4.51.0 |
| [CVE-2025-3777](https://osv.dev/vulnerability/GHSA-phhr-52qp-3mj4) | Medium | URL validation bypass — image_utils | 4.52.1 |
| [CVE-2025-3933](https://osv.dev/vulnerability/GHSA-37mw-44qp-f5jm) | Medium | ReDoS — DonutProcessor.token2json() | 4.52.1 |
| [CVE-2025-5197](https://osv.dev/vulnerability/GHSA-9356-575x-2w9m) | Medium | ReDoS — convert_tf_weight_name | 4.53.0 |
| [CVE-2025-6638](https://osv.dev/vulnerability/GHSA-59p9-h35m-wg4g) | Medium | ReDoS — MarianTokenizer | 4.53.0 |
| [CVE-2025-6051](https://osv.dev/vulnerability/GHSA-rcv9-qm8p-9p6j) | Medium | ReDoS — EnglishNormalizer | 4.53.0 |
| [CVE-2025-6921](https://osv.dev/vulnerability/GHSA-4w7r-h757-3r74) | Medium | ReDoS — AdamWeightDecay | 4.53.0 |
| [CVE-2026-1839](https://osv.dev/vulnerability/GHSA-69w3-r845-3855) | High | RCE — Trainer._load_rng_state() | 5.0.0rc3 |

**Reachability verdict:** `UNREACHABLE` for all 18. This project uses only `SentenceTransformer("all-MiniLM-L6-v2")` inference. None of the vulnerable code paths (Trax, MobileViTV2, MaskFormer, Nougat, GPT-NeoX-Japanese, Marian, Donut, Trainer RNG) are imported or called.  
**Action:** Upgrade to `transformers==4.53.0` (already applied in constraints.txt).

---

### No upstream fix available (8 CVEs) — Accepted Risk

| CVE | Type | Affected Component | Reachability |
|-----|------|--------------------|--------------|
| CVE-2025-14929 | RCE — X-CLIP checkpoint deserialization | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14926 | Code injection — SEW convert_config | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14927 | Code injection — SEW-D convert_config | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14928 | Code injection — HuBERT convert_config | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14920 | RCE — Perceiver deserialization | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14921 | RCE — Transformer-XL deserialization | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14924 | RCE — megatron_gpt2 deserialization | `convert_*` scripts | UNREACHABLE |
| CVE-2025-14930 | RCE — GLM4 deserialization | `convert_*` scripts | UNREACHABLE |

**Rationale:** All 8 affect `convert_*_to_pytorch` checkpoint-conversion CLI scripts only. This project never calls these scripts or imports these model classes. The attack vector requires a user to deliberately run a conversion script against a malicious checkpoint. Not applicable to inference-only use.  
**Review date:** 2027-01-01 or when upstream publishes a fix.

---

### Triaged 2026-10-14 — 3 advisories surfaced by `pip-audit` (no pin change)

Pinned set at triage: `transformers==4.53.0`, `accelerate==1.14.0`,
`sentence-transformers==5.6.0`. Verdicts below were traced against the installed
library source, not the advisory text alone.

| Advisory | Package | Type | Vulnerable entry point | Fixed In | Reachability |
|----------|---------|------|------------------------|----------|--------------|
| [PYSEC-2026-3804 / CVE-2026-69112](https://osv.dev/vulnerability/GHSA-4j2p-28q2-5m79) | accelerate ≤1.14.0 | Path traversal / DoS — sharded-checkpoint `weight_map` | `load_checkpoint_in_model`, `load_checkpoint_and_dispatch` | none published | UNREACHABLE |
| [PYSEC-2026-3929 / CVE-2026-9856](https://osv.dev/vulnerability/GHSA-xrqw-3rrv-vx5w) | transformers <5.10.0 | Arbitrary file write — `chat_template` keys used as filenames | `PreTrainedTokenizerBase.save_pretrained`, `ProcessorMixin.save_pretrained` | 5.10.0 | UNREACHABLE |
| [PYSEC-2026-4174 / CVE-2026-80047](https://osv.dev/vulnerability/GHSA-x9r9-c232-4q39) | transformers 4.49.0–5.8.1 | Unconsented remote-file write before `trust_remote_code` check | `GenerationMixin.load_custom_generate` | none for the 4.x line | UNREACHABLE |

**Rationale:**

- **PYSEC-2026-3804 (accelerate):** this project never imports `accelerate` directly.
  `transformers==4.53.0` references `load_checkpoint_and_dispatch` only in a docstring
  (`integrations/accelerate.py`) and loads sharded checkpoints with its own
  `modeling_utils` code path; `sentence-transformers==5.6.0` imports nothing from
  `accelerate` except its version string (`base/model_card.py`). The vulnerable
  functions are not on any call path from `SentenceTransformer(...)` or
  `AutoTokenizer.from_pretrained(...)`. `accelerate` stays pinned only for
  `init_empty_weights` (see the 2026-07-08 addendum).
- **PYSEC-2026-3929 (transformers `save_pretrained`):** the trigger is *saving* a
  tokenizer/processor loaded from a malicious Hub repo. This project calls neither
  `save_pretrained` nor `SentenceTransformer.save()`; in `sentence-transformers` the only
  `save_pretrained` call sites are `save()`, `push_to_hub`, and the trainer's `_save`
  (`base/modules/transformer.py`, `base/modules/input_module.py`, `base/trainer.py`),
  none of which the inference path invokes. **Becomes reachable** if a future change
  adds `model.save()` / `push_to_hub` — re-triage then, and note that the unpinned
  model revision (B615) is what makes the malicious-repo premise plausible.
- **PYSEC-2026-4174 (transformers `load_custom_generate`):** reachable only via
  `GenerationMixin.generate(custom_generate=...)` or from `from_pretrained` when
  `model.can_generate()` is true (`modeling_utils.py` ~L4872). `all-MiniLM-L6-v2` loads
  as `BertModel`, for which `can_generate()` is `False` and `load_custom_generate` is not
  even defined (verified in the pinned venv). This project never calls `generate()`.

**Action:** none. No bump is warranted on reachability grounds; `transformers 5.10.0`
would fix PYSEC-2026-3929 but crossing the `<5.0.0` ceiling is an ask-first major
migration, and the other two have no fix for the pinned lines.
**Review date:** 2027-01-01, or immediately if `save()` / `push_to_hub` / `generate()`
usage is added, or if `accelerate` publishes a fix.

---

## Addendum 2026-07-08 — accelerate/transformers import incompatibility (not a CVE)

**Finding:** the pin combination previously in `constraints.txt`
(`transformers==4.53.0` + `accelerate==0.34.2`) does not import successfully.
`transformers==4.53.0`'s `trainer.py` imports `TorchTensorParallelPlugin` from
`accelerate.utils`, a symbol introduced in `accelerate` 1.3.0 — `accelerate==0.34.2`
predates it. Result:

```
ImportError: cannot import name 'TorchTensorParallelPlugin' from 'accelerate.utils'
```

This fires the moment anything does `import sentence_transformers` (transitively,
`import insight_extractor.extractor`) — a constraints-pinned install cannot even
collect `tests/unit/`, let alone load a model. Not a security vulnerability; a
packaging-compatibility bug in the previous pin set.

**Verified reachable:** yes — reproduced in a clean Python 3.12 venv with
`pip install -r requirements.txt -c constraints.txt`.

**Fix applied:** `accelerate` floor raised to `>=1.3.0` in `requirements.txt` and
`pyproject.toml`; `constraints.txt` re-pinned to `accelerate==1.14.0` (latest at time
of fix, verified importable against `transformers==4.53.0` /
`sentence-transformers==3.4.1`). `transformers` and `sentence-transformers` pins are
unchanged — this addendum is scoped to `accelerate` only.

**Verification performed:**
- Clean-venv install with the new constraints succeeds
- `import accelerate, sentence_transformers, transformers` succeeds
- `from accelerate.utils import TorchTensorParallelPlugin` succeeds
- `from accelerate import init_empty_weights` still succeeds (the original fix this
  pin protects, unaffected by the bump)
- `pytest tests/unit/` — 89/89 pass (previously failed to collect)

### Note — additional `pip-audit` findings surfaced, not yet triaged

Re-running `pip-audit` against the actual installed (constraints-pinned) environment
as part of this fix surfaced 10 findings against `transformers==4.53.0`:
`PYSEC-2025-211` through `PYSEC-2025-218` (8 advisories — count matches the existing
"No upstream fix available" table above, likely the same GHSA advisories under PYSEC
identifiers rather than new ones, but not confirmed one-for-one) plus `CVE-2026-1839`
(already tracked above, verdict `UNREACHABLE`) and **`CVE-2026-4372`** (fixed in
`5.3.0`, **not yet triaged** — not present in this document prior to this addendum).

This is out of scope for an `accelerate`-only compatibility fix (bumping
`transformers` beyond `4.53.0` is a separate, ask-first change per this repo's
dependency rules). Flagged here for a dedicated `transformers` CVE re-triage —
identify `CVE-2026-4372`'s affected component and reachability verdict, and confirm
whether the `PYSEC-*` IDs are duplicates of the already-documented `CVE-2025-149xx`
series or net-new.

**2026-08-15 re-check:** re-ran `pip-audit` against a clean constraints-pinned install
(`transformers==4.53.0`) as part of a dependency-consistency verification pass. Same
`PYSEC-2025-211`..`218` and `PYSEC-2026-2288`/`2289` findings as above, plus one net-new
advisory not previously listed here: **`PYSEC-2026-2290`** (fixed in `5.5.0`), not yet
triaged. Rolled into the same dedicated `transformers` CVE re-triage noted above — no
verdict assigned, no pin changed.

**2026-10-14 re-check:** re-ran `pip-audit` against the constraints-pinned environment
(`transformers==4.53.0`, `accelerate==1.14.0`, `sentence-transformers==5.6.0`) during a
dependency-doc drift pass. Same findings as above plus three net-new advisories not
previously listed here: **`PYSEC-2026-3929`** (transformers, fixed in `5.10.0`),
**`PYSEC-2026-4174`** (transformers, no fix version reported), and
**`PYSEC-2026-3804`** (`accelerate`, no fix version reported — first advisory recorded
against `accelerate` in this document). Triaged the same day — see "Triaged 2026-10-14"
under CVE Findings above; all three `UNREACHABLE`, no pin changed.

---

## SAST Findings (bandit)

### B615 — HuggingFace Unsafe Download (MEDIUM / HIGH confidence)

**File:** `src/insight_extractor/tokenizer.py:26`  
**CWE:** [CWE-494](https://cwe.mitre.org/data/definitions/494.html) — Download of Code Without Integrity Check  
**Details:** `SentenceTransformer(model_name)` called without a pinned `revision=` hash. If the model hub is compromised, a malicious model update could be pulled.  
**Mitigation:** Pin the model revision in production:
```python
SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", revision="c9b44c9")
```
**Status:** Accepted for development use. Recommend pinning for any production deployment.

---

## Secret Scanning (detect-secrets)

**Result:** CLEAN — no API keys, tokens, passwords, or credentials detected in `src/`.

---

## GitHub Actions Audit

**Result:** All actions pinned to `@vN` version tags. No SHA-pinning (best practice for supply chain hardening, lower priority for personal projects).

---

## Hardened Manifest Changes Applied

```diff
--- a/requirements.txt
+++ b/requirements.txt
-sentence-transformers>=3.0.0,<4.0.0
+sentence-transformers>=3.4.1,<4.0.0
-transformers>=4.40.0,<4.45.0
+transformers>=4.53.0,<5.0.0
+accelerate>=0.26.0

--- a/constraints.txt
+++ b/constraints.txt
-sentence-transformers==3.0.1
+sentence-transformers==3.4.1
-transformers==4.44.2
+transformers==4.53.0
+accelerate==0.34.2
```

### 2026-10-06 addendum — sentence-transformers major bump (commit 1d45bf1, dependabot)

```diff
--- a/requirements.txt (and pyproject.toml)
+++ b/requirements.txt (and pyproject.toml)
-sentence-transformers>=3.4.1,<4.0.0
+sentence-transformers>=5.6.0,<6.0.0

--- a/constraints.txt
+++ b/constraints.txt
-sentence-transformers==3.4.1
+sentence-transformers==5.6.0
```

No pip-audit findings were triaged with this bump itself; the three net-new advisories
found on 2026-10-14 are triaged under CVE Findings above. `transformers==4.53.0` and
`accelerate==1.14.0` are unchanged and the import triangle was re-verified on 2026-10-14
(Python 3.12.3 and 3.13.16, clean venvs, `-c constraints.txt`).

### 2026-07-08 addendum — accelerate compatibility fix

```diff
--- a/requirements.txt
+++ b/requirements.txt
-accelerate>=0.26.0
+accelerate>=1.3.0

--- a/constraints.txt
+++ b/constraints.txt
-accelerate==0.34.2
+accelerate==1.14.0

--- a/pyproject.toml
+++ b/pyproject.toml
-    "accelerate>=0.26.0",
+    "accelerate>=1.3.0",
```

---

## Remediation Commands

```bash
# Apply all fixes at once (Linux / macOS / Windows)
python -m pip install -r requirements.txt -c constraints.txt
python -m pip install -e .

# Verify clean
pip-audit -r requirements.txt
```
