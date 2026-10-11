"""Bounded read-only SQLite execution."""

from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
import time
from typing import Any

from app.database.db import DEFAULT_DB_PATH, connect_readonly, seed_database


@dataclass
class QueryExecutionResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    elapsed_ms: float = 0
    error: str | None = None


def execute_readonly(sql: str, *, params: dict[str, Any] | None = None, db_path=DEFAULT_DB_PATH, max_rows: int = 1000, timeout_seconds: float = 10) -> QueryExecutionResult:
    seed_database(db_path)
    start = time.perf_counter()
    conn = connect_readonly(db_path)
    conn.set_progress_handler(lambda: 1 if (time.perf_counter() - start) > timeout_seconds else 0, 1000)
    try:
        cursor = conn.execute(sql, params or {})
        rows = [dict(row) for row in cursor.fetchmany(max_rows)]
        return QueryExecutionResult(True, [d[0] for d in cursor.description or []], rows, len(rows), (time.perf_counter() - start) * 1000)
    except sqlite3.OperationalError as exc:
        return QueryExecutionResult(False, elapsed_ms=(time.perf_counter() - start) * 1000, error=str(exc))
    finally:
        conn.close()
