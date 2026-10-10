"""HAVING clause: parsing, semantic checks, IR shape, optimization and planning."""
from __future__ import annotations

from app.compiler.ast import nodes as ast
from app.compiler.cost.config import load_cost_config
from app.compiler.cost.statistics import load_statistics
from app.compiler.ir import nodes as ir
from app.compiler.ir.builder import build_ir
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.optimizer.engine import OptimizerEngine
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer

HAVING_SQL = (
    "SELECT s.dept_id, COUNT(s.id) AS total FROM students s "
    "GROUP BY s.dept_id HAVING COUNT(s.id) > 2"
)


def _analyze(sql: str, catalog):
    return SemanticAnalyzer(catalog).analyze(parse(tokenize(sql)))


def _build(sql: str, catalog) -> ir.IRNode:
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    return build_ir(query, catalog, semantic)


def _optimize(sql: str) -> ir.IRNode:
    stats = load_statistics()
    config = load_cost_config()
    catalog = stats.to_catalog()
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    root = build_ir(query, catalog, semantic)
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    return OptimizerEngine(stats, config, ctx).optimize(root).root


def _find(node: ir.IRNode, op_type):
    """Return the first node of the given type in pre-order, or None."""
    if isinstance(node, op_type):
        return node
    for child in node.children:
        found = _find(child, op_type)
        if found is not None:
            return found
    return None


def _plan_ops(node: dict) -> list[str]:
    ops = [node["op"]]
    for child in node["children"]:
        ops.extend(_plan_ops(child))
    return ops


# -- parsing -----------------------------------------------------------------
def test_parses_having_after_group_by():
    query = parse(tokenize(HAVING_SQL))
    assert query.group_by is not None
    assert isinstance(query.having, ast.Having)
    assert isinstance(query.having.condition, ast.Comparison)
    assert query.having.condition.left.name == "COUNT"


def test_having_without_group_by_parses():
    query = parse(tokenize("SELECT COUNT(*) FROM students s HAVING COUNT(*) > 1"))
    assert query.group_by is None
    assert query.having is not None


def test_having_serialized_in_query_dict():
    data = parse(tokenize(HAVING_SQL)).to_dict()
    assert data["having"]["kind"] == "Having"
    assert data["having"]["condition"]["kind"] == "Comparison"


def test_query_without_having_serializes_null():
    data = parse(tokenize("SELECT s.name FROM students s")).to_dict()
    assert data["having"] is None


# -- semantic analysis -------------------------------------------------------
def test_aggregate_in_having_is_valid(catalog):
    assert _analyze(HAVING_SQL, catalog).valid


def test_having_on_grouped_column_is_valid(catalog):
    result = _analyze(
        "SELECT s.dept_id FROM students s GROUP BY s.dept_id HAVING s.dept_id > 1",
        catalog,
    )
    assert result.valid, [e.code for e in result.errors]


def test_ungrouped_column_in_having_reports_sem018(catalog):
    result = _analyze(
        "SELECT s.dept_id FROM students s GROUP BY s.dept_id HAVING s.cgpa > 2",
        catalog,
    )
    assert any(e.code == "SEM018" for e in result.errors)


def test_ungrouped_column_in_having_without_group_by_reports_sem018(catalog):
    result = _analyze("SELECT COUNT(*) FROM students s HAVING s.cgpa > 2", catalog)
    assert any(e.code == "SEM018" for e in result.errors)


def test_ungrouped_select_column_with_having_aggregate_reports_sem016(catalog):
    result = _analyze("SELECT s.name FROM students s HAVING COUNT(*) > 1", catalog)
    assert any(e.code == "SEM016" for e in result.errors)


def test_unknown_column_inside_having_aggregate_is_reported(catalog):
    result = _analyze(
        "SELECT s.dept_id FROM students s GROUP BY s.dept_id HAVING COUNT(s.nope) > 1",
        catalog,
    )
    assert any(e.code == "SEM004" for e in result.errors)


# -- relational IR -----------------------------------------------------------
def test_having_lowers_to_filter_above_aggregate(catalog):
    root = _build(HAVING_SQL, catalog)
    assert isinstance(root, ir.Project)
    having = root.children[0]
    assert isinstance(having, ir.Filter)
    assert isinstance(having.children[0], ir.Aggregate)


def test_having_only_aggregate_is_collected(catalog):
    root = _build(
        "SELECT s.dept_id FROM students s GROUP BY s.dept_id HAVING COUNT(s.id) > 2",
        catalog,
    )
    aggregate = _find(root, ir.Aggregate)
    assert [f.name for f in aggregate.functions] == ["COUNT"]


def test_repeated_aggregate_is_computed_once(catalog):
    # COUNT(s.id) appears in both SELECT and HAVING.
    root = _build(HAVING_SQL, catalog)
    aggregate = _find(root, ir.Aggregate)
    assert len(aggregate.functions) == 1


# -- optimization ------------------------------------------------------------
def test_aggregate_predicate_stays_above_aggregate():
    root = _optimize(HAVING_SQL)
    having = _find(root, ir.Filter)
    assert isinstance(having.children[0], ir.Aggregate)
    # The aggregate reads the scan directly; nothing was pushed below it.
    assert isinstance(having.children[0].children[0], ir.Scan)


def test_grouping_key_predicate_moves_below_aggregate():
    root = _optimize(
        "SELECT s.dept_id, COUNT(s.id) FROM students s GROUP BY s.dept_id HAVING s.dept_id > 2"
    )
    aggregate = _find(root, ir.Aggregate)
    assert isinstance(aggregate.children[0], ir.Filter)
    assert isinstance(aggregate.children[0].children[0], ir.Scan)


# -- end-to-end planning -----------------------------------------------------
def test_having_query_plans_end_to_end(pipeline):
    result = pipeline.compile(HAVING_SQL)
    assert result["success"], result["semanticErrors"]
    ops = _plan_ops(result["selectedPlan"]["tree"])
    assert "Aggregate" in ops
    assert "Filter" in ops


def test_invalid_having_returns_no_plans(pipeline):
    result = pipeline.compile(
        "SELECT s.dept_id FROM students s GROUP BY s.dept_id HAVING s.cgpa > 2"
    )
    assert not result["success"]
    assert result["semanticErrors"][0]["code"] == "SEM018"
    assert result["candidatePlans"] == []
