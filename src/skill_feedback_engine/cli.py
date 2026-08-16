"""Command-line interface for Skill Feedback Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from . import __version__
from .config import resolve_paths
from .service import FeedbackEngine
from .validation import validate_skill


def emit(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}: {json.dumps(item, sort_keys=True)}")
            else:
                print(f"{key}: {item}")
    else:
        print(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-feedback",
        description="Observe work. Propose better skills.",
    )
    parser.add_argument("--home", help="Override SKILL_FEEDBACK_HOME")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize local state")
    init_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show local queue counts")
    status_parser.add_argument("--json", action="store_true")

    targets_parser = subparsers.add_parser("targets", help="List skill source mappings")
    targets_parser.add_argument("--json", action="store_true")

    map_parser = subparsers.add_parser("map-target", help="Map an alias to an owned skill source")
    map_parser.add_argument("--skill", required=True, help="Canonical SKILL.md name")
    map_parser.add_argument("--alias", action="append", default=[])
    map_parser.add_argument("--source-path", help="Private local path to the skill source")
    map_parser.add_argument("--repository", help="Public owner/repository identifier")
    map_parser.add_argument("--repository-path", help="Skill path inside the repository")
    map_parser.add_argument(
        "--delivery", choices=("source-pr", "personal", "inbox"), default="inbox"
    )
    map_parser.add_argument("--json", action="store_true")

    observe_parser = subparsers.add_parser("observe", help="Record a high-value feedback signal")
    observe_parser.add_argument("--skill", required=True, help="Target skill name or stable identifier")
    observe_parser.add_argument(
        "--kind",
        required=True,
        choices=("correction", "pattern", "failure", "outcome"),
    )
    observe_parser.add_argument("--summary", required=True, help="Concise reusable lesson")
    observe_parser.add_argument("--evidence", help="Private local evidence; never included in exports")
    observe_parser.add_argument("--source", default="manual")
    observe_parser.add_argument(
        "--sensitivity", choices=("private", "shareable"), default="private"
    )
    observe_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("review", help="Turn pending signals into draft proposals")
    review_parser.add_argument("--full", action="store_true", help="Include single-signal groups")
    review_parser.add_argument("--skill", help="Review one target skill")
    review_parser.add_argument("--json", action="store_true")

    proposals_parser = subparsers.add_parser("proposals", help="List review-gated proposals")
    proposals_parser.add_argument(
        "--status", choices=("draft", "accepted", "rejected", "exported")
    )
    proposals_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show one proposal")
    show_parser.add_argument("proposal_id")
    show_parser.add_argument("--json", action="store_true")

    export_parser = subparsers.add_parser("export", help="Create a sanitized PR-ready proposal bundle")
    export_parser.add_argument("proposal_id")
    export_parser.add_argument("--output", type=Path)
    export_parser.add_argument("--json", action="store_true")

    status_change_parser = subparsers.add_parser("set-status", help="Record a proposal decision")
    status_change_parser.add_argument("proposal_id")
    status_change_parser.add_argument("status", choices=("draft", "accepted", "rejected"))
    status_change_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate an Agent Skill folder")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "validate":
        result = validate_skill(args.path)
        emit(result, args.json)
        return 0 if result["valid"] else 1

    paths = resolve_paths(args.home)
    engine = FeedbackEngine(paths)

    if args.command == "init":
        emit(
            {
                "home": str(paths.home),
                "database": str(paths.database),
                "config": str(paths.config),
                "status": "ready",
            },
            args.json,
        )
        return 0
    if args.command == "status":
        result: Dict[str, Any] = {"home": str(paths.home)}
        result.update(engine.db.counts())
        emit(result, args.json)
        return 0
    if args.command == "targets":
        emit({"targets": engine.config.get("targets", [])}, args.json)
        return 0
    if args.command == "map-target":
        emit(
            engine.map_target(
                skill=args.skill,
                aliases=args.alias,
                source_path=args.source_path,
                repository=args.repository,
                repository_path=args.repository_path,
                delivery=args.delivery,
            ),
            args.json,
        )
        return 0
    if args.command == "observe":
        result = engine.observe(
            skill=args.skill,
            kind=args.kind,
            summary=args.summary,
            evidence=args.evidence,
            source=args.source,
            sensitivity=args.sensitivity,
        )
        emit(result, args.json)
        return 0
    if args.command == "review":
        emit(engine.review(full=args.full, skill=args.skill), args.json)
        return 0
    if args.command == "proposals":
        emit({"proposals": engine.db.list_proposals(args.status)}, args.json)
        return 0
    if args.command == "show":
        proposal = engine.db.get_proposal(args.proposal_id)
        if not proposal:
            raise ValueError(f"proposal not found: {args.proposal_id}")
        emit(proposal, args.json)
        return 0
    if args.command == "export":
        emit(engine.export_proposal(args.proposal_id, args.output), args.json)
        return 0
    if args.command == "set-status":
        if not engine.db.set_proposal_status(args.proposal_id, args.status):
            raise ValueError(f"proposal not found: {args.proposal_id}")
        emit({"proposal_id": args.proposal_id, "status": args.status}, args.json)
        return 0
    raise ValueError(f"unknown command: {args.command}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
