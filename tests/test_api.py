from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_analyze_and_get_run():
    response = client.post("/api/v1/analyze", json={"query": "最近三个月各渠道的销售额"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["security"]["safe"] is True
    assert "SUM(o.amount)" in body["result"]["sql"]
    assert body["result"]["data"]["row_count"] > 0
    assert body["result"]["report"]["facts"]
    fetched = client.get(f"/api/v1/runs/{body['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"


def test_ambiguous_conversion_requires_clarification():
    response = client.post("/api/v1/analyze", json={"question": "分析转化率"})
    assert response.status_code == 202
    result = response.json()["result"]
    assert result["next_action"] == "clarify"
    assert result["clarification_question"]


def test_missing_run():
    assert client.get("/api/v1/runs/missing").status_code == 404
