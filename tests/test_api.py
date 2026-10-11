import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_analyze_and_get_run():
    response = client.post("/api/v1/analyze", json={"query": "按月份分析销售额", "dataset": "sales"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert "SUM(sales_amount)" in body["result"]["sql"]
    fetched = client.get(f"/api/v1/runs/{body['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"

def test_missing_run():
    assert client.get("/api/v1/runs/missing").status_code == 404
