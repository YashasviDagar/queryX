"""Parser unit tests."""
from __future__ import annotations

import pytest

from app.compiler.ast import nodes as ast
from app.compiler.lexer.errors import ParseError
from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse


def _parse(sql: str) -> ast.Query:
    return parse(tokenize(sql))


def test_parse_select_from_where():
    query = _parse("SELECT id, name FROM students WHERE cgpa > 8.0")
    assert isinstance(query, ast.Query)
    assert query.select is not None
    assert len(query.select.columns) == 2
    assert query.from_clause.table.name == "students"
    assert isinstance(query.where.condition, ast.Comparison)
    assert query.where.condition.operator == ">"


def test_parse_join_with_alias():
    query = _parse(
        "SELECT s.name FROM students s INNER JOIN departments d ON s.dept_id = d.id"
    )
    assert query.from_clause.table.alias.name == "s"
    assert len(query.joins) == 1
    join = query.joins[0]
    assert join.join_type == "INNER"
    assert join.table.name == "departments"
    assert isinstance(join.condition, ast.Comparison)


def test_parse_group_order_limit():
    query = _parse(
        "SELECT dept_id, COUNT(id) FROM students GROUP BY dept_id ORDER BY dept_id DESC LIMIT 5"
    )
    assert query.group_by is not None and len(query.group_by.columns) == 1
    assert query.order_by.items[0].direction == "DESC"
    assert query.limit.count == 5


def test_parse_aggregate_functions():
    query = _parse("SELECT COUNT(*), SUM(cgpa), AVG(cgpa) FROM students")
    functions = [c for c in query.select.columns if isinstance(c, ast.FunctionCall)]
    assert [f.name for f in functions] == ["COUNT", "SUM", "AVG"]
    assert functions[0].star is True


def test_boolean_precedence_and_over_or():
    query = _parse("SELECT a FROM t WHERE x = 1 OR y = 2 AND z = 3")
    condition = query.where.condition
    assert isinstance(condition, ast.LogicalExpression)
    assert condition.operator == "OR"
    assert isinstance(condition.right, ast.LogicalExpression)
    assert condition.right.operator == "AND"


def test_arithmetic_precedence():
    query = _parse("SELECT a FROM t WHERE x = 1 + 2 * 3")
    comparison = query.where.condition
    assert isinstance(comparison.right, ast.BinaryExpression)
    assert comparison.right.operator == "+"
    assert isinstance(comparison.right.right, ast.BinaryExpression)
    assert comparison.right.right.operator == "*"


def test_alias_with_as():
    query = _parse("SELECT COUNT(id) AS total FROM students")
    column = query.select.columns[0]
    assert column.alias.name == "total"


def test_missing_from_raises():
    with pytest.raises(ParseError) as excinfo:
        _parse("SELECT id WHERE id = 1")
    assert excinfo.value.diagnostic.stage == "parser"


def test_join_without_on_raises():
    with pytest.raises(ParseError) as excinfo:
        _parse("SELECT a FROM t1 JOIN t2")
    assert excinfo.value.diagnostic.code == "PAR004"


def test_trailing_tokens_raise():
    with pytest.raises(ParseError):
        _parse("SELECT a FROM t extra tokens")
