# Skill Feedback Engine

**Observe work. Propose better skills.**

[![CI](https://github.com/Openly-Useful/skill-feedback-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Openly-Useful/skill-feedback-engine/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Openly-Useful/skill-feedback-engine)](https://github.com/Openly-Useful/skill-feedback-engine/releases/latest)
[![Openly Useful](https://img.shields.io/badge/Openly%20Useful-openlyuseful.org-247a4b)](https://openlyuseful.org/#projects)

Skill Feedback Engine is a local-first, provider-neutral feedback loop for Agent Skills. It captures high-value corrections, failures, reusable patterns, and validated outcomes; groups recurring signals; and prepares sanitized, review-gated skill improvement proposals.

It does not silently rewrite skills, publish conversation history, or merge pull requests.

## Status

This repository contains the functional [`v0.1.0`](https://github.com/Openly-Useful/skill-feedback-engine/releases/tag/v0.1.0) core:

- Standard-library Python CLI with no runtime dependencies.
- Concurrent-safe SQLite state under `~/.local/share/skill-feedback-engine` by default.
- Incremental reviews that require repeated signals.
- Explicit full reviews for inspecting single signals.
- Sanitized Markdown and JSON proposal bundles.
- A portable Agent Skill plus Codex, Claude, and generic adapters.
- A macOS 4:00 AM local-time scheduler template.

The proposal engine is deterministic in v0.1. It stages evidence-backed briefs; an agent or human applies and validates the actual `SKILL.md` diff.

## Quick start

Python 3.9 or newer is required.

```sh
python3 -m pip install -e .
skill-feedback init
```

Capture two related signals:

```sh
skill-feedback observe \
  --skill engineering-code-review \
  --kind correction \
  --summary "Lead reviews with actionable findings and include exact file locations."

skill-feedback observe \
  --skill engineering-code-review \
  --kind correction \
  --summary "Keep review summaries secondary to concrete findings."
```

Create and inspect a draft proposal:

```sh
skill-feedback review
skill-feedback proposals --status draft
skill-feedback show <proposal-id>
skill-feedback export <proposal-id>
```

For a complete on-demand pass that includes isolated signals:

```sh
skill-feedback review --full
```

## How it works

```text
agent work
   ↓
local observations ── raw evidence stays local
   ↓
incremental or full review
   ↓
sanitized draft proposal
   ↓
validated skill diff
   ↓
human-approved PR
```

Routine reviews require `review.minimum_signals` observations in the same skill and signal category. The default is two. A successful review marks only the observations included in a generated proposal; unmatched signals remain pending.

## Commands

| Command | Purpose |
| --- | --- |
| `skill-feedback init` | Initialize local configuration and SQLite state. |
| `skill-feedback targets` | List canonical skill and source mappings. |
| `skill-feedback map-target` | Map aliases to a source PR, personal repo, or inbox route. |
| `skill-feedback observe` | Capture a correction, failure, pattern, or outcome. |
| `skill-feedback status` | Show observation and proposal queue counts. |
| `skill-feedback review` | Review repeated pending signals. |
| `skill-feedback review --full` | Review all pending signal groups. |
| `skill-feedback proposals` | List generated proposals. |
| `skill-feedback show ID` | Inspect a proposal and its local metadata. |
| `skill-feedback export ID` | Produce a sanitized PR-ready bundle. |
| `skill-feedback set-status ID STATUS` | Record an accepted or rejected decision. |
| `skill-feedback validate PATH` | Validate basic Agent Skill structure. |

Use `--home PATH` before the command or set `SKILL_FEEDBACK_HOME` to move the state directory.

## Configuration

The engine creates `config.json` on first use:

```json
{
  "schema_version": 1,
  "review": {
    "minimum_signals": 2
  },
  "privacy": {
    "export_evidence": false
  },
  "targets": []
}
```

`privacy.export_evidence` is reserved and must remain `false` in this release. Raw evidence is intentionally absent from proposal payloads and exports.

### Target mappings

Map the identifier agents commonly use to the canonical `name` declared by the target `SKILL.md`:

```sh
skill-feedback map-target \
  --skill code-review \
  --alias engineering-code-review \
  --source-path ~/.codex/plugins/example/skills/code-review \
  --repository openly-useful/personal-skills \
  --repository-path skills/code-review \
  --delivery personal
```

Delivery strategies are:

- `source-pr`: propose the change to the skill's owned upstream repository.
- `personal`: route the proposal to a private personal-skills repository.
- `inbox`: stage the proposal for manual ownership resolution.

Local `source_path` values remain private. Sanitized exports include only the delivery strategy, repository identifier, and repository-relative path.

## Install the Agent Skill

The portable skill is in `skills/skill-feedback-engine`.

For Codex user-level discovery:

```sh
cp -R skills/skill-feedback-engine ~/.codex/skills/skill-feedback-engine
```

Then add `adapters/codex/AGENTS.snippet.md` to the applicable persistent instructions. This avoids modifying a separate curated `.agents/skills` pool.

Provider adapters contain activation guidance only. They all use the same CLI, database, observation policy, and export format.

## Daily review on macOS

`adapters/codex/com.openlyuseful.skill-feedback-engine.plist` is a launchd template for 4:00 AM in the machine's local timezone, including daylight-saving changes.

Replace `__SKILL_FEEDBACK_EXECUTABLE__` with the absolute path returned by `command -v skill-feedback`, copy the file to `~/Library/LaunchAgents`, and load it with `launchctl`. The scheduled command runs an incremental review and creates nothing when there are no qualifying observations.

## Privacy and review boundary

- Observation summaries are sanitized before storage.
- Optional evidence is local-only and excluded from every export.
- Export bundles contain sanitized summaries, rationale, and opaque observation IDs.
- Redaction is defense in depth, not a substitute for inspecting a proposal before publishing it.
- The engine never edits a target skill or opens, merges, or updates a PR by itself.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m skill_feedback_engine --help
python3 -m skill_feedback_engine validate skills/skill-feedback-engine
```

When running directly from a checkout without installing it, set `PYTHONPATH=src` before the `python3 -m skill_feedback_engine` commands.
