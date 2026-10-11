"""FastAPI entry point for the local AI data operations agent MVP."""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from database import DEMO_DATA_VERSION, seed_demo_data
from executor import QueryError, SQLiteExecutor
from policy import SecurityPolicy
from semantic import SemanticRegistry

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "demo.sqlite"
REGISTRY = SemanticRegistry.default()
RUNS: dict[str, dict[str, Any]] = {}


class AnalyzeRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    question: str | None = Field(default=None, min_length=1)
    dataset: str = "demo_ecommerce"
    filters: dict[str, Any] = Field(default_factory=dict)
    simulate: bool = True

    @model_validator(mode="after")
    def normalize_query(self) -> "AnalyzeRequest":
        if not self.query and not self.question:
            raise ValueError("query 或 question 至少填写一个")
        if not self.query:
            self.query = self.question
        return self


class AnalyzeResponse(BaseModel):
    run_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        seed_demo_data(conn, reset=True)
    finally:
        conn.close()


def _time_range(question: str) -> tuple[str, str, list[str]]:
    if m := re.search(r"(20\d{2})年(\d{1,2})月", question):
        year, month = int(m.group(1)), int(m.group(2))
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year + (month == 12):04d}-{1 if month == 12 else month + 1:02d}-01"
        return start, end, []
    if "最近三个月" in question or "近三个月" in question:
        return "2026-07-01", "2026-10-01", []
    if "最近一个月" in question or "上个月" in question:
        return "2026-09-01", "2026-10-01", []
    return "2026-07-01", "2026-10-01", ["未指定时间范围，演示模式使用 2026-07 至 2026-09"]


def parse_intent(question: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    q = question.strip()
    start, end, warnings = _time_range(q)
    dimensions: list[str] = []
    if any(x in q for x in ("月", "月份", "趋势", "最近")):
        dimensions.append("month")
    for name, terms in (("channel", ("渠道",)), ("city", ("城市", "地区")), ("device_type", ("设备",)), ("category", ("品类", "商品分类"))):
        if any(x in q for x in terms):
            dimensions.append(name)
    matched: list[str] = []
    lowered = q.lower()
    for metric in REGISTRY.metrics.values():
        if any(alias.lower() in lowered for alias in (metric.name, *metric.aliases)):
            matched.append(metric.name)
    if not matched and any(x in q for x in ("销售", "成交", "gmv")):
        matched = ["revenue"]
    if not matched and "转化" in q:
        matched = ["conversion_rate"]
    if not matched and any(x in q for x in ("订单", "下单")):
        matched = ["orders"]
    clarification = None
    if "转化率" in q and not re.search(r"(注册|活跃|加购).{0,8}(支付|下单)|\d+\s*天", q):
        clarification = "请指定转化起点、终点和时间窗口，例如“注册后 7 天支付转化率”。"
    if not matched:
        clarification = clarification or "暂未匹配到已发布指标，请指定销售额、订单数、活跃用户、付费率等指标。"
    return {"question": q, "time": {"start": start, "end": end, "timezone": "Asia/Shanghai"}, "metrics": matched, "dimensions": dimensions or ["all"], "filters": filters or {}, "warnings": warnings, "need_clarification": clarification is not None, "clarification_question": clarification}


DIM_SQL = {"month": "strftime('%Y-%m', u.register_time)", "channel": "u.channel", "city": "u.city", "device_type": "u.device_type", "category": "p.category"}


def _projection(dimensions: list[str], alias: str = "u") -> tuple[list[str], list[str]]:
    names = [d for d in dimensions if d != "all"]
    if not names:
        return ["1 AS _key"], ["1"]
    expressions = []
    keys = []
    for name in names:
        expression = DIM_SQL[name].replace("u.", f"{alias}.")
        expressions.append(f"{expression} AS {name}")
        keys.append(expression)
    return expressions, keys


def generate_sql(intent: dict[str, Any]) -> str:
    metrics, dimensions = intent["metrics"], intent["dimensions"]
    dim_names = [d for d in dimensions if d != "all"]
    projection, keys = _projection(dimensions)
    group = ", ".join(keys) if dim_names else "1"
    ctes: list[str] = [f"spine AS (SELECT DISTINCT {', '.join(projection)} FROM users u LEFT JOIN products p ON 1=1 WHERE u.register_time >= :start AND u.register_time < :end)"]
    aliases: list[str] = []
    definitions = {
        "active_users": ("user_events e JOIN users u ON u.user_id=e.user_id", "e.event_time", "e.event_type='active'", "COUNT(DISTINCT e.user_id)"),
        "paid_users": ("orders o JOIN users u ON u.user_id=o.user_id", "o.order_time", "o.status='paid'", "COUNT(DISTINCT o.user_id)"),
        "orders": ("orders o JOIN users u ON u.user_id=o.user_id", "o.order_time", "o.status='paid'", "COUNT(DISTINCT o.order_id)"),
        "revenue": ("orders o JOIN users u ON u.user_id=o.user_id LEFT JOIN products p ON p.product_id=o.product_id", "o.order_time", "o.status='paid'", "COALESCE(SUM(o.amount),0)"),
    }
    for metric in metrics:
        if metric in {"pay_rate", "aov", "repeat_users", "repeat_rate", "conversion_rate"}:
            continue
        source, time_field, predicate, expression = definitions.get(metric, definitions["revenue"])
        cte = f"m_{metric}"
        ctes.append(f"{cte} AS (SELECT {', '.join(_projection(dimensions)[0])}, {expression} AS {metric} FROM {source} WHERE {time_field} >= :start AND {time_field} < :end AND {predicate} GROUP BY {group})")
        aliases.append(cte)
    if "pay_rate" in metrics:
        for metric in ("active_users", "paid_users"):
            if f"m_{metric}" not in aliases:
                source, time_field, predicate, expression = definitions[metric]
                cte = f"m_{metric}"
                ctes.append(f"{cte} AS (SELECT {', '.join(_projection(dimensions)[0])}, {expression} AS {metric} FROM {source} WHERE {time_field} >= :start AND {time_field} < :end AND {predicate} GROUP BY {group})")
                aliases.append(cte)
    if "aov" in metrics and "m_orders" not in aliases:
        source, time_field, predicate, expression = definitions["orders"]
        ctes.append(f"m_orders AS (SELECT {', '.join(_projection(dimensions)[0])}, {expression} AS orders FROM {source} WHERE {time_field} >= :start AND {time_field} < :end AND {predicate} GROUP BY {group})")
        aliases.append("m_orders")
    joins = []
    for alias in aliases:
        condition = " AND ".join(f"s.{d}={alias}.{d}" for d in dim_names) if dim_names else "s._key=1"
        joins.append(f"LEFT JOIN {alias} ON {condition}")
    selected = [f"s.{d}" for d in dim_names] if dim_names else ["s._key"]
    for metric in metrics:
        if metric == "pay_rate":
            selected.append("CAST(COALESCE(m_paid_users.paid_users,0) AS REAL)/NULLIF(m_active_users.active_users,0) AS pay_rate")
        elif metric == "aov":
            selected.append("CAST(COALESCE(m_revenue.revenue,0) AS REAL)/NULLIF(m_orders.orders,0) AS aov")
        elif metric in {"repeat_users", "repeat_rate", "conversion_rate"}:
            selected.append(f"NULL AS {metric}")
        else:
            selected.append(f"COALESCE(m_{metric}.{metric},0) AS {metric}")
    order = ", ".join(f"s.{d}" for d in dim_names) if dim_names else "1"
    return "WITH " + ", ".join(ctes) + " SELECT " + ", ".join(selected) + " FROM spine s " + " ".join(joins) + f" ORDER BY {order} LIMIT 1000"


def quality_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues = []
    if not rows:
        issues.append({"code": "EMPTY_RESULT", "severity": "warning", "message": "查询没有返回数据"})
    for row in rows:
        for key, value in row.items():
            if key.endswith("rate") and value is not None and not 0 <= value <= 1:
                issues.append({"code": "RATIO_OUT_OF_RANGE", "severity": "error", "message": f"{key} 超出 0–100%"})
    return {"status": "fail" if any(x["severity"] == "error" for x in issues) else ("warning" if issues else "pass"), "reliability": "low" if issues else "high", "issues": issues, "manual_review_required": bool(issues)}


def _run(request: AnalyzeRequest) -> dict[str, Any]:
    ensure_database()
    intent = parse_intent(request.query or request.question or "", request.filters)
    matches = [{"name": name, "definition": REGISTRY.metrics[name].definition, "formula": REGISTRY.metrics[name].formula, "version": REGISTRY.metrics[name].version} for name in intent["metrics"] if name in REGISTRY.metrics]
    if intent["need_clarification"]:
        return {"intent": intent, "semantic_matches": matches, "next_action": "clarify", "clarification_question": intent["clarification_question"], "data_version": DEMO_DATA_VERSION}
    sql = generate_sql(intent)
    allowed = {"users", "user_events", "orders", "products", "spine"} | {f"m_{m}" for m in intent["metrics"]} | {"m_active_users", "m_paid_users", "m_orders"}
    policy = SecurityPolicy.create(allowed_tables=allowed, required_time_columns=("register_time", "event_time", "order_time"), max_rows=1000, timeout_ms=5000)
    executor = SQLiteExecutor(str(DB_PATH), policy)
    try:
        result = executor.execute(sql, {"start": intent["time"]["start"], "end": intent["time"]["end"]})
    except QueryError as exc:
        return {"intent": intent, "semantic_matches": matches, "sql": sql, "security": {"safe": False, "blocked_reason": exc.message, "code": exc.code}, "next_action": "review", "error": exc.message}
    finally:
        executor.close()
    quality = quality_check(result.rows)
    report = {"question": intent["question"], "facts": [{"text": f"返回 {result.row_count} 行结果，覆盖 {intent['time']['start']} 至 {intent['time']['end']}。", "evidence_id": "data.row_count"}], "hypotheses": ["当前数据只能描述变化，不能单独证明因果原因。"], "recommendations": ["结合质量提示按渠道、城市或设备继续下钻验证。"], "quality": quality, "sql": sql, "data_version": DEMO_DATA_VERSION}
    return {"intent": intent, "semantic_matches": matches, "query_plan": {"dimensions": intent["dimensions"], "metrics": intent["metrics"]}, "sql": sql, "security": {"safe": True, "policy_version": "mvp-1"}, "data": {"columns": result.columns, "rows": result.rows, "row_count": result.row_count, "elapsed_ms": result.elapsed_ms, "truncated": result.truncated}, "quality": quality, "report": report, "next_action": "done", "data_version": DEMO_DATA_VERSION}


def create_app() -> FastAPI:
    api = FastAPI(title="AI Data Operations Agent", version="1.0.0")

    @api.on_event("startup")
    def startup() -> None:
        ensure_database()

    @api.post("/api/v1/analyze", response_model=AnalyzeResponse, status_code=202)
    def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            result = _run(request)
            record = {"run_id": run_id, "status": "completed", "created_at": now, "updated_at": now, "result": result, "error": result.get("error")}
        except Exception as exc:
            record = {"run_id": run_id, "status": "failed", "created_at": now, "updated_at": now, "result": None, "error": str(exc)}
        RUNS[run_id] = record
        return AnalyzeResponse(run_id=run_id, status=record["status"], result=record["result"], error=record["error"])

    @api.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        if run_id not in RUNS:
            raise HTTPException(status_code=404, detail="run not found")
        return RUNS[run_id]

    @api.get("/api/v1/metrics")
    def metrics() -> dict[str, Any]:
        context = REGISTRY.to_context()
        return {"version": REGISTRY.version, "metrics": context["metrics"], "dimensions": context["dimensions"]}

    return api


app = create_app()
