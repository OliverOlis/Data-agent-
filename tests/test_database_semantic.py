from database import create_demo_database
from semantic import GOLDEN_EXAMPLES, SemanticRegistry


def test_demo_database_has_schema_and_deterministic_rows():
    conn = create_demo_database()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "user_events", "orders", "products"} <= tables
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 24
    assert conn.execute("SELECT COUNT(*) FROM orders WHERE status='refunded'").fetchone()[0] == 2
    conn.close()


def test_registry_resolves_chinese_aliases_and_protects_context():
    registry = SemanticRegistry.default()
    assert registry.resolve_metric("销售额").name == "revenue"
    assert registry.resolve_metric("付费率").denominator == "active_users"
    assert registry.resolve_metric("转化率").null_policy == "clarify missing event/window"
    context = registry.to_context()
    assert context["version"] == "semantic-v1"
    assert any(m["name"] == "aov" for m in context["metrics"])


def test_golden_examples_are_reviewable_and_complete():
    assert len(GOLDEN_EXAMPLES) == 20
    assert all(item["question"] and item["metrics"] for item in GOLDEN_EXAMPLES)
    assert sum(item.get("clarification_required", False) for item in GOLDEN_EXAMPLES) == 1
