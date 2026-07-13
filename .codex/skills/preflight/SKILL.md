---
name: preflight
description: Run the Insight_Extractor validation gates before committing or pushing. Use for readiness checks, multi-file edits, CI questions, and docs or skill changes that affect repository workflow.
---

# Codex preflight

Use the detailed checklist in \`.claude/skills/preflight/SKILL.md\` as the implementation reference. This file is the Codex entrypoint.

Run from the repository root in PowerShell:

\`\`\`powershell
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
python -m mypy src/insight_extractor
python -m pytest tests/unit/ -v --tb=short
git diff --check
git status --short
\`\`\`

For changes to \`config.py\`, \`constants.py\`, packaging, or import boundaries, also run the model-free smoke check from the detailed checklist. Do not run the CLI from the repository root because it writes \`insights_extracted.md\` and \`insight_extractor_state.json\`.

Before staging, reject generated artifacts:

- \`insights_extracted.md\`
- \`insight_extractor_state.json\`
- \`junit*.xml\`
- \`coverage.xml\`
- \`.coverage\`
- \`*.log\`
- model or HuggingFace caches

Do not weaken a gate, skip a failing test, or add a bare type ignore. If dependencies are missing, report the exact skipped gate. Real model downloads belong to integration verification, not unit preflight.

Exit with one status per gate, including explicit skips.