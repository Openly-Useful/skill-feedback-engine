"""SQLite persistence with atomic review transactions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    skill TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('correction', 'pattern', 'failure', 'outcome')),
    summary TEXT NOT NULL,
    evidence TEXT,
    source TEXT NOT NULL,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('private', 'shareable')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed')),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS observations_status_skill
ON observations(status, skill, created_at);

CREATE TABLE IF NOT EXISTS review_runs (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('incremental', 'full')),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    observation_count INTEGER NOT NULL,
    proposal_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    skill TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    suggested_change TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'accepted', 'rejected', 'exported')),
    review_run_id TEXT NOT NULL REFERENCES review_runs(id),
    observation_ids_json TEXT NOT NULL,
    public_payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS proposals_status_skill
ON proposals(status, skill, created_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Database:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add_observation(
        self,
        *,
        skill: str,
        kind: str,
        summary: str,
        evidence: Optional[str],
        source: str,
        sensitivity: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        observation_id = new_id("obs")
        created_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO observations
                    (id, created_at, skill, kind, summary, evidence, source, sensitivity, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    created_at,
                    skill,
                    kind,
                    summary,
                    evidence,
                    source,
                    sensitivity,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
        return {
            "id": observation_id,
            "created_at": created_at,
            "skill": skill,
            "kind": kind,
            "summary": summary,
            "source": source,
            "sensitivity": sensitivity,
            "status": "pending",
        }

    def counts(self) -> Dict[str, int]:
        with self.connection() as connection:
            observations = connection.execute(
                "SELECT status, COUNT(*) AS count FROM observations GROUP BY status"
            ).fetchall()
            proposals = connection.execute(
                "SELECT status, COUNT(*) AS count FROM proposals GROUP BY status"
            ).fetchall()
        result = {
            "observations_pending": 0,
            "observations_reviewed": 0,
            "observations_dismissed": 0,
            "proposals_draft": 0,
            "proposals_accepted": 0,
            "proposals_rejected": 0,
            "proposals_exported": 0,
        }
        for row in observations:
            result[f"observations_{row['status']}"] = row["count"]
        for row in proposals:
            result[f"proposals_{row['status']}"] = row["count"]
        return result

    def list_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM proposals"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC, id DESC"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._proposal_from_row(row) for row in rows]

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._proposal_from_row(row) if row else None

    def set_proposal_status(self, proposal_id: str, status: str) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE proposals SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), proposal_id),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["observation_ids"] = json.loads(value.pop("observation_ids_json"))
        value["public_payload"] = json.loads(value.pop("public_payload_json"))
        return value
