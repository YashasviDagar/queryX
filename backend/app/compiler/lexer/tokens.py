"""Token definitions for the SmartSQL/queryX lexer.

Every token carries its type, the raw lexeme, and a 1-based line/column so that
downstream compiler stages can report precise source locations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TokenType(str, Enum):
    # --- Keywords -----------------------------------------------------------
    SELECT = "SELECT"
    FROM = "FROM"
    WHERE = "WHERE"
    JOIN = "JOIN"
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    OUTER = "OUTER"
    ON = "ON"
    GROUP = "GROUP"
    BY = "BY"
    ORDER = "ORDER"
    ASC = "ASC"
    DESC = "DESC"
    LIMIT = "LIMIT"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    AS = "AS"
    DISTINCT = "DISTINCT"

    # --- Literals / identifiers --------------------------------------------
    IDENTIFIER = "IDENTIFIER"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"

    # --- Arithmetic operators ----------------------------------------------
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"

    # --- Comparison operators ----------------------------------------------
    EQ = "EQ"
    NEQ = "NEQ"
    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"

    # --- Punctuation --------------------------------------------------------
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    DOT = "DOT"

    # --- End of input -------------------------------------------------------
    EOF = "EOF"


KEYWORDS: dict[str, TokenType] = {
    "SELECT": TokenType.SELECT,
    "FROM": TokenType.FROM,
    "WHERE": TokenType.WHERE,
    "JOIN": TokenType.JOIN,
    "INNER": TokenType.INNER,
    "LEFT": TokenType.LEFT,
    "RIGHT": TokenType.RIGHT,
    "OUTER": TokenType.OUTER,
    "ON": TokenType.ON,
    "GROUP": TokenType.GROUP,
    "BY": TokenType.BY,
    "ORDER": TokenType.ORDER,
    "ASC": TokenType.ASC,
    "DESC": TokenType.DESC,
    "LIMIT": TokenType.LIMIT,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
    "NOT": TokenType.NOT,
    "AS": TokenType.AS,
    "DISTINCT": TokenType.DISTINCT,
}

# Human-friendly category used by the UI to group tokens.
_CATEGORY: dict[TokenType, str] = {
    TokenType.SELECT: "keyword",
    TokenType.FROM: "keyword",
    TokenType.WHERE: "keyword",
    TokenType.JOIN: "keyword",
    TokenType.INNER: "keyword",
    TokenType.LEFT: "keyword",
    TokenType.RIGHT: "keyword",
    TokenType.OUTER: "keyword",
    TokenType.ON: "keyword",
    TokenType.GROUP: "keyword",
    TokenType.BY: "keyword",
    TokenType.ORDER: "keyword",
    TokenType.ASC: "keyword",
    TokenType.DESC: "keyword",
    TokenType.LIMIT: "keyword",
    TokenType.AND: "keyword",
    TokenType.OR: "keyword",
    TokenType.NOT: "keyword",
    TokenType.AS: "keyword",
    TokenType.DISTINCT: "keyword",
    TokenType.IDENTIFIER: "identifier",
    TokenType.INTEGER: "literal",
    TokenType.FLOAT: "literal",
    TokenType.STRING: "literal",
    TokenType.PLUS: "operator",
    TokenType.MINUS: "operator",
    TokenType.STAR: "operator",
    TokenType.SLASH: "operator",
    TokenType.PERCENT: "operator",
    TokenType.EQ: "comparison",
    TokenType.NEQ: "comparison",
    TokenType.LT: "comparison",
    TokenType.LTE: "comparison",
    TokenType.GT: "comparison",
    TokenType.GTE: "comparison",
    TokenType.LPAREN: "punctuation",
    TokenType.RPAREN: "punctuation",
    TokenType.COMMA: "punctuation",
    TokenType.SEMICOLON: "punctuation",
    TokenType.DOT: "punctuation",
    TokenType.EOF: "eof",
}


@dataclass
class Token:
    """A single lexical token produced by the lexer."""

    type: TokenType
    lexeme: str
    line: int
    column: int
    value: Optional[Any] = None

    @property
    def category(self) -> str:
        return _CATEGORY.get(self.type, "other")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "lexeme": self.lexeme,
            "line": self.line,
            "column": self.column,
            "value": self.value,
            "category": self.category,
        }


@dataclass
class TokenStream:
    """Convenience wrapper around a list of tokens."""

    tokens: list[Token] = field(default_factory=list)

    def to_list(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self.tokens]
