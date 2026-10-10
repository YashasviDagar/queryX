"""AST serialization tests."""
from __future__ import annotations

from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse

from .conftest import EXAMPLE_SQL


def test_ast_serializes_to_json_shape():
    query = parse(tokenize(EXAMPLE_SQL))
    data = query.to_dict()
    assert data["kind"] == "Query"
    assert data["select"]["kind"] == "Select"
    assert data["from"]["table"]["name"] == "students"
    assert data["from"]["table"]["alias"]["name"] == "s"
    assert len(data["joins"]) == 1
    assert data["joins"][0]["joinType"] == "INNER"
    assert data["where"]["condition"]["kind"] == "LogicalExpression"


def test_ast_nodes_have_positions():
    query = parse(tokenize(EXAMPLE_SQL))
    data = query.to_dict()
    assert data["line"] >= 1
    assert data["column"] >= 1
    column = data["select"]["columns"][0]
    assert column["kind"] == "Column"
    assert column["table"] == "s"
    assert column["name"] == "name"


def test_literal_types_serialized():
    query = parse(tokenize("SELECT a FROM t WHERE x = 8.0 AND y = 3 AND z = 'abc'"))
    condition = query.where.condition
    # left-most comparison is x = 8.0
    literal = condition.left.left.right.to_dict()
    assert literal["kind"] == "Literal"
    assert literal["literalType"] == "float"
