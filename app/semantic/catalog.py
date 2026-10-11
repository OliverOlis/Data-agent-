"""Small, explicit semantic catalog used by the MVP.

The catalog is deliberately code-readable and versioned. The SQL generator may
only use metric and dimension names exposed here.
"""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    aliases: tuple[str, ...]
    definition: str
    expression: str
    allowed_dimensions: tuple[str, ...]
    time_field: str
    unit: str = "number"


DIMENSIONS = {
    "month": "strftime('%Y-%m', users.register_time)",
    "channel": "users.channel",
    "city": "users.city",
    "device_type": "users.device_type",
    "category": "products.category",
}

METRICS: dict[str, Metric] = {
    "registered_users": Metric("registered_users", "注册用户数", ("用户数", "注册用户"), "时间范围内去重注册用户数", "COUNT(DISTINCT users.user_id)", tuple(DIMENSIONS), "users.register_time"),
    "active_users": Metric("active_users", "活跃用户数", ("活跃用户",), "时间范围内发生有效行为的去重用户数", "COUNT(DISTINCT user_events.user_id)", tuple(DIMENSIONS), "user_events.event_time"),
    "paid_users": Metric("paid_users", "付费用户数", ("付费用户",), "时间范围内存在已支付订单的去重用户数", "COUNT(DISTINCT CASE WHEN orders.status = 'paid' THEN orders.user_id END)", tuple(DIMENSIONS), "orders.order_time"),
    "orders": Metric("orders", "订单数", ("订单量",), "时间范围内已支付订单数", "COUNT(DISTINCT CASE WHEN orders.status = 'paid' THEN orders.order_id END)", tuple(DIMENSIONS), "orders.order_time"),
    "sales": Metric("sales", "销售额", ("GMV", "成交额", "营业额"), "已支付订单金额之和，币种为 CNY", "COALESCE(SUM(CASE WHEN orders.status = 'paid' THEN orders.amount ELSE 0 END), 0)", tuple(DIMENSIONS), "orders.order_time", "CNY"),
    "pay_rate": Metric("pay_rate", "付费率", ("支付率",), "付费用户数 / 活跃用户数，分母为 0 返回 NULL", "CAST(COUNT(DISTINCT CASE WHEN orders.status = 'paid' THEN orders.user_id END) AS REAL) / NULLIF(COUNT(DISTINCT user_events.user_id), 0)", tuple(DIMENSIONS), "user_events.event_time", "ratio"),
    "aov": Metric("aov", "客单价", ("平均订单金额",), "销售额 / 已支付订单数，分母为 0 返回 NULL", "COALESCE(SUM(CASE WHEN orders.status = 'paid' THEN orders.amount ELSE 0 END), 0) / NULLIF(COUNT(DISTINCT CASE WHEN orders.status = 'paid' THEN orders.order_id END), 0)", tuple(DIMENSIONS), "orders.order_time", "CNY"),
    "repeat_users": Metric("repeat_users", "复购用户数", ("复购人数",), "统计周期内已支付次数不少于 2 次的去重用户数", "COUNT(DISTINCT CASE WHEN paid_order_count >= 2 THEN user_id END)", tuple(DIMENSIONS), "orders.order_time"),
    "repeat_rate": Metric("repeat_rate", "复购率", ("复购用户率",), "复购用户数 / 付费用户数", "CAST(COUNT(DISTINCT CASE WHEN paid_order_count >= 2 THEN user_id END) AS REAL) / NULLIF(COUNT(DISTINCT user_id), 0)", tuple(DIMENSIONS), "orders.order_time", "ratio"),
}


def get_metric(name_or_alias: str) -> Metric | None:
    needle = name_or_alias.strip().lower()
    if needle in METRICS:
        return METRICS[needle]
    for metric in METRICS.values():
        if needle == metric.label.lower() or needle in {a.lower() for a in metric.aliases}:
            return metric
    return None


def list_metrics() -> list[Metric]:
    return list(METRICS.values())


def match_metrics(text: str) -> list[Metric]:
    lowered = text.lower()
    found: list[Metric] = []
    for metric in METRICS.values():
        words = (metric.name, metric.label, *metric.aliases)
        if any(word.lower() in lowered for word in words):
            found.append(metric)
    return found


EXAMPLE_QUERIES = [
    {"question": "最近三个月各渠道的销售额", "metrics": ["sales"], "dimensions": ["month", "channel"]},
    {"question": "比较不同设备类型的付费率", "metrics": ["pay_rate"], "dimensions": ["device_type"]},
    {"question": "找出活跃用户最多的渠道", "metrics": ["active_users"], "dimensions": ["channel"]},
]
