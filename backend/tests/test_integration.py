"""End-to-end integration tests over the full pipeline."""
from __future__ import annotations

from .conftest import EXAMPLE_SQL


def test_full_compile_bundle_shape(pipeline):
    result = pipeline.compile(EXAMPLE_SQL)
    assert result["success"]
    for key in (
        "query",
        "tokens",
        "ast",
        "semanticErrors",
        "relationalIR",
        "optimizedIR",
        "optimizationSteps",
        "candidatePlans",
        "selectedPlan",
        "costComparison",
        "explanation",
    ):
        assert key in result
    assert result["tokens"]
    assert result["ast"]["kind"] == "Query"
    assert result["semanticErrors"] == []
    assert result["selectedPlan"] is not None


def test_example_demonstrates_predicate_pushdown(pipeline):
    result = pipeline.compile(EXAMPLE_SQL)
    rules = {step["rule"] for step in result["optimizationSteps"]}
    assert "Predicate Pushdown" in rules
    # The original logical plan is a filter over a join.
    assert result["relationalIR"]["op"] == "Project"
    assert result["relationalIR"]["children"][0]["op"] == "Filter"
    assert result["relationalIR"]["children"][0]["children"][0]["op"] == "Join"


def test_example_explanation_mentions_selected_plan(pipeline):
    result = pipeline.compile(EXAMPLE_SQL)
    explanation = result["explanation"]
    assert explanation["planSelection"]["selectedPlan"] == result["selectedPlan"]["name"]
    assert "estimated cost" in explanation["planSelection"]["reason"].lower()
    assert explanation["optimizationExplanations"]


def test_row_reduction_reported(pipeline):
    result = pipeline.compile(EXAMPLE_SQL)
    pushdown = next(
        s for s in result["optimizationSteps"] if s["rule"] == "Predicate Pushdown"
    )
    impact = pushdown["estimatedImpact"]
    assert impact["estimatedRowsBefore"] >= impact["estimatedRowsAfter"]


def test_invalid_table_returns_semantic_error(pipeline):
    result = pipeline.compile("SELECT x.name FROM teachers x WHERE x.salary > 1")
    assert not result["success"]
    assert result["semanticErrors"]
    assert result["semanticErrors"][0]["code"] == "SEM002"
    assert result["candidatePlans"] == []


def test_lexer_error_is_reported(pipeline):
    result = pipeline.compile("SELECT @ FROM t")
    assert not result["success"]
    assert result["errors"]
    assert result["errors"][0]["stage"] == "lexer"


def test_parser_error_is_reported(pipeline):
    result = pipeline.compile("SELECT id WHERE id = 1")
    assert not result["success"]
    assert result["errors"]
    assert result["errors"][0]["stage"] == "parser"


def test_aggregate_query_end_to_end(pipeline):
    result = pipeline.compile(
        "SELECT s.dept_id, COUNT(s.id) AS total FROM students s GROUP BY s.dept_id"
    )
    assert result["success"]
    assert result["optimizedIR"] is not None


def test_aggregate_with_order_by_alias_end_to_end(pipeline):
    result = pipeline.compile(
        "SELECT s.dept_id, AVG(s.cgpa) AS avg_cgpa FROM students s "
        "GROUP BY s.dept_id ORDER BY avg_cgpa DESC"
    )
    assert result["success"], result["semanticErrors"]
    assert result["selectedPlan"] is not None


def test_three_way_join_end_to_end(pipeline):
    sql = (
        "SELECT s.name, c.title FROM students s "
        "INNER JOIN enrollments e ON s.id = e.student_id "
        "INNER JOIN courses c ON e.course_id = c.id "
        "WHERE s.cgpa > 9.0 AND c.credits = 4;"
    )
    result = pipeline.compile(sql)
    assert result["success"]
    assert len(result["candidatePlans"]) >= 6


def test_single_table_query_end_to_end(pipeline):
    result = pipeline.compile("SELECT s.name FROM students s WHERE s.city = 'Pune'")
    assert result["success"]
    assert result["selectedPlan"] is not None


def test_examples_endpoint_data(pipeline):
    from app.services.examples import get_examples

    examples = get_examples()
    assert any(e["id"] == "join_pushdown" for e in examples)
    for example in examples:
        # Every example must at least tokenize/parse without crashing the API.
        result = pipeline.compile(example["sql"])
        assert "success" in result


def test_left_join_returns_diagnostic_not_crash(pipeline):
    result = pipeline.compile(
        "SELECT s.name, d.name FROM students s "
        "LEFT JOIN departments d ON s.dept_id = d.id"
    )
    assert result["success"] is False
    assert result["semanticErrors"]
    assert result["semanticErrors"][0]["code"] == "SEM017"
    assert result["candidatePlans"] == []
    assert result["selectedPlan"] is None


def test_all_examples_compile_without_exception(pipeline):
    from app.services.examples import get_examples

    for example in get_examples():
        result = pipeline.compile(example["sql"])  # must not raise
        assert isinstance(result["success"], bool)


def test_distinct_end_to_end(pipeline):
    result = pipeline.compile(
        "SELECT DISTINCT s.city FROM students s WHERE s.cgpa > 8.0"
    )
    assert result["success"], result["semanticErrors"]
    ops: list[str] = []

    def collect(tree):
        ops.append(tree["op"])
        for child in tree["children"]:
            collect(child)

    for plan in result["candidatePlans"]:
        collect(plan["tree"])
    assert "Distinct" in ops
    # DISTINCT on city (50 distinct values) must reduce the estimated rows.
    assert result["selectedPlan"]["estimatedRows"] <= 50


def test_count_distinct_end_to_end(pipeline):
    result = pipeline.compile(
        "SELECT COUNT(DISTINCT s.city) AS cities FROM students s"
    )
    assert result["success"], result["semanticErrors"]
    assert result["selectedPlan"] is not None


def test_mixed_aggregate_without_group_by_returns_diagnostic(pipeline):
    result = pipeline.compile("SELECT s.name, COUNT(s.id) FROM students s")
    assert result["success"] is False
    assert result["semanticErrors"]
    assert result["semanticErrors"][0]["code"] == "SEM016"
    assert result["candidatePlans"] == []
