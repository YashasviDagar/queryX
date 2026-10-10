"""Lexer unit tests."""
from __future__ import annotations

import pytest

from app.compiler.lexer.errors import LexError
from app.compiler.lexer.lexer import tokenize
from app.compiler.lexer.tokens import TokenType


def test_select_tokens_and_positions():
    tokens = tokenize("SELECT id FROM students")
    assert [t.type for t in tokens] == [
        TokenType.SELECT,
        TokenType.IDENTIFIER,
        TokenType.FROM,
        TokenType.IDENTIFIER,
        TokenType.EOF,
    ]
    assert tokens[0].line == 1 and tokens[0].column == 1
    assert tokens[1].lexeme == "id"
    assert tokens[1].column == 8


def test_keywords_are_case_insensitive():
    tokens = tokenize("select * from students where id = 1")
    assert tokens[0].type == TokenType.SELECT
    assert tokens[2].type == TokenType.FROM
    assert tokens[4].type == TokenType.WHERE


def test_numbers():
    tokens = tokenize("10 3.14 6.02e2")
    assert tokens[0].type == TokenType.INTEGER and tokens[0].value == 10
    assert tokens[1].type == TokenType.FLOAT and tokens[1].value == 3.14
    assert tokens[2].type == TokenType.FLOAT and tokens[2].value == pytest.approx(602.0)


def test_strings_with_escape():
    tokens = tokenize("'CSE' 'O''Brien'")
    assert tokens[0].type == TokenType.STRING and tokens[0].value == "CSE"
    assert tokens[1].value == "O'Brien"


def test_operators_and_comparisons():
    tokens = tokenize("a >= 1 AND b <> 2 OR c <= 3")
    types = [t.type for t in tokens]
    assert TokenType.GTE in types
    assert TokenType.NEQ in types
    assert TokenType.LTE in types
    assert TokenType.AND in types and TokenType.OR in types


def test_multiline_positions():
    tokens = tokenize("SELECT a\nFROM t")
    from_token = tokens[2]
    assert from_token.line == 2
    assert from_token.column == 1


def test_unexpected_character_raises():
    with pytest.raises(LexError) as excinfo:
        tokenize("SELECT @ FROM t")
    assert excinfo.value.diagnostic.code == "LEX002"
    assert excinfo.value.diagnostic.stage == "lexer"


def test_unterminated_string_raises():
    with pytest.raises(LexError) as excinfo:
        tokenize("SELECT 'abc FROM t")
    assert excinfo.value.diagnostic.code == "LEX004"


def test_comments_are_skipped():
    tokens = tokenize("SELECT a -- comment\nFROM t /* block */ WHERE a = 1")
    types = [t.type for t in tokens]
    assert types.count(TokenType.IDENTIFIER) == 3
    assert TokenType.WHERE in types
