#!/usr/bin/env python3
"""Validate skill-only Codex/Claude registration against publisher metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PYPROJECT_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
PYTHON_VERSION = re.compile(r'^__version__\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def read_json(path: Path, errors: List[str]) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"{path.relative_to(ROOT)} is missing or invalid JSON")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must contain a JSON object")
        return {}
    return value


def validate_registration(root: Path = ROOT) -> List[str]:
    errors: List[str] = []
    publisher = read_json(root / "publisher" / "publisher.json", errors)
    if publisher.get("schemaVersion") != 1:
        errors.append("publisher schemaVersion must be 1")
    if publisher.get("authorityManifest") != "https://openlyuseful.org/publisher/manifest.json":
        errors.append("publisher authority manifest is invalid")
    identity = publisher.get("publisher")
    expected_identity = {
        "displayName": "Openly Useful",
        "homepage": "https://openlyuseful.org",
        "studio": "https://openlyuseful.com",
        "publicContact": "hello@openlyuseful.org",
    }
    if identity != expected_identity:
        errors.append("publisher identity does not match Openly Useful")
    legal = publisher.get("plannedLegalEntity")
    if not isinstance(legal, dict) or legal.get("name") != "Openly Useful LLC" or legal.get("status") != "formation-pending":
        errors.append("planned entity must be Openly Useful LLC with formation-pending status")
    elif sorted(legal.get("roles", [])) != ["licensee", "operator", "publisher"]:
        errors.append("planned entity roles are invalid")
    expected_operator = {
        "status": "founder-operated",
        "type": "founder-individual",
        "displayName": "Founder of Openly Useful",
        "operatingAs": "Openly Useful",
    }
    if publisher.get("currentOperator") != expected_operator:
        errors.append("current operation must remain founder-operated while formation is pending")
    expected_publication = {
        "externalPublicationAllowed": True,
        "authorization": "granted",
        "authorizationBasis": "founder-owner-direct",
        "effectiveWhileFormationPending": True,
        "blockingRequirements": [
            "namespace-verification",
            "provider-account-authentication",
            "provider-review",
        ],
    }
    if publisher.get("publication") != expected_publication:
        errors.append("external publication must use founder-owner-direct authority while formation is pending")

    component = publisher.get("component")
    if not isinstance(component, dict):
        errors.append("publisher component metadata is required")
        return errors
    if component.get("name") != "skill-feedback-engine" or not SEMVER.fullmatch(str(component.get("version", ""))):
        errors.append("component identity/version is invalid")
    if component.get("skillNames") != ["skill-feedback-engine"]:
        errors.append("component must expose exactly one canonical skill")
    if component.get("mcp") is not False:
        errors.append("Skill Feedback Engine must explicitly remain MCP-free")

    component_version = str(component.get("version", ""))
    version_sources = [
        ("package", root / "pyproject.toml", PYPROJECT_VERSION),
        ("runtime", root / "src" / "skill_feedback_engine" / "__init__.py", PYTHON_VERSION),
    ]
    for label, path, pattern in version_sources:
        try:
            match = pattern.search(path.read_text(encoding="utf-8"))
        except OSError:
            match = None
        if match is None or match.group(1) != component_version:
            errors.append(f"{label} version must match publisher component version")
    project_status = read_json(root / ".project-status" / "manifest.json", errors)
    if project_status.get("initiative", {}).get("release") != f"v{component_version}":
        errors.append("project status release must match publisher component version")

    skill_artifacts = sorted(path.relative_to(root).as_posix() for path in (root / "skills").rglob("SKILL*.md"))
    if skill_artifacts != ["skills/skill-feedback-engine/SKILL.md"]:
        errors.append("duplicate or unexpected SKILL artifacts: " + ", ".join(skill_artifacts))

    author = {
        "name": expected_identity["displayName"],
        "email": expected_identity["publicContact"],
        "url": expected_identity["homepage"],
    }
    common = {
        "name": component.get("name"),
        "version": component.get("version"),
        "author": author,
        "homepage": component.get("repository"),
        "repository": component.get("repository"),
        "license": component.get("license"),
        "skills": component.get("skillsPath"),
    }
    codex = read_json(root / ".codex-plugin" / "plugin.json", errors)
    claude = read_json(root / ".claude-plugin" / "plugin.json", errors)
    for label, manifest in (("Codex", codex), ("Claude", claude)):
        for field, expected in common.items():
            if manifest.get(field) != expected:
                errors.append(f"{label} plugin {field} does not derive from publisher metadata")
        if "mcpServers" in manifest or (root / ".mcp.json").exists():
            errors.append(f"{label} skill-only registration cannot declare MCP")
    interface = codex.get("interface")
    if not isinstance(interface, dict):
        errors.append("Codex interface metadata is required")
    else:
        policies = publisher.get("policies", {})
        if interface.get("displayName") != component.get("displayName"):
            errors.append("Codex display name mismatch")
        if interface.get("developerName") != expected_identity["displayName"]:
            errors.append("Codex developer name mismatch")
        if interface.get("privacyPolicyURL") != policies.get("privacy"):
            errors.append("Codex privacy URL mismatch")
        if interface.get("termsOfServiceURL") != policies.get("terms"):
            errors.append("Codex terms URL mismatch")

    codex_marketplace = read_json(root / ".agents" / "plugins" / "marketplace.json", errors)
    codex_entries = codex_marketplace.get("plugins")
    if codex_marketplace.get("interface") != {"displayName": "Openly Useful"}:
        errors.append("Codex marketplace publisher mismatch")
    if not isinstance(codex_entries, list) or len(codex_entries) != 1:
        errors.append("Codex marketplace must contain exactly one plugin")
    else:
        entry = codex_entries[0]
        if entry.get("name") != component.get("name") or entry.get("source") != {"source": "local", "path": "./"}:
            errors.append("Codex marketplace root source mismatch")
        if entry.get("policy") != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
            errors.append("Codex marketplace policy mismatch")

    claude_marketplace = read_json(root / ".claude-plugin" / "marketplace.json", errors)
    claude_entries = claude_marketplace.get("plugins")
    if claude_marketplace.get("owner") != author or claude_marketplace.get("version") != component.get("version"):
        errors.append("Claude marketplace publisher/version mismatch")
    if not isinstance(claude_entries, list) or len(claude_entries) != 1:
        errors.append("Claude marketplace must contain exactly one plugin")
    else:
        entry = claude_entries[0]
        if entry.get("name") != component.get("name") or entry.get("source") != "./" or entry.get("strict") is not True:
            errors.append("Claude marketplace root source mismatch")
        if entry.get("author") != author or entry.get("version") != component.get("version"):
            errors.append("Claude marketplace component metadata mismatch")
    return errors


def main() -> int:
    errors = validate_registration()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Validated canonical skill plus Codex, Claude, marketplace, and publisher registration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
