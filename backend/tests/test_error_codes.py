"""Diagnostic-code coverage for lexer, parser and semantic errors not hit elsewhere.

PAR001, SEM012 and SEM013 are not listed here: the parser rejects the SQL that
would reach them first (e.g. ``SELECT 1`` raises PAR002 before SEM012 can run,
and JOIN without ``ON`` is a parse error), so they are unreachable via SQL text.
"""
from __future__ import annotations

import pytest


def _codes(result: dict) -> list[str]:
    return [d["code"] for d in result.get("errors", []) + result.get("semanticErrors", [])]


@pytest.mark.parametrize(
    "sql, code",
    [
        ("SELECT s.name /* unterminated FROM students s", "LEX005"),
        ("SELECT 1", "PAR002"),
        ("SELECT s.name FROM students s WHERE (s.cgpa > 8", "PAR002"),
        ("SELECT s.name FROM students s WHERE s.cgpa > 8 extra junk", "PAR003"),
        ("SELECT FROM students s", "PAR005"),
        ("SELECT zzz FROM students s", "SEM005"),
        ("SELECT SUM(*) FROM students s", "SEM008"),
        ("SELECT SUM(s.name) FROM students s", "SEM009"),
        ("SELECT s.name FROM students s WHERE s.cgpa + 'x' > 1", "SEM011"),
        ("SELECT s.name FROM students s JOIN departments d ON s.dept_id", "SEM014"),
    ],
)
def test_diagnostic_code_is_emitted(pipeline, sql, code):
    result = pipeline.compile(sql)
    assert result["success"] is False
    assert code in _codes(result), _codes(result)
    assert result["candidatePlans"] == []
