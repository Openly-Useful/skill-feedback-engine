"""Configuration and filesystem layout for local engine state."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": 1,
    "review": {
        "minimum_signals": 2,
    },
    "privacy": {
        "export_evidence": False,
    },
    "targets": [],
}


@dataclass(frozen=True)
class EnginePaths:
    home: Path
    database: Path
    config: Path
    exports: Path


def resolve_paths(explicit_home: Optional[str] = None) -> EnginePaths:
    configured = explicit_home or os.environ.get("SKILL_FEEDBACK_HOME")
    if configured:
        home = Path(configured).expanduser()
    else:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        home = data_home / "skill-feedback-engine"
    home = home.resolve()
    return EnginePaths(
        home=home,
        database=home / "feedback.sqlite3",
        config=home / "config.json",
        exports=home / "exports",
    )


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def initialize_paths(paths: EnginePaths) -> None:
    paths.home.mkdir(parents=True, exist_ok=True)
    paths.exports.mkdir(parents=True, exist_ok=True)
    if not paths.config.exists():
        atomic_write(paths.config, json.dumps(DEFAULT_CONFIG, indent=2) + "\n")


def load_config(paths: EnginePaths) -> Dict[str, Any]:
    initialize_paths(paths)
    try:
        value = json.loads(paths.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid configuration at {paths.config}: {exc}") from exc
    if value.get("schema_version") != 1:
        raise ValueError("Unsupported configuration schema_version; expected 1")
    minimum = value.get("review", {}).get("minimum_signals")
    if not isinstance(minimum, int) or minimum < 1:
        raise ValueError("review.minimum_signals must be an integer greater than zero")
    if value.get("privacy", {}).get("export_evidence") is not False:
        raise ValueError("privacy.export_evidence must remain false")
    if not isinstance(value.get("targets"), list):
        raise ValueError("targets must be a list")
    return value


def save_config(paths: EnginePaths, value: Dict[str, Any]) -> None:
    atomic_write(paths.config, json.dumps(value, indent=2, sort_keys=True) + "\n")
