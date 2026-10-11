from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    register_time TEXT NOT NULL,
    channel TEXT NOT NULL,
    city TEXT NOT NULL,
    device_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    price NUMERIC NOT NULL CHECK (price >= 0)
);
CREATE TABLE IF NOT EXISTS user_events (
    event_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('active', 'add_to_cart', 'pay', 'login')),
    event_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    order_time TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('paid', 'cancelled', 'refunded')),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    refund_amount NUMERIC NOT NULL DEFAULT 0 CHECK (refund_amount >= 0)
);
CREATE INDEX IF NOT EXISTS idx_users_register_time ON users(register_time);
CREATE INDEX IF NOT EXISTS idx_events_time_type ON user_events(event_time, event_type);
CREATE INDEX IF NOT EXISTS idx_events_user ON user_events(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_time_status ON orders(order_time, status);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE TABLE IF NOT EXISTS metric_definitions (
    metric_name TEXT NOT NULL,
    version TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'published',
    owner TEXT NOT NULL DEFAULT 'data-ops',
    PRIMARY KEY(metric_name, version)
);
CREATE TABLE IF NOT EXISTS query_examples (
    example_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    golden_sql TEXT,
    metrics_json TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved'
);
CREATE TABLE IF NOT EXISTS query_runs (
    run_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    sql_text TEXT,
    elapsed_ms REAL,
    data_version TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_findings (
    finding_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES query_runs(run_id),
    rule_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    evidence_json TEXT,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY,
    run_id TEXT REFERENCES query_runs(run_id),
    feedback_type TEXT NOT NULL,
    suggestion TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS evaluation_cases (
    case_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    expected_intent_json TEXT NOT NULL,
    expected_sql TEXT,
    pass_criteria TEXT NOT NULL
);
"""


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the business tables and indexes in an open SQLite connection."""
    connection.executescript(SCHEMA_SQL)
    connection.commit()
