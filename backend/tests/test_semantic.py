"""Semantic analyzer tests."""
from __future__ import annotations

from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer


def _analyze(sql: str, catalog):
    query = parse(tokenize(sql))
    return SemanticAnalyzer(catalog).analyze(query)


def test_valid_query(catalog, example_sql):
    result = _analyze(example_sql, catalog)
    assert result.valid
    assert result.errors == []
    assert "students" in result.referenced_tables
    assert "departments" in result.referenced_tables


def test_unknown_table(catalog):
    result = _analyze("SELECT x.name FROM teachers x WHERE x.salary > 1", catalog)
    assert not result.valid
    assert any(e.code == "SEM002" for e in result.errors)


def test_unknown_column(catalog):
    result = _analyze("SELECT s.nope FROM students s", catalog)
    assert not result.valid
    assert any(e.code == "SEM004" for e in result.errors)


def test_ambiguous_column(catalog):
    result = _analyze(
        "SELECT name FROM students s INNER JOIN departments d ON s.dept_id = d.id",
        catalog,
    )
    assert not result.valid
    assert any(e.code == "SEM006" for e in result.errors)


def test_duplicate_alias(catalog):
    result = _analyze(
        "SELECT a.id FROM students a INNER JOIN departments a ON a.dept_id = a.id",
        catalog,
    )
    assert not result.valid
    assert any(e.code == "SEM001" for e in result.errors)


def test_aggregate_in_where(catalog):
    result = _analyze("SELECT s.id FROM students s WHERE COUNT(s.id) > 1", catalog)
    assert not result.valid
    assert any(e.code == "SEM015" for e in result.errors)


def test_nongrouped_column(catalog):
    result = _analyze(
        "SELECT s.dept_id, s.name, COUNT(s.id) FROM students s GROUP BY s.dept_id",
        catalog,
    )
    assert not result.valid
    assert any(e.code == "SEM016" for e in result.errors)


def test_grouped_aggregate_is_valid(catalog):
    result = _analyze(
        "SELECT s.dept_id, COUNT(s.id) FROM students s GROUP BY s.dept_id",
        catalog,
    )
    assert result.valid, [e.message for e in result.errors]


def test_aggregate_without_group_by_rejects_bare_column(catalog):
    result = _analyze("SELECT s.name, COUNT(s.id) FROM students s", catalog)
    assert not result.valid
    assert any(e.code == "SEM016" for e in result.errors)


def test_aggregate_only_without_group_by_is_valid(catalog):
    result = _analyze("SELECT COUNT(s.id), SUM(s.cgpa) FROM students s", catalog)
    assert result.valid, [e.message for e in result.errors]


def test_star_with_aggregate_rejected(catalog):
    result = _analyze("SELECT *, COUNT(s.id) FROM students s", catalog)
    assert not result.valid
    assert any(e.code == "SEM016" for e in result.errors)


def test_type_mismatch(catalog):
    result = _analyze("SELECT s.id FROM students s WHERE s.cgpa = 'high'", catalog)
    assert not result.valid
    assert any(e.code == "SEM010" for e in result.errors)


def test_unknown_function(catalog):
    result = _analyze("SELECT MEDIAN(s.cgpa) FROM students s", catalog)
    assert not result.valid
    assert any(e.code == "SEM007" for e in result.errors)


def test_errors_carry_location_and_suggestion(catalog):
    result = _analyze("SELECT s.nope FROM students s", catalog)
    error = next(e for e in result.errors if e.code == "SEM004")
    assert error.line >= 1
    assert error.suggestion is not None
    assert error.to_dict()["location"]["line"] == error.line


def test_order_by_select_alias_is_valid(catalog):
    result = _analyze(
        "SELECT s.dept_id, AVG(s.cgpa) AS avg_cgpa FROM students s "
        "GROUP BY s.dept_id ORDER BY avg_cgpa DESC",
        catalog,
    )
    assert result.valid, [e.message for e in result.errors]


def test_right_join_rejected(catalog):
    result = _analyze(
        "SELECT s.name, d.name FROM students s "
        "RIGHT JOIN departments d ON s.dept_id = d.id",
        catalog,
    )
    assert not result.valid
    assert any(e.code == "SEM017" for e in result.errors)
    error = next(e for e in result.errors if e.code == "SEM017")
    assert "not supported" in error.message
    assert error.suggestion is not None


def test_distinct_is_valid(catalog):
    result = _analyze("SELECT DISTINCT s.city FROM students s", catalog)
    assert result.valid, [e.message for e in result.errors]
