"""SQLite persistence layer.

The store owns only Élise Memory data. It never writes to Home Assistant.
"""

import sqlite3
from pathlib import Path

from .models import MemoryCreate, MemoryRecord


class MemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('house', 'temporal')),
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    valid_from TEXT,
                    valid_until TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_kind_key "
                "ON memories(kind, key)"
            )

    def add(self, item: MemoryCreate) -> MemoryRecord:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories
                    (kind, key, value, source, valid_from, valid_until)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.kind,
                    item.key,
                    item.value,
                    item.source,
                    item.valid_from.isoformat() if item.valid_from else None,
                    item.valid_until.isoformat() if item.valid_until else None,
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

    def find(self, kind: str, key: str) -> list[MemoryRecord]:
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
        return [self._record(row) for row in rows]

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
