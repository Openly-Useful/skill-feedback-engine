"""Conservative redaction for summaries and export-safe proposal payloads."""

from __future__ import annotations

import re


REPLACEMENTS = (
    (re.compile(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)\b(?:bearer|token|api[_ -]?key)\s*[:=]?\s+[A-Za-z0-9._~+/=-]{12,}"), "[REDACTED_CREDENTIAL]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    (re.compile(r"/(?:Users|home)/[^/\s]+"), "~"),
)


def sanitize(value: str) -> str:
    result = value.strip()
    for pattern, replacement in REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result
