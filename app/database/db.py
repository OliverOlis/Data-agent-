"""SQLite schema and deterministic demo data."""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "demo.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY, register_time TEXT NOT NULL, channel TEXT NOT NULL,
  city TEXT NOT NULL, device_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS user_events (
  event_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, event_type TEXT NOT NULL, event_time TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS orders (
  order_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, order_time TEXT NOT NULL, amount REAL NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('paid','cancelled','refunded')), product_id INTEGER NOT NULL,
  refund_amount REAL NOT NULL DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(user_id), FOREIGN KEY(product_id) REFERENCES products(product_id)
);
CREATE INDEX IF NOT EXISTS idx_users_register ON users(register_time);
CREATE INDEX IF NOT EXISTS idx_events_time ON user_events(event_time);
CREATE INDEX IF NOT EXISTS idx_orders_time_status ON orders(order_time, status);
"""


def initialize_database(path: str | Path = DEFAULT_DB_PATH) -> Path:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path


def seed_database(path: str | Path = DEFAULT_DB_PATH, *, seed: int = 7, user_count: int = 320) -> Path:
    db_path = initialize_database(path)
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    channels = ["自然流量", "信息流广告", "社交媒体", "联盟渠道"]
    cities = ["北京", "上海", "广州", "深圳", "杭州"]
    devices = ["iOS", "Android", "Web"]
    categories = [(1, "无线耳机", "数码", 299), (2, "保温杯", "家居", 89), (3, "跑鞋", "运动", 399), (4, "咖啡豆", "食品", 129)]
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM user_events")
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM products")
        conn.executemany("INSERT INTO products VALUES (?,?,?,?)", categories)
        users = []
        for user_id in range(1, user_count + 1):
            dt = start + timedelta(days=rng.randrange(270), hours=rng.randrange(24))
            users.append((user_id, dt.isoformat(), rng.choice(channels), rng.choice(cities), rng.choice(devices)))
        conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)
        events, orders = [], []
        event_id = order_id = 1
        for user_id, register_time, *_ in users:
            reg = datetime.fromisoformat(register_time)
            for _ in range(rng.randint(1, 5)):
                event_dt = reg + timedelta(days=rng.randrange(1, 75), hours=rng.randrange(24))
                events.append((event_id, user_id, rng.choice(["view", "add_to_cart", "login"]), event_dt.isoformat()))
                event_id += 1
            if rng.random() < 0.54:
                for _ in range(1 + (rng.random() < 0.17)):
                    order_dt = reg + timedelta(days=rng.randrange(2, 90), hours=rng.randrange(24))
                    product_id, _, _, price = rng.choice(categories)
                    status = "paid" if rng.random() < 0.87 else rng.choice(["cancelled", "refunded"])
                    amount = round(price * rng.uniform(.75, 1.25), 2)
                    refund = amount if status == "refunded" else 0
                    orders.append((order_id, user_id, order_dt.isoformat(), amount, status, product_id, refund))
                    order_id += 1
        conn.executemany("INSERT INTO user_events VALUES (?,?,?,?)", events)
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", orders)
        conn.commit()
    return db_path


def connect_readonly(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(path).resolve()
    if not db_path.exists():
        seed_database(db_path)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
