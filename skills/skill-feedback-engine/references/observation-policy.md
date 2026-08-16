# Observation policy

## Record

Record feedback when at least one condition holds:

- The user explicitly corrects agent behavior that could recur.
- The same skill failure or workaround appears more than once.
- A provider-neutral workflow would save meaningful effort in future tasks.
- A technique succeeds under a concrete validation step.

Use a stable skill identifier. Summarize the reusable lesson rather than the surrounding conversation.

## Do not record

Do not record:

- Secrets, credentials, personal data, private repository content, or verbatim conversations.
- Ordinary progress updates or one-time project decisions.
- Speculation about what the user prefers.
- Feedback that belongs only in a code fix, issue tracker, project status file, or durable memory system.
- Model output that was never checked.

## Sensitivity

Use `private` by default. Use `shareable` only when the summary is already suitable for a public proposal. Evidence remains local regardless of sensitivity.

Before exporting, inspect the generated bundle. Automated redaction reduces risk but does not replace human review.
