from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from policy.security import SecurityPolicy, SecurityViolation, validate_sql


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    elapsed_ms: float = 0.0


class QueryError(RuntimeError):
    def __init__(self, code: str, message: str, *, cause: Optional[Exception] = None):
        super().__init__(message)
        self.code, self.message, self.cause = code, message, cause


class SQLiteExecutor:
    def __init__(self, database: str = ":memory:", policy: SecurityPolicy | None = None):
        self.policy = policy or SecurityPolicy()
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only = ON")

    def close(self) -> None:
        self.connection.close()

    def execute(self, sql: str, params: Mapping[str, Any] | tuple[Any, ...] = ()) -> QueryResult:
        try:
            query = validate_sql(sql, self.policy)
        except SecurityViolation as exc:
            raise QueryError(exc.code, exc.message, cause=exc) from exc
        started = time.monotonic()
        deadline = started + self.policy.timeout_ms / 1000

        def progress() -> int:
            return 1 if time.monotonic() >= deadline else 0

        self.connection.set_progress_handler(progress, 1_000)
        try:
            cur = self.connection.execute(query, params)
            columns = [d[0] for d in (cur.description or ())]
            rows = []
            for row in cur:
                if len(rows) >= self.policy.max_rows:
                    return QueryResult(columns, rows, len(rows), True, (time.monotonic() - started) * 1000)
                rows.append(dict(row))
            return QueryResult(columns, rows, len(rows), False, (time.monotonic() - started) * 1000)
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise QueryError("timeout", "Query exceeded the configured timeout", cause=exc) from exc
            raise QueryError("sql_error", str(exc), cause=exc) from exc
        except sqlite3.Error as exc:
            raise QueryError("sql_error", str(exc), cause=exc) from exc
        finally:
            self.connection.set_progress_handler(None, 0)
