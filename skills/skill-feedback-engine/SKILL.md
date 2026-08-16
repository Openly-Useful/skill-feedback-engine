---
name: skill-feedback-engine
description: Capture high-value feedback from agent work and turn recurring corrections, failures, reusable patterns, and validated outcomes into review-gated skill improvement proposals. Use when a user corrects an agent, a skill repeatedly underperforms, a workflow should become reusable, a successful technique should be preserved, or the user asks to review, improve, optimize, or maintain Agent Skills or SKILL.md files.
---

# Skill Feedback Engine

Observe work. Propose better skills. Keep evidence local and require review before changing any skill.

## Capture a signal

Capture only substantive, reusable feedback. Do not record ordinary task progress, project-specific next steps, guesses about user preferences, or information already handled by a memory system.

Classify the signal as one of:

- `correction`: The user corrected behavior, output, or interpretation.
- `failure`: A skill or workflow failed or caused avoidable rework.
- `pattern`: A repeatable method should become part of a skill.
- `outcome`: A technique was validated and should be preserved.

Record the smallest useful sanitized summary after finishing the user's task:

```sh
skill-feedback observe \
  --skill <skill-name> \
  --kind <correction|failure|pattern|outcome> \
  --summary "<reusable lesson>" \
  --source <provider-or-session>
```

Put sensitive detail only in `--evidence`. Evidence remains in the local database and is never included in proposal exports. Never include secrets intentionally.

If the CLI is unavailable, do not block the user's task. Briefly state that capture could not run and preserve no sensitive material elsewhere.

Read [references/observation-policy.md](references/observation-policy.md) when deciding whether a signal is durable enough to record.

## Review signals

Run the incremental review for routine scheduled work:

```sh
skill-feedback review
```

The incremental review requires repeated signals by default and leaves isolated observations pending. Run a full review only when the user explicitly asks for a complete analysis:

```sh
skill-feedback review --full
```

Inspect proposals before exporting them:

```sh
skill-feedback proposals --status draft
skill-feedback show <proposal-id>
```

## Prepare a reviewed change

Export a sanitized proposal bundle:

```sh
skill-feedback export <proposal-id>
```

Then:

1. Locate the source repository for the target skill.
2. Read its current `SKILL.md` and directly referenced resources.
3. Apply the smallest change supported by the proposal.
4. Validate the skill structure and run a representative forward test.
5. Present the exact diff for human review.
6. Open or update a draft PR only when repository access is authorized.
7. Never merge automatically.

Read [references/provider-adapters.md](references/provider-adapters.md) before installing activation or scheduling instructions for a specific agent provider.

## Boundaries

- Keep raw observations, evidence, and local paths private.
- Export only sanitized proposal text and opaque observation identifiers.
- Treat proposals as hypotheses, not proof that a skill should change.
- Prefer one open proposal or draft PR per skill; update it instead of generating PR spam.
- Leave system-managed and third-party plugin skills untouched unless their source and ownership are explicit.
- Do not duplicate durable user preferences from memory systems or project tasks from status trackers.
