"""Relational IR construction tests."""
from __future__ import annotations

from app.compiler.ir import nodes as ir
from app.compiler.ir.builder import build_ir
from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer


def _build(sql: str, catalog) -> ir.IRNode:
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    return build_ir(query, catalog, semantic)


def test_join_query_ir_shape(catalog, example_sql):
    root = _build(example_sql, catalog)
    assert isinstance(root, ir.Project)
    child = root.children[0]
    assert isinstance(child, ir.Filter)
    join = child.children[0]
    assert isinstance(join, ir.Join)
    assert isinstance(join.left, ir.Scan)
    assert isinstance(join.right, ir.Scan)
    assert join.left.table == "students"
    assert join.right.table == "departments"


def test_single_table_filter_ir(catalog):
    root = _build("SELECT s.name FROM students s WHERE s.cgpa > 8.0", catalog)
    assert isinstance(root, ir.Project)
    assert isinstance(root.children[0], ir.Filter)
    assert isinstance(root.children[0].children[0], ir.Scan)


def test_aggregate_ir(catalog):
    root = _build(
        "SELECT s.dept_id, COUNT(s.id) FROM students s GROUP BY s.dept_id", catalog
    )
    project = root
    assert isinstance(project, ir.Project)
    aggregate = project.children[0]
    assert isinstance(aggregate, ir.Aggregate)
    assert len(aggregate.group_by) == 1
    assert aggregate.functions[0].name == "COUNT"


def test_sort_and_limit_ir(catalog):
    root = _build(
        "SELECT s.name FROM students s ORDER BY s.name ASC LIMIT 5", catalog
    )
    assert isinstance(root, ir.Limit)
    assert isinstance(root.children[0], ir.Sort)
    assert root.count == 5


def test_ir_to_dict_has_children(catalog, example_sql):
    root = _build(example_sql, catalog)
    data = root.to_dict()
    assert data["op"] == "Project"
    assert data["children"][0]["op"] == "Filter"
    assert data["children"][0]["children"][0]["op"] == "Join"


def test_distinct_ir_shape(catalog):
    root = _build("SELECT DISTINCT s.city FROM students s", catalog)
    assert isinstance(root, ir.Distinct)
    assert isinstance(root.children[0], ir.Project)
    assert isinstance(root.children[0].children[0], ir.Scan)


def test_distinct_before_sort_and_limit(catalog):
    root = _build(
        "SELECT DISTINCT s.city FROM students s ORDER BY s.city ASC LIMIT 5", catalog
    )
    assert isinstance(root, ir.Limit)
    assert isinstance(root.children[0], ir.Sort)
    assert isinstance(root.children[0].children[0], ir.Distinct)
