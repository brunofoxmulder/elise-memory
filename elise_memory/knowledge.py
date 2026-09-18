"""Structured durable knowledge for Élise Memory.

Canonical knowledge and validated REX are stored separately from conversational
temporal memories. Google Drive and Home Assistant remain read-only sources.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

KnowledgeOrigin = Literal["canonical", "rex"]
KnowledgeStatus = Literal["current", "superseded", "inactive", "candidate", "validated", "rejected"]


class KnowledgeCreate(BaseModel):
    key: str = Field(min_length=1, max_length=300)
    object_type: str = Field(min_length=1, max_length=100)
    domain: str | None = Field(default=None, max_length=150)
    value: str = Field(min_length=1, max_length=20_000)
    origin: KnowledgeOrigin
    source_id: str = Field(min_length=1, max_length=500)
    source_locator: str | None = Field(default=None, max_length=1000)
    source_validated_at: datetime | None = None
    evidence: str | None = Field(default=None, max_length=5000)
    confidence: float | None = Field(default=None, ge=0, le=100)
    status: KnowledgeStatus = "current"


class KnowledgeStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    domain TEXT,
                    value TEXT NOT NULL,
                    origin TEXT NOT NULL CHECK(origin IN ('canonical','rex')),
                    source_id TEXT NOT NULL,
                    source_locator TEXT,
                    source_validated_at TEXT,
                    evidence TEXT,
                    confidence REAL,
                    status TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    superseded_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_current_source
                ON knowledge(origin, source_id, key)
                WHERE status IN ('current','validated','candidate');
                CREATE INDEX IF NOT EXISTS idx_knowledge_key_status
                ON knowledge(key, status);
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_key TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    object_key TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'current',
                    created_at TEXT NOT NULL,
                    UNIQUE(subject_key, relation, object_key, source_id)
                );
                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                """
            )

    def replace_current(self, item: KnowledgeCreate, content_hash: str) -> int | None:
        """Atomically replace one source fact; unchanged content creates no duplicate."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT id, content_hash FROM knowledge
                   WHERE origin=? AND source_id=? AND key=?
                   AND status IN ('current','validated','candidate')
                   ORDER BY id DESC LIMIT 1""",
                (item.origin, item.source_id, item.key),
            ).fetchone()
            if row and row[1] == content_hash:
                return None
            if row:
                conn.execute(
                    "UPDATE knowledge SET status='superseded', superseded_at=? WHERE id=?",
                    (now, row[0]),
                )
            cur = conn.execute(
                """INSERT INTO knowledge
                (key,object_type,domain,value,origin,source_id,source_locator,
                 source_validated_at,evidence,confidence,status,content_hash,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item.key, item.object_type, item.domain, item.value, item.origin,
                    item.source_id, item.source_locator,
                    item.source_validated_at.isoformat() if item.source_validated_at else None,
                    item.evidence, item.confidence, item.status, content_hash, now,
                ),
            )
            return int(cur.lastrowid)

    def active(self, key: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM knowledge WHERE key=?
                   AND status IN ('current','validated','candidate')
                   ORDER BY CASE origin WHEN 'canonical' THEN 0 ELSE 1 END, id DESC""",
                (key,),
            ).fetchall()
        return [dict(row) for row in rows]


    def apply_canonical_snapshot(
        self,
        compiled: list[tuple[KnowledgeCreate, str]],
        *,
        expected_min_ratio: float = 0.70,
        relations: list[dict] | None = None,
    ) -> dict:
        """Atomically publish a complete canonical snapshot.

        Empty or abnormally small snapshots are rejected. Existing canonical
        knowledge remains untouched on any validation or database error.
        REX rows are never modified by this operation.
        """
        if not compiled:
            raise ValueError("empty_canonical_snapshot")
        identities = [(x.source_id, x.key) for x, _ in compiled]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate_canonical_identity")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            current_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge WHERE origin='canonical' "
                "AND status='current'"
            ).fetchone()[0]
            if current_count and len(compiled) < current_count * expected_min_ratio:
                raise ValueError("canonical_snapshot_volume_drop")

            run = conn.execute(
                "INSERT INTO sync_runs(started_at,status,source_count,record_count) "
                "VALUES (?, 'running', 0, ?)",
                (now, len(compiled)),
            ).lastrowid
            seen = set()
            changed = 0
            for item, content_hash in compiled:
                identity = (item.source_id, item.key)
                seen.add(identity)
                row = conn.execute(
                    """SELECT id, content_hash FROM knowledge
                       WHERE origin='canonical' AND source_id=? AND key=?
                       AND status='current' ORDER BY id DESC LIMIT 1""",
                    identity,
                ).fetchone()
                if row and row[1] == content_hash:
                    continue
                if row:
                    conn.execute(
                        "UPDATE knowledge SET status='superseded', superseded_at=? WHERE id=?",
                        (now, row[0]),
                    )
                conn.execute(
                    """INSERT INTO knowledge
                    (key,object_type,domain,value,origin,source_id,source_locator,
                     source_validated_at,evidence,confidence,status,content_hash,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?, 'current', ?,?)""",
                    (
                        item.key,item.object_type,item.domain,item.value,'canonical',
                        item.source_id,item.source_locator,
                        item.source_validated_at.isoformat() if item.source_validated_at else None,
                        item.evidence,item.confidence,content_hash,now,
                    ),
                )
                changed += 1

            stale = conn.execute(
                """SELECT id, source_id, key FROM knowledge
                   WHERE origin='canonical' AND status='current'"""
            ).fetchall()
            deactivated = 0
            for row in stale:
                if (row[1], row[2]) not in seen:
                    conn.execute(
                        "UPDATE knowledge SET status='inactive', superseded_at=? WHERE id=?",
                        (now, row[0]),
                    )
                    deactivated += 1
            if relations is not None:
                relation_ids = [r["source_id"] for r in relations]
                if len(relation_ids) != len(set(relation_ids)):
                    raise ValueError("duplicate_canonical_relation")
                conn.execute(
                    "DELETE FROM knowledge_relations WHERE source_id LIKE 'index:relations:%'"
                )
                for relation in relations:
                    conn.execute(
                        """INSERT INTO knowledge_relations
                        (subject_key,relation,object_key,source_id,status,created_at)
                        VALUES (?,?,?,?, 'current', ?)""",
                        (relation["subject_key"], relation["relation"],
                         relation["object_key"], relation["source_id"], now),
                    )

            conn.execute(
                """UPDATE sync_runs SET completed_at=?, status='success',
                   source_count=?, record_count=? WHERE id=?""",
                (datetime.now(timezone.utc).isoformat(),
                 len({x.source_id.split(':',1)[0] for x,_ in compiled}),
                 len(compiled), run),
            )
        return {"records": len(compiled), "changed": changed, "deactivated": deactivated}


    def replace_canonical_relations(self, relations: list[dict]) -> None:
        """Replace the derived canonical relation view in one transaction."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM knowledge_relations WHERE source_id LIKE 'index:relations:%'")
            for relation in relations:
                conn.execute(
                    """INSERT INTO knowledge_relations
                    (subject_key,relation,object_key,source_id,status,created_at)
                    VALUES (?,?,?,?, 'current', ?)""",
                    (relation["subject_key"], relation["relation"],
                     relation["object_key"], relation["source_id"], now),
                )
