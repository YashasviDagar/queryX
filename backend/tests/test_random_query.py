"""Random query generator, used as a fuzzer for the whole pipeline."""
from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.random_query import random_query

FUZZ_SEEDS = range(40)


@pytest.mark.parametrize("seed", FUZZ_SEEDS)
def test_random_query_compiles_runs_and_all_plans_agree(pipeline, seed):
    query = random_query(pipeline.database, random.Random(seed))
    result = pipeline.compile(query["sql"])
    assert result["success"], (query["sql"], result["errors"] or result["semanticErrors"])
    codegen = result["codegen"]
    assert codegen["success"], (query["sql"], codegen.get("error"))
    statuses = {check["status"] for check in codegen["planChecks"]}
    assert not statuses & {"mismatch", "error"}, query["sql"]


def test_same_seed_gives_same_query(pipeline):
    first = random_query(pipeline.database, random.Random(7))
    second = random_query(pipeline.database, random.Random(7))
    assert first == second


def test_random_endpoint_returns_sql():
    with TestClient(app) as client:
        body = client.get("/api/random", params={"seed": 3}).json()
    assert body["sql"].startswith("SELECT")
    assert body["description"]


def test_where_on_left_join_nullable_side_is_planned(pipeline):
    # Found by the fuzzer: the filter on s stays above the LEFT join, and the
    # planner used to assume every filter in a join chain sits on a table scan.
    sql = (
        "SELECT d.name, s.name, e.grade FROM courses c "
        "INNER JOIN departments d ON c.dept_id = d.id "
        "LEFT JOIN students s ON s.dept_id = d.id "
        "INNER JOIN enrollments e ON e.course_id = c.id "
        "WHERE s.age <= 27;"
    )
    result = pipeline.compile(sql)
    assert result["success"]
    assert all(check["status"] in ("match", "skipped") for check in result["codegen"]["planChecks"])
