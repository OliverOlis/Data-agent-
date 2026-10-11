from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Union

from .schema import create_schema

DEMO_DATA_VERSION = "demo-ecommerce-2026.10.v1"


def seed_demo_data(connection: sqlite3.Connection, *, reset: bool = False) -> None:
    """Create a small deterministic dataset, including refund and missing-month cases."""
    create_schema(connection)
    if reset:
        connection.executescript("DELETE FROM user_events; DELETE FROM orders; DELETE FROM users; DELETE FROM products;")
    products = [(1, "保温杯", "家居", 59.0), (2, "运动鞋", "服饰", 299.0), (3, "耳机", "数码", 199.0), (4, "瑜伽垫", "运动", 129.0)]
    connection.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?)", products)
    channels = ("自然流量", "广告投放", "社交推荐")
    cities = ("上海", "北京", "深圳", "杭州")
    devices = ("mobile", "desktop", "tablet")
    users = []
    for i in range(1, 25):
        day = date(2026, 7, 1) + timedelta(days=(i * 3) % 92)
        users.append((i, f"{day.isoformat()}T08:00:00Z", channels[i % 3], cities[i % 4], devices[i % 3]))
    connection.executemany("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?)", users)
    events = []
    eid = 1
    for user_id, registered, *_ in users:
        d = registered[:10]
        events.append((eid, user_id, "active", f"{d}T09:00:00Z")); eid += 1
        if user_id % 3 != 0:
            events.append((eid, user_id, "add_to_cart", f"{d}T10:00:00Z")); eid += 1
        if user_id % 5 == 0:  # repeated event is useful for quality checks
            events.append((eid, user_id, "active", f"{d}T11:00:00Z")); eid += 1
    connection.executemany("INSERT OR IGNORE INTO user_events VALUES (?, ?, ?, ?)", events)
    orders = []
    oid = 1
    for user_id, registered, *_ in users:
        if user_id % 4 == 0:
            continue
        order_day = date.fromisoformat(registered[:10]) + timedelta(days=user_id % 12)
        status = "refunded" if user_id in (7, 14) else ("cancelled" if user_id in (9, 18) else "paid")
        amount = float(products[user_id % len(products)][3])
        refund = amount if status == "refunded" else 0.0
        orders.append((oid, user_id, f"{order_day.isoformat()}T12:00:00Z", amount, status, (user_id % 4) + 1, refund)); oid += 1
        if user_id in (2, 5, 11):
            orders.append((oid, user_id, f"{(order_day + timedelta(days=20)).isoformat()}T12:00:00Z", amount / 2, "paid", ((user_id + 1) % 4) + 1, 0.0)); oid += 1
    connection.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", orders)
    connection.commit()


def create_demo_database(target: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Return a connection containing schema and deterministic demo rows."""
    connection = sqlite3.connect(str(target))
    connection.row_factory = sqlite3.Row
    seed_demo_data(connection)
    return connection
