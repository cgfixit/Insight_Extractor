# `.codex/`

Codex-specific onboarding for `Insight_Extractor`.

## Files

- `codex_custom_instructions.md` — review-first behavior, minimal diffs, and secret safety.
- `ponytail-plugin.json` — existing optional Ponytail metadata.
- `skills/` — Codex-native project workflows.

`AGENTS.md` owns repository-wide rules. `CLAUDE.md` remains the detailed historical operating manual. Do not duplicate runtime architecture or dependency pins here.

## Skill dispatch

| Skill | Use it for |
|---|---|
| `preflight` | Ruff, formatting, strict mypy, unit tests, smoke checks, and staging hygiene before a commit or push |
| `verify-no-model` | Regex/dynamic/full-fake pipeline verification without a HuggingFace download |
| `add-entity-pattern` | Adding a new static regex entity and synchronizing enum, pattern, tests, docs, and smoke coverage |
| `optimize` | A small, measured improvement to regex, stemmer, state, or dynamic-expansion hot paths |

The skills reuse the existing `.claude/skills/` checklists where those are more detailed. The Codex versions are the entrypoints and add Windows-friendly commands plus explicit stop conditions.

## Safe defaults

- Keep model loading lazy.
- Keep unit validation offline and deterministic.
- Keep dependency changes separate and synchronized across all three manifests.
- Use a feature branch and a draft PR for repository changes.
- Do not add money-mode behavior or unrelated product features.