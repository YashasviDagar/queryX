"""HTTP-layer tests for the REST routes (FastAPI TestClient)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import EXAMPLE_SQL


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("endpoint", ["/api/lex", "/api/parse", "/api/analyze", "/api/optimize", "/api/compile", "/api/plans"])
def test_post_endpoints_accept_valid_sql(client, endpoint):
    response = client.post(endpoint, json={"sql": EXAMPLE_SQL})
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.parametrize("endpoint", ["/api/lex", "/api/parse", "/api/analyze", "/api/optimize", "/api/plans"])
def test_post_endpoints_reject_missing_sql(client, endpoint):
    response = client.post(endpoint, json={})
    assert response.status_code == 422


def test_lex_returns_tokens(client):
    body = client.post("/api/lex", json={"sql": "SELECT id FROM students"}).json()
    assert body["tokens"]
    assert "SELECT" in str(body["tokens"][0]).upper()
    assert body["errors"] == []


def test_parse_returns_query_ast(client):
    body = client.post("/api/parse", json={"sql": "SELECT s.name FROM students s"}).json()
    assert body["ast"]["kind"] == "Query"


def test_analyze_reports_unknown_table(client):
    body = client.post("/api/analyze", json={"sql": "SELECT x.a FROM nope x"}).json()
    assert body["success"] is False
    assert body["semantic"]["valid"] is False
    assert body["semantic"]["errors"][0]["code"] == "SEM002"


def test_optimize_and_compile_return_same_bundle(client):
    optimize = client.post("/api/optimize", json={"sql": EXAMPLE_SQL}).json()
    compile_ = client.post("/api/compile", json={"sql": EXAMPLE_SQL}).json()
    assert optimize["selectedPlan"]["name"] == compile_["selectedPlan"]["name"]
    assert optimize["optimizationSteps"] == compile_["optimizationSteps"]


def test_plans_endpoint_returns_only_plan_fields(client):
    body = client.post("/api/plans", json={"sql": EXAMPLE_SQL}).json()
    assert set(body) == {
        "success",
        "errors",
        "semanticErrors",
        "candidatePlans",
        "selectedPlan",
        "costComparison",
        "explanation",
    }
    assert body["candidatePlans"]
    assert "selectedPlan" in body["explanation"]


def test_plans_endpoint_error_query_has_no_candidates(client):
    body = client.post("/api/plans", json={"sql": "SELECT x.a FROM nope x"}).json()
    assert body["success"] is False
    assert body["candidatePlans"] == []


def test_schema_endpoint(client):
    body = client.get("/api/schema").json()
    assert body["tables"]


def test_statistics_endpoint(client):
    body = client.get("/api/statistics").json()
    assert "tables" in body


def test_examples_endpoint(client):
    body = client.get("/api/examples").json()
    assert any(example["id"] == "join_pushdown" for example in body)


def test_seed_example_endpoint(client):
    body = client.get("/api/examples/seed").json()
    assert body["id"] == "join_pushdown"


def test_health_and_root(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").json()["name"] == "queryX"
