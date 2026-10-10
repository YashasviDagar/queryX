"""Compiler-style error hierarchy shared across all pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CompilerError:
    """A structured diagnostic.

    ``stage`` identifies the compiler phase that produced the error
    (lexer / parser / semantic), while ``code`` is a stable identifier such as
    ``LEX001`` that the frontend can reference in documentation.
    """

    code: str
    message: str
    stage: str
    line: int = 0
    column: int = 0
    suggestion: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "line": self.line,
            "column": self.column,
            "suggestion": self.suggestion,
            "location": {"line": self.line, "column": self.column},
        }


class LexError(Exception):
    """Raised when the lexer encounters an invalid character or literal."""

    def __init__(
        self,
        message: str,
        line: int,
        column: int,
        code: str = "LEX001",
        suggestion: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = CompilerError(
            code=code,
            message=message,
            stage="lexer",
            line=line,
            column=column,
            suggestion=suggestion,
        )


class ParseError(Exception):
    """Raised when the token stream violates the SQL grammar."""

    def __init__(
        self,
        message: str,
        line: int,
        column: int,
        code: str = "PAR001",
        suggestion: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = CompilerError(
            code=code,
            message=message,
            stage="parser",
            line=line,
            column=column,
            suggestion=suggestion,
        )
