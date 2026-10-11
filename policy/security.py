"""Defensive validation for user supplied analytics SQL.

The validator intentionally accepts a small, predictable SQL subset: one
read-only SELECT (or WITH ... SELECT) statement.  It performs lexical checks
before execution and is designed to be used alongside SQLite authorizer hooks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


class SecurityViolation(ValueError):
    """Raised when a query violates the configured security policy."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SecurityPolicy:
    allowed_tables: Optional[frozenset[str]] = None
    allowed_columns: Optional[frozenset[str]] = None
    required_time_columns: tuple[str, ...] = ()
    max_rows: int = 10_000
    timeout_ms: int = 5_000
    allow_aggregates: bool = True
    max_sql_length: int = 100_000

    @classmethod
    def create(cls, **kwargs) -> "SecurityPolicy":
        if "allowed_tables" in kwargs and kwargs["allowed_tables"] is not None:
            kwargs["allowed_tables"] = frozenset(x.lower() for x in kwargs["allowed_tables"])
        if "allowed_columns" in kwargs and kwargs["allowed_columns"] is not None:
            kwargs["allowed_columns"] = frozenset(x.lower() for x in kwargs["allowed_columns"])
        return cls(**kwargs)


_COMMENTS = re.compile(r"(?:--[^\n]*|/\*.*?\*/)", re.S)
_STRING = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"")
_IDENT = r"(?:[A-Za-z_][\w$]*|\"[^\"]+\")"
_FORBIDDEN = re.compile(r"\b(?:insert|update|delete|drop|alter|create|attach|detach|reindex|vacuum|replace|truncate|pragma|load_extension|recursive)\b", re.I)
_TABLE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)?)", re.I)


def _strip_literals_and_comments(sql: str) -> str:
    return _STRING.sub(" ", _COMMENTS.sub(" ", sql))


def validate_sql(sql: str, policy: SecurityPolicy = SecurityPolicy()) -> str:
    """Validate and normalize SQL, returning a semicolon-free query."""
    if not isinstance(sql, str) or not sql.strip():
        raise SecurityViolation("empty_query", "SQL query is empty")
    if len(sql) > policy.max_sql_length:
        raise SecurityViolation("query_too_long", "SQL query exceeds configured length")
    clean = _strip_literals_and_comments(sql).strip()
    # A trailing semicolon is harmless; any other statement separator is not.
    if ";" in clean.rstrip(";"):
        raise SecurityViolation("multiple_statements", "Only one SQL statement is allowed")
    normalized = sql.strip().rstrip(";").strip()
    tokenized = clean.lower()
    if not re.match(r"^(?:with\b[\s\S]*\bselect\b|select\b)", tokenized):
        raise SecurityViolation("read_only", "Only SELECT statements are permitted")
    if _FORBIDDEN.search(tokenized):
        raise SecurityViolation("forbidden_syntax", "Statement contains forbidden SQL syntax")
    if not policy.allow_aggregates and re.search(r"\b(?:sum|avg|count|min|max|group\s+by)\b", tokenized):
        raise SecurityViolation("aggregate_forbidden", "Aggregate queries are disabled")
    tables = {m.group(1).split(".")[-1].strip('"').lower() for m in _TABLE.finditer(clean)}
    if policy.allowed_tables is not None and not tables.issubset(policy.allowed_tables):
        raise SecurityViolation("table_forbidden", "Query references a table outside the allowlist")
    if policy.required_time_columns:
        if not any(re.search(rf"\b{re.escape(c)}\b", clean, re.I) for c in policy.required_time_columns):
            raise SecurityViolation("time_filter_required", "A time condition is required")
        if not re.search(r"\b(?:where|having)\b", clean, re.I):
            raise SecurityViolation("time_filter_required", "A WHERE or HAVING clause is required")
    if policy.allowed_columns is not None:
        # Conservative extraction of qualified identifiers; '*' remains allowed.
        refs = {m.group(1).lower() for m in re.finditer(r"\b([A-Za-z_][\w$]*)\b\s*(?:[<>=!]|\b(?:as|is|in|like)\b)", clean, re.I)}
        unknown = refs - policy.allowed_columns - {"select", "from", "where", "and", "or", "not", "null"}
        if unknown:
            raise SecurityViolation("column_forbidden", f"Query references disallowed columns: {sorted(unknown)}")
    return normalized
