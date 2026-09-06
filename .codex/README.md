# `.codex/`

Codex-specific onboarding for `Insight_Extractor`.

## Files

- `AGENTS.md` — detailed project guidance loaded through the root `AGENTS.md` entrypoint.
- `codex_custom_instructions.md` — review-first behavior, minimal diffs, and secret safety.
- `ponytail-plugin.json` — existing optional Ponytail metadata.
- `skills/` — maintained workflow references.
- `../.agents/skills/` — discoverable repository skill entrypoints with `insight-` names.

The root `AGENTS.md` is Codex's auto-discovered entrypoint and delegates here.
`CLAUDE.md` remains the detailed historical operating manual. Do not duplicate runtime
architecture or dependency pins here.

## Discovery

Codex discovers repository skills under `.agents/skills`; `.codex/skills` alone is
not the documented repository discovery location. The four thin entrypoints link
to the maintained workflows here, avoiding duplicate checklists and collisions with
personal skills such as `preflight` and `optimize`. See the
[official skill discovery documentation](https://developers.openai.com/codex/skills/).
Open a new task in this checkout if the new skills are missing from the current catalog.

`skills/Insight-Optimizer/SKILL.md` is an optional extended optimization reference
(`name: insight-optimizer`); `skills/fable-protocol/SKILL.md` is historical owner
guidance, not a default project entrypoint. Its cross-project and model claims are
not evidence about this codebase. `ponytail-plugin.json` is reference metadata,
not proof that a plugin or hooks are installed.

## Skill dispatch

| Skill | Use it for |
|---|---|
| `insight-preflight` | Ruff, formatting, strict mypy, unit tests, smoke checks, and staging hygiene before a commit or push |
| `insight-verify-no-model` | Regex/dynamic/full-fake pipeline verification without a HuggingFace download |
| `insight-add-entity-pattern` | Adding a new static regex entity and synchronizing enum, pattern, tests, docs, and smoke coverage |
| `insight-optimize` | A small, measured improvement to regex, stemmer, state, or dynamic-expansion hot paths |

The skills reuse the existing `.claude/skills/` checklists where those are more detailed. The Codex versions are the entrypoints and add Windows-friendly commands plus explicit stop conditions.

## Safe defaults

- Keep model loading lazy.
- Keep unit validation offline and deterministic.
- Keep dependency changes separate and synchronized across all three manifests.
- Use a feature branch and a draft PR for repository changes.
- Do not add money-mode behavior or unrelated product features.
