# Provider adapters

Keep the engine state and review policy provider-neutral. Limit adapters to discovery, activation, observation handoff, and scheduling.

## Codex

- Install the skill folder under `~/.codex/skills/skill-feedback-engine` for user-level discovery.
- Add the repository's `adapters/codex/AGENTS.snippet.md` to the applicable `AGENTS.md`.
- Use the launchd template for a local 4:00 AM review on macOS, or a Codex automation when available.

## Claude Code

- Install the skill in the user or project skill location supported by the active Claude Code version.
- Add `adapters/claude/CLAUDE.snippet.md` to the applicable instructions file.
- Keep capture best-effort so an unavailable CLI never blocks the user's task.

## Other agents

- Place `SKILL.md` where the provider discovers Agent Skills.
- Adapt `adapters/generic/INSTRUCTIONS.snippet.md` to the provider's persistent instruction mechanism.
- Invoke the same `skill-feedback` CLI and use the same local state directory.

Do not put provider-specific fields in the core configuration or observation schema.
