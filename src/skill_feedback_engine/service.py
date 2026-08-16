"""Domain workflows for observations, reviews, and sanitized exports."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

from .config import EnginePaths, atomic_write, initialize_paths, load_config, save_config
from .db import Database, new_id, utc_now
from .redaction import sanitize


KIND_TITLES = {
    "correction": "Address recurring correction",
    "pattern": "Capture reusable workflow pattern",
    "failure": "Prevent recurring failure",
    "outcome": "Preserve validated successful outcome",
}


class FeedbackEngine:
    def __init__(self, paths: EnginePaths):
        self.paths = paths
        initialize_paths(paths)
        self.config = load_config(paths)
        self.db = Database(paths.database)
        self.db.initialize()

    def target_for(self, identifier: str) -> Optional[Dict[str, Any]]:
        for target in self.config.get("targets", []):
            names = [target.get("skill", "")] + target.get("aliases", [])
            if identifier in names:
                return target
        return None

    def canonical_skill(self, identifier: str) -> str:
        target = self.target_for(identifier)
        return target["skill"] if target else identifier

    def map_target(
        self,
        *,
        skill: str,
        aliases: List[str],
        source_path: Optional[str],
        repository: Optional[str],
        repository_path: Optional[str],
        delivery: str,
    ) -> Dict[str, Any]:
        if delivery not in {"source-pr", "personal", "inbox"}:
            raise ValueError("delivery must be source-pr, personal, or inbox")
        target = {
            "skill": skill.strip(),
            "aliases": sorted(set(value.strip() for value in aliases if value.strip())),
            "source_path": source_path.strip() if source_path else None,
            "repository": repository.strip() if repository else None,
            "repository_path": repository_path.strip() if repository_path else None,
            "delivery": delivery,
        }
        if not target["skill"]:
            raise ValueError("skill must not be empty")
        targets = [
            value for value in self.config.get("targets", []) if value.get("skill") != target["skill"]
        ]
        targets.append(target)
        self.config["targets"] = sorted(targets, key=lambda value: value["skill"])
        save_config(self.paths, self.config)
        return target

    def observe(
        self,
        *,
        skill: str,
        kind: str,
        summary: str,
        evidence: Optional[str] = None,
        source: str = "manual",
        sensitivity: str = "private",
    ) -> Dict[str, Any]:
        if not skill.strip():
            raise ValueError("skill must not be empty")
        if kind not in KIND_TITLES:
            raise ValueError(f"unsupported observation kind: {kind}")
        safe_summary = sanitize(summary)
        if not safe_summary:
            raise ValueError("summary must not be empty")
        if sensitivity not in {"private", "shareable"}:
            raise ValueError("sensitivity must be private or shareable")
        return self.db.add_observation(
            skill=self.canonical_skill(skill.strip()),
            kind=kind,
            summary=safe_summary,
            evidence=evidence.strip() if evidence else None,
            source=source.strip() or "manual",
            sensitivity=sensitivity,
        )

    def review(self, *, full: bool = False, skill: Optional[str] = None) -> Dict[str, Any]:
        mode = "full" if full else "incremental"
        skill = self.canonical_skill(skill) if skill else None
        threshold = 1 if full else int(self.config["review"]["minimum_signals"])
        started_at = utc_now()
        review_id = new_id("review")
        created: List[Dict[str, Any]] = []
        updated: List[Dict[str, Any]] = []

        with self.db.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO review_runs
                    (id, mode, started_at, finished_at, observation_count, proposal_count)
                VALUES (?, ?, ?, ?, 0, 0)
                """,
                (review_id, mode, started_at, started_at),
            )
            query = "SELECT * FROM observations WHERE status = 'pending'"
            params: Tuple[Any, ...] = ()
            if skill:
                query += " AND skill = ?"
                params = (skill,)
            query += " ORDER BY created_at, id"
            observations = [dict(row) for row in connection.execute(query, params).fetchall()]

            groups: DefaultDict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            for observation in observations:
                groups[(observation["skill"], observation["kind"])].append(observation)

            for (target_skill, kind), group in groups.items():
                if len(group) < threshold:
                    continue
                new_summaries = list(dict.fromkeys(sanitize(item["summary"]) for item in group))
                new_observation_ids = [item["id"] for item in group]
                existing = connection.execute(
                    """
                    SELECT * FROM proposals
                    WHERE skill = ? AND kind = ? AND status IN ('draft', 'exported')
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (target_skill, kind),
                ).fetchone()
                existing_payload = json.loads(existing["public_payload_json"]) if existing else {}
                summaries = list(
                    dict.fromkeys(existing_payload.get("signals", []) + new_summaries)
                )
                observation_ids = list(
                    dict.fromkeys(
                        (json.loads(existing["observation_ids_json"]) if existing else [])
                        + new_observation_ids
                    )
                )
                title = f"{KIND_TITLES[kind]} in {target_skill}"
                rationale = (
                    f"{len(observation_ids)} {kind} signal{'s' if len(observation_ids) != 1 else ''} "
                    f"were captured for {target_skill}."
                )
                bullets = "\n".join(f"- {value}" for value in summaries)
                suggested_change = (
                    f"Review `{target_skill}` and express these observed requirements as one "
                    "concise, non-duplicative instruction:\n\n"
                    f"{bullets}\n\n"
                    "Keep the change scoped, preserve existing behavior, and validate it with a representative task."
                )
                confidence = min(0.95, 0.45 + 0.12 * len(observation_ids))
                proposal_id = existing["id"] if existing else new_id("prop")
                created_at = utc_now()
                public_payload = {
                    "schema_version": 1,
                    "proposal_id": proposal_id,
                    "skill": target_skill,
                    "kind": kind,
                    "title": title,
                    "rationale": rationale,
                    "suggested_change": suggested_change,
                    "confidence": confidence,
                    "observation_ids": observation_ids,
                    "signals": summaries,
                }
                target = self.target_for(target_skill)
                if target:
                    public_payload["delivery"] = {
                        "strategy": target.get("delivery", "inbox"),
                        "repository": target.get("repository"),
                        "path": target.get("repository_path"),
                    }
                values = (
                    created_at,
                    target_skill,
                    kind,
                    title,
                    rationale,
                    suggested_change,
                    confidence,
                    review_id,
                    json.dumps(observation_ids),
                    json.dumps(public_payload, sort_keys=True),
                )
                if existing:
                    connection.execute(
                        """
                        UPDATE proposals
                        SET updated_at = ?, skill = ?, kind = ?, title = ?, rationale = ?,
                            suggested_change = ?, confidence = ?, status = 'draft',
                            review_run_id = ?, observation_ids_json = ?, public_payload_json = ?
                        WHERE id = ?
                        """,
                        values + (proposal_id,),
                    )
                    updated.append(public_payload)
                else:
                    connection.execute(
                        """
                        INSERT INTO proposals
                            (id, created_at, updated_at, skill, kind, title, rationale,
                             suggested_change, confidence, review_run_id,
                             observation_ids_json, public_payload_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (proposal_id, created_at) + values,
                    )
                    created.append(public_payload)
                connection.executemany(
                    "UPDATE observations SET status = 'reviewed' WHERE id = ?",
                    [(observation_id,) for observation_id in new_observation_ids],
                )

            finished_at = utc_now()
            connection.execute(
                """
                UPDATE review_runs
                SET finished_at = ?, observation_count = ?, proposal_count = ?
                WHERE id = ?
                """,
                (finished_at, len(observations), len(created) + len(updated), review_id),
            )

        return {
            "id": review_id,
            "mode": mode,
            "observations_considered": len(observations),
            "proposals_created": len(created),
            "proposals_updated": len(updated),
            "proposals": created + updated,
        }

    def export_proposal(self, proposal_id: str, output: Optional[Path] = None) -> Dict[str, str]:
        proposal = self.db.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"proposal not found: {proposal_id}")
        directory = output.resolve() if output else self.paths.exports / proposal_id
        directory.mkdir(parents=True, exist_ok=True)
        payload = proposal["public_payload"]
        delivery = payload.get("delivery")
        delivery_markdown = ""
        if delivery:
            destination = delivery.get("repository") or "local patch inbox"
            repository_path = delivery.get("path")
            if repository_path:
                destination += f"/{repository_path}"
            delivery_markdown = (
                f"**Delivery:** `{delivery.get('strategy', 'inbox')}` to `{destination}`  \n"
            )
        markdown = (
            f"# {payload['title']}\n\n"
            f"**Target skill:** `{payload['skill']}`  \n"
            f"**Signal type:** `{payload['kind']}`  \n"
            f"{delivery_markdown}"
            f"**Confidence:** {payload['confidence']:.2f}\n\n"
            f"## Why this is proposed\n\n{payload['rationale']}\n\n"
            f"## Suggested change\n\n{payload['suggested_change']}\n\n"
            "## Evidence boundary\n\n"
            "The underlying evidence remains in the local Skill Feedback Engine database. "
            "Only sanitized summaries and observation identifiers are included here.\n\n"
            "## Validation checklist\n\n"
            "- [ ] Confirm the proposal matches the target skill's scope.\n"
            "- [ ] Inspect the exact diff before applying it.\n"
            "- [ ] Run the skill validator and a representative forward test.\n"
            "- [ ] Merge only after human approval.\n"
        )
        markdown_path = directory / "proposal.md"
        json_path = directory / "proposal.json"
        atomic_write(markdown_path, markdown)
        atomic_write(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        self.db.set_proposal_status(proposal_id, "exported")
        return {"markdown": str(markdown_path), "json": str(json_path)}
