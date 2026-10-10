"""Optimizer rule tests."""
from __future__ import annotations

from app.compiler.cost.config import load_cost_config
from app.compiler.cost.statistics import load_statistics
from app.compiler.ir import nodes as ir
from app.compiler.ir.builder import build_ir
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.optimizer.engine import OptimizerEngine
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer


def _optimize(sql: str):
    stats = load_statistics()
    config = load_cost_config()
    catalog = stats.to_catalog()
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    root = build_ir(query, catalog, semantic)
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    return OptimizerEngine(stats, config, ctx).optimize(root)


def _scans(node: ir.IRNode) -> list[ir.Scan]:
    found: list[ir.Scan] = []
    if isinstance(node, ir.Scan):
        found.append(node)
    for child in node.children:
        found.extend(_scans(child))
    return found


def _has_op(node: ir.IRNode, op_type) -> bool:
    if isinstance(node, op_type):
        return True
    return any(_has_op(c, op_type) for c in node.children)


def test_predicate_pushdown_moves_filters_below_join(example_sql):
    result = _optimize(example_sql)
    root = result.root
    assert any(r.rule == "Predicate Pushdown" for r in result.records)
    # The top of the tree should no longer be a Filter directly over a Join.
    # Walk down to the join; each side should be a Filter over a Scan.
    node = root
    while not isinstance(node, ir.Join):
        node = node.children[0]
    assert isinstance(node.left, ir.Filter)
    assert isinstance(node.right, ir.Filter)
    assert isinstance(node.left.children[0], ir.Scan)
    assert isinstance(node.right.children[0], ir.Scan)


def test_constant_folding_applied():
    result = _optimize(
        "SELECT s.name FROM students s WHERE 2 + 3 < 10 AND s.cgpa > 7.5"
    )
    assert any(r.rule == "Constant Folding" for r in result.records)


def test_constant_false_filter_is_kept_but_folded():
    result = _optimize("SELECT s.name FROM students s WHERE 2 > 5")
    assert any(r.rule == "Constant Folding" for r in result.records)


def test_redundant_condition_removed():
    result = _optimize("SELECT s.name FROM students s WHERE s.cgpa > 8.0 AND s.cgpa > 8.0")
    assert any(r.rule == "Redundant Condition Removal" for r in result.records)


def test_projection_pruning_reduces_scan_columns():
    result = _optimize("SELECT s.name FROM students s WHERE s.cgpa > 8.0")
    assert any(r.rule == "Projection Pruning" for r in result.records)
    scan = next(s for s in _scans(result.root) if s.table == "students")
    assert scan.columns is not None
    assert set(scan.columns) == {"name", "cgpa"}


def test_join_reordering_records_step():
    sql = (
        "SELECT s.name, c.title FROM students s "
        "INNER JOIN enrollments e ON s.id = e.student_id "
        "INNER JOIN courses c ON e.course_id = c.id "
        "WHERE s.cgpa > 9.0"
    )
    result = _optimize(sql)
    assert any(r.rule == "Join Reordering" for r in result.records)


def test_records_have_required_fields(example_sql):
    result = _optimize(example_sql)
    assert result.records
    for record in result.records:
        data = record.to_dict()
        for key in ("rule", "before", "after", "reason", "estimatedImpact"):
            assert key in data
        impact = data["estimatedImpact"]
        assert "estimatedRowsBefore" in impact
        assert "estimatedRowsAfter" in impact
        assert "estimatedCostBefore" in impact


def test_optimization_does_not_mutate_original(example_sql):
    stats = load_statistics()
    config = load_cost_config()
    catalog = stats.to_catalog()
    query = parse(tokenize(example_sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    root = build_ir(query, catalog, semantic)
    before = root.to_dict()
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    OptimizerEngine(stats, config, ctx).optimize(root)
    assert root.to_dict() == before


def _find_join(node: ir.IRNode) -> ir.Join | None:
    if isinstance(node, ir.Join):
        return node
    for child in node.children:
        found = _find_join(child)
        if found is not None:
            return found
    return None


def test_or_predicate_across_tables_is_not_pushed_down():
    result = _optimize(
        "SELECT s.name, d.name FROM students s "
        "INNER JOIN departments d ON s.dept_id = d.id "
        "WHERE s.cgpa > 8.0 OR d.name = 'CSE'"
    )
    join = _find_join(result.root)
    assert join is not None
    # The OR references both inputs, so it must stay above the join
    # instead of being pushed into either side.
    assert isinstance(join.left, ir.Scan)
    assert isinstance(join.right, ir.Scan)


def test_three_way_join_reorder_preserves_all_relations():
    result = _optimize(
        "SELECT s.name, c.title FROM students s "
        "INNER JOIN enrollments e ON s.id = e.student_id "
        "INNER JOIN courses c ON e.course_id = c.id "
        "WHERE s.cgpa > 9.0"
    )
    tables = sorted(scan.table for scan in _scans(result.root))
    assert tables == ["courses", "enrollments", "students"]
    joins: list[ir.Join] = []

    def collect(node):
        if isinstance(node, ir.Join):
            joins.append(node)
        for child in node.children:
            collect(child)

    collect(result.root)
    assert len(joins) == 2


def test_rules_without_applicable_work_emit_no_records():
    result = _optimize("SELECT s.name FROM students s")
    rules = {record.rule for record in result.records}
    assert "Constant Folding" not in rules
    assert "Redundant Condition Removal" not in rules
    assert "Predicate Pushdown" not in rules


def test_distinct_preserved_and_pruned():
    result = _optimize("SELECT DISTINCT s.city FROM students s WHERE s.cgpa > 8.0")
    assert isinstance(result.root, ir.Distinct)
    assert _has_op(result.root, ir.Distinct)
    scan = next(s for s in _scans(result.root) if s.table == "students")
    assert scan.columns is not None
    assert set(scan.columns) == {"city", "cgpa"}
