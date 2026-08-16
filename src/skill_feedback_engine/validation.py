"""Lightweight Agent Skill validation without third-party YAML dependencies."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_skill(path: Path) -> Dict[str, Any]:
    skill_file = path / "SKILL.md" if path.is_dir() else path
    errors: List[str] = []
    warnings: List[str] = []
    if not skill_file.exists():
        return {
            "valid": False,
            "path": str(skill_file),
            "errors": ["SKILL.md not found"],
            "warnings": warnings,
        }
    content = skill_file.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        errors.append("SKILL.md must start with YAML frontmatter")
        return {"valid": False, "path": str(skill_file), "errors": errors, "warnings": warnings}
    closing = content.find("\n---\n", 4)
    if closing == -1:
        errors.append("YAML frontmatter is not closed")
        return {"valid": False, "path": str(skill_file), "errors": errors, "warnings": warnings}
    fields: Dict[str, str] = {}
    for line in content[4:closing].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"\'')
    unexpected = sorted(set(fields) - {"name", "description"})
    if unexpected:
        warnings.append(
            "provider-specific frontmatter fields were not validated: " + ", ".join(unexpected)
        )
    name = fields.get("name", "")
    if not NAME_PATTERN.fullmatch(name):
        errors.append("name must contain only lowercase letters, digits, and single hyphens")
    if len(name) > 64:
        errors.append("name must be 64 characters or fewer")
    if not fields.get("description"):
        errors.append("description is required")
    body = content[closing + 5 :].strip()
    if not body:
        errors.append("skill instructions are required")
    return {
        "valid": not errors,
        "path": str(skill_file),
        "name": name,
        "errors": errors,
        "warnings": warnings,
    }
