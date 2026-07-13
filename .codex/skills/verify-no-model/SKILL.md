---
name: verify-no-model
description: Verify regex, dynamic-keyword, and full extraction orchestration without downloading the HuggingFace BERT model. Use after extractor, stemmer, tokenizer, constants, models, or output changes.
---

# Codex model-free verification

Use the detailed checklist in `.claude/skills/verify-no-model/SKILL.md` for the full fake-model patterns. This is the Codex entrypoint.

Rules:

- Run from a disposable directory, never the repository root.
- Regex and dynamic keyword paths must not access `.model` or `.tokenizer`.
- For full-pipeline tests, inject `extractor._model` and `extractor._tokenizer` before calling `extract()` or `load_state()`.
- Do not use `seed_keywords=[]` to mean “no keywords”; the implementation treats falsy input as the default seed bank.
- Assert concrete values such as a known CVE, IP, or entity, not merely non-empty output.
- Confirm the Markdown report and JSON state round-trip in the disposable directory, then confirm the repository has no generated artifacts.

A minimal model-free check:

```powershell
$verify = Join-Path $env:TEMP "insight-extractor-verify"
New-Item -ItemType Directory -Force $verify | Out-Null
Push-Location $verify
try {
    python -c "from insight_extractor.extractor import InsightExtractor; x=InsightExtractor(seed_keywords=['ransomware','CVE'], output_dir='.'); text='Ransomware exploited CVE-2026-12345 at 192.168.1.10'; assert x.extract_regex_entities(text)['CVE_ID'] == ['CVE-2026-12345']; print('model-free regex OK')"
} finally {
    Pop-Location
}
```

Escalate to `tests/integration/` only when changing model loading, real tokenization, embedding behavior, dependency compatibility, or model-path error handling. Use `[run-integration]` or workflow dispatch for that gate, and report it explicitly if skipped.