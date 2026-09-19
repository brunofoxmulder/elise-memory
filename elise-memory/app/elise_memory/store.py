"""SQLite persistence for Élise Memory.

This module owns only the app's private database. It never writes to Home Assistant.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import MemoryCreate, MemoryRecord


class MemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='memories'"
            ).fetchone()
            if existing and "'conversation'" not in (existing[0] or ""):
                conn.executescript(
                    """
                    ALTER TABLE memories RENAME TO memories_legacy;
                    CREATE TABLE memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        kind TEXT NOT NULL CHECK(kind IN ('house', 'conversation', 'temporal')),
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        source TEXT NOT NULL,
                        valid_from TEXT,
                        valid_until TEXT,
                        created_at TEXT NOT NULL
                    );
                    INSERT INTO memories
                        (id, kind, key, value, source, valid_from, valid_until, created_at)
                    SELECT id, kind, key, value, source, valid_from, valid_until, created_at
                    FROM memories_legacy;
                    DROP TABLE memories_legacy;
                    """
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('house', 'conversation', 'temporal')),
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    valid_from TEXT,
                    valid_until TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_kind_key "
                "ON memories(kind, key)"
            )

    def search(
        self,
        query: str,
        *,
        kinds: tuple[str, ...] = ("house", "conversation"),
        limit: int = 6,
        at: datetime | None = None,
    ) -> list[MemoryRecord]:
        """Search active advisory memories without interpreting or executing them."""
        terms = [term for term in query.casefold().split() if len(term) >= 2]
        if not terms or not kinds:
            return []
        limit = max(1, min(limit, 20))
        clause = " OR ".join(
            "lower(key) LIKE ? OR lower(value) LIKE ?" for _ in terms
        )
        patterns = [f"%{term}%" for term in terms]
        params = [pattern for pattern in patterns for _ in range(2)]
        placeholders = ",".join("?" for _ in kinds)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT id, kind, key, value, source, valid_from,
                           valid_until, created_at
                    FROM memories
                    WHERE kind IN ({placeholders}) AND ({clause})
                    ORDER BY id DESC LIMIT ?""",
                (*kinds, *params, limit),
            ).fetchall()
        now = at or datetime.now(timezone.utc)
        return [
            record
            for row in rows
            if self._is_active(record := self._record(row), now)
        ]

    def add(self, item: MemoryCreate) -> MemoryRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories
                    (kind, key, value, source, valid_from, valid_until, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.kind,
                    item.key,
                    item.value,
                    item.source,
                    item.valid_from.isoformat() if item.valid_from else None,
                    item.valid_until.isoformat() if item.valid_until else None,
                    created_at,
                ),
            )
            row = conn.execute(
                """
                SELECT id, kind, key, value, source, valid_from,
                       valid_until, created_at
                FROM memories WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._record(row)

    def find(
        self,
        kind: str,
        key: str,
        *,
        at: datetime | None = None,
        include_inactive: bool = False,
    ) -> list[MemoryRecord]:
        """Return newest-first records, optionally restricted to temporal validity."""
        at = at or datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, kind, key, value, source, valid_from,
                       valid_until, created_at
                FROM memories
                WHERE kind = ? AND key = ?
                ORDER BY id DESC
                """,
                (kind, key),
            ).fetchall()

        records = [self._record(row) for row in rows]
        if include_inactive:
            return records
        return [record for record in records if self._is_active(record, at)]

    @staticmethod
    def _is_active(record: MemoryRecord, at: datetime) -> bool:
        if record.kind != "temporal":
            return True
        if record.valid_from and at < record.valid_from:
            return False
        if record.valid_until and at >= record.valid_until:
            return False
        return True

    @staticmethod
    def _record(row: tuple) -> MemoryRecord:
        return MemoryRecord(
            id=row[0],
            kind=row[1],
            key=row[2],
            value=row[3],
            source=row[4],
            valid_from=row[5],
            valid_until=row[6],
            created_at=row[7],
        )
