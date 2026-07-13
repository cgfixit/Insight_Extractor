---
name: add-entity-pattern
description: Add a new static regex entity to Insight_Extractor while keeping the enum, pattern map, tests, README, and optional smoke coverage synchronized.
---

# Codex regex-entity workflow

Use the detailed checklist in \`.claude/skills/add-entity-pattern/SKILL.md\` as the implementation reference.

Before editing:

1. Read the actual signatures and current pattern behavior in \`config.py\`, \`constants.py\`, \`extractor.py\`, and the nearest unit tests.
2. Test the candidate regex against positive, negative, and near-miss strings.
3. Check overlap with existing patterns.

Keep the change synchronized:

- Add a \`PatternLabel\` member in \`src/insight_extractor/config.py\`.
- Add the raw pattern to \`REGEX_PATTERNS\` in \`src/insight_extractor/constants.py\`.
- Prefer non-capturing groups; \`re.findall\` returns captured groups instead of full matches.
- Test exact expected matches and a negative case in \`tests/unit/\`.
- Update the README regex table.
- Extend the model-free CI smoke input/assertion only when the entity is a core IOC and the existing gate is the right place.

Do not change \`models.py\`, the public API, or the dynamic keyword pipeline unless the request requires it. Run the \`preflight\` skill before commit and report any integration/model gate skipped.