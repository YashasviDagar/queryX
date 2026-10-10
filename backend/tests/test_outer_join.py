"""LEFT JOIN support: semantics-preserving optimization and planning."""
from __future__ import annotations

from app.compiler.cost.cardinality import CardinalityEstimator
from app.compiler.ir import nodes as ir
from app.compiler.ir.builder import build_ir
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer
from app.compiler.cost.config import load_cost_config
from app.compiler.cost.statistics import load_statistics
from app.compiler.optimizer.engine import OptimizerEngine

LEFT_SQL = "SELECT s.name, d.name FROM students s LEFT JOIN departments d ON s.dept_id = d.id"


def _analyze(sql: str, catalog):
    return SemanticAnalyzer(catalog).analyze(parse(tokenize(sql)))


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
    if isinstance(node, op_type):
        return node
    for child in node.children:
        found = _find(child, op_type)
        if found is not None:
            return found
    return None


def _join_of(root: ir.IRNode) -> ir.Join:
    join = _find(root, ir.Join)
    assert join is not None
    return join


def _physical_nodes(node: dict) -> list[dict]:
    found = [node]
    for child in node["children"]:
        found.extend(_physical_nodes(child))
    return found


# -- semantics ---------------------------------------------------------------
def test_left_join_is_valid(catalog):
    result = _analyze(LEFT_SQL, catalog)
    assert result.valid, [e.code for e in result.errors]


def test_left_join_keeps_join_type_in_ir(catalog):
    query = parse(tokenize(LEFT_SQL))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    root = build_ir(query, catalog, semantic)
    assert _join_of(root).join_type == "LEFT"


# -- predicate placement -----------------------------------------------------
def test_left_side_predicate_moves_into_preserved_input():
    root = _optimize(LEFT_SQL + " WHERE s.cgpa > 8.0")
    join = _join_of(root)
    assert join.join_type == "LEFT"
    assert isinstance(join.left, ir.Filter)
    assert isinstance(join.left.children[0], ir.Scan)


def test_right_side_predicate_stays_above_outer_join():
    root = _optimize(LEFT_SQL + " WHERE d.name = 'CSE'")
    join = _join_of(root)
    # Moving it into the nullable side would keep students with no match.
    assert isinstance(join.right, ir.Scan)
    assert isinstance(_find(root, ir.Filter).children[0], ir.Join)


def test_predicate_across_both_sides_stays_above_outer_join():
    root = _optimize(LEFT_SQL + " WHERE s.cgpa > 8.0 OR d.name = 'CSE'")
    join = _join_of(root)
    assert isinstance(join.right, ir.Scan)
    assert isinstance(join.left, ir.Scan)
    assert join.condition is not None
    assert join.condition.operator == "="


def test_on_condition_is_not_changed_by_where_predicates():
    root = _optimize(LEFT_SQL + " WHERE d.name = 'CSE'")
    join = _join_of(root)
    assert join.condition.left.name == "dept_id"
    assert join.condition.right.name == "id"


# -- cardinality -------------------------------------------------------------
def test_left_join_rows_never_fall_below_left_input():
    stats = load_statistics()
    config = load_cost_config()
    estimator = CardinalityEstimator(stats, config, ExprContext({}, {}, {}))
    inner = estimator.join_rows(1000, 0.5, None, "INNER")
    outer = estimator.join_rows(1000, 0.5, None, "LEFT")
    assert outer == 1000
    assert outer >= inner


# -- planning ----------------------------------------------------------------
def test_left_join_plans_end_to_end(pipeline):
    result = pipeline.compile(LEFT_SQL)
    assert result["success"], result["semanticErrors"]
    assert result["candidatePlans"]
    for candidate in result["candidatePlans"]:
        joins = [n for n in _physical_nodes(candidate["tree"]) if n["details"].get("joinType") == "LEFT"]
        assert len(joins) == 1


def test_inner_join_above_left_join_keeps_all_relations(pipeline):
    sql = (
        "SELECT s.name, c.title FROM students s "
        "LEFT JOIN enrollments e ON s.id = e.student_id "
        "INNER JOIN courses c ON e.course_id = c.id "
        "WHERE s.cgpa > 9.0"
    )
    result = pipeline.compile(sql)
    assert result["success"], result["semanticErrors"]
    assert result["candidatePlans"]
    for candidate in result["candidatePlans"]:
        scans = sorted(
            n["details"]["table"]
            for n in _physical_nodes(candidate["tree"])
            if n["op"] in ("SeqScan", "IndexScan")
        )
        assert scans == ["courses", "enrollments", "students"]
        assert any(n["details"].get("joinType") == "LEFT" for n in _physical_nodes(candidate["tree"]))
