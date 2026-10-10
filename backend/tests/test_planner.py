"""Physical planner and selector tests."""
from __future__ import annotations


def test_multiple_candidates_generated(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    assert result["success"]
    assert len(result["candidatePlans"]) >= 3


def test_every_candidate_has_cost_and_rows(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    for plan in result["candidatePlans"]:
        assert plan["estimatedCost"] > 0
        assert plan["estimatedRows"] > 0
        assert "tree" in plan


def test_exactly_one_selected_plan(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    selected = [p for p in result["candidatePlans"] if p["selected"]]
    assert len(selected) == 1
    assert result["selectedPlan"]["id"] == selected[0]["id"]


def test_selected_plan_is_minimum_cost(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    costs = [p["estimatedCost"] for p in result["candidatePlans"]]
    assert result["selectedPlan"]["estimatedCost"] == min(costs)


def test_cost_comparison_sorted(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    comparison = result["costComparison"]
    assert comparison == sorted(comparison, key=lambda c: c["estimatedCost"])


def test_index_scan_candidate_exists(pipeline):
    result = pipeline.compile("SELECT s.name FROM students s WHERE s.cgpa > 8.0")
    assert result["success"]
    ops = []

    def collect(tree):
        ops.append(tree["op"])
        for child in tree["children"]:
            collect(child)

    for plan in result["candidatePlans"]:
        collect(plan["tree"])
    assert "IndexScan" in ops
    assert "SeqScan" in ops


def test_join_algorithms_present(pipeline, example_sql):
    result = pipeline.compile(example_sql)
    algorithms = {p["joinAlgorithm"] for p in result["candidatePlans"]}
    assert {"HashJoin", "NestedLoopJoin"}.issubset(algorithms)
