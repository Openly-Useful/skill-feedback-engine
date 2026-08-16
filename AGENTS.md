# Repository guidance

Keep the core provider-neutral and dependency-light. Provider-specific activation and scheduling belong under `adapters/`.

Before claiming completion, run:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m skill_feedback_engine validate skills/skill-feedback-engine
plutil -lint adapters/codex/com.openlyuseful.skill-feedback-engine.plist
```

Preserve these boundaries:

- Raw evidence remains local and absent from exports.
- Proposals require review; never edit skills or merge PRs automatically.
- The routine review stays incremental and no-ops without qualifying signals.
- The on-demand full review must be explicit.
- Keep Python compatibility at 3.9 or newer unless the project contract changes.
