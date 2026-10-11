"""Deterministic SQL policy for the demo read-only database."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover - fallback gives a useful policy result
    sqlglot = None
    exp = None


ALLOWED_TABLES = {"users", "user_events", "orders", "products"}
ALLOWED_FUNCTIONS = {"COUNT", "SUM", "COALESCE", "NULLIF", "CAST", "REAL", "STRFTIME", "ROUND", "AVG", "MAX", "MIN"}
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|attach|detach|pragma|replace|vacuum|create)\b", re.I)


@dataclass
class SQLValidationResult:
    safe: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_sql: str = ""
    policy_version: str = "mvp-1"


def validate_sql(sql: str, *, require_time_filter: bool = True, max_limit: int = 1000) -> SQLValidationResult:
    violations: list[str] = []
    text = (sql or "").strip()
    if not text:
        return SQLValidationResult(False, ["SQL 为空"])
    if ";" in text.rstrip(";"):
        violations.append("禁止多语句执行")
    if FORBIDDEN.search(text):
        violations.append("只允许只读查询，检测到写入或管理语句")
    if not re.match(r"^(with\b[\s\S]+select\b|select\b)", text, re.I):
        violations.append("SQL 必须以 SELECT 或 WITH ... SELECT 开始")
    if require_time_filter and not re.search(r"(register_time|event_time|order_time)\s*(between|>=|>|<=|<|=)", text, re.I):
        violations.append("查询必须包含时间范围条件")
    limit_match = re.search(r"\blimit\s+(\d+)", text, re.I)
    if limit_match and int(limit_match.group(1)) > max_limit:
        violations.append(f"LIMIT 不能超过 {max_limit}")
    if sqlglot:
        try:
            tree = sqlglot.parse_one(text, read="sqlite")
            if not isinstance(tree, (exp.Select, exp.Union, exp.With)) and not tree.find(exp.Select):
                violations.append("无法解析为查询语句")
            for table in tree.find_all(exp.Table):
                if table.name.lower() not in ALLOWED_TABLES:
                    violations.append(f"不允许访问表: {table.name}")
            for function in tree.find_all(exp.Func):
                name = function.sql_name().upper()
                if name not in ALLOWED_FUNCTIONS:
                    violations.append(f"不允许使用函数: {name}")
            normalized = tree.sql(dialect="sqlite")
        except Exception as exc:
            violations.append(f"SQL 解析失败: {exc}")
            normalized = text
    else:
        normalized = text
    return SQLValidationResult(not violations, violations, [], normalized)
