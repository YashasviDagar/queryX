"""Hand-written SQL lexer.

Scans a SQL source string into a stream of :class:`Token` objects. The lexer is
intentionally independent from any external SQL library so that the whole
compiler pipeline is implemented from first principles.
"""
from __future__ import annotations

from .errors import LexError
from .tokens import KEYWORDS, Token, TokenType

_WHITESPACE = " \t\r\n"
_IDENT_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_PART = _IDENT_START | set("0123456789")
_DIGITS = set("0123456789")

_TWO_CHAR_OPS: dict[str, TokenType] = {
    "<>": TokenType.NEQ,
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
}

_SINGLE_CHAR_OPS: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "=": TokenType.EQ,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    ",": TokenType.COMMA,
    ";": TokenType.SEMICOLON,
    ".": TokenType.DOT,
}


class Lexer:
    """Converts a SQL string into a list of tokens."""

    def __init__(self, source: str) -> None:
        self.source = source or ""
        self.length = len(self.source)
        self.pos = 0
        self.line = 1
        self.column = 1

    # -- low level helpers ---------------------------------------------------
    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return ""

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    # -- scanners ------------------------------------------------------------
    def _skip_whitespace_and_comments(self) -> None:
        while self.pos < self.length:
            ch = self._peek()
            if ch in _WHITESPACE:
                self._advance()
                continue
            # line comment: -- ...
            if ch == "-" and self._peek(1) == "-":
                while self.pos < self.length and self._peek() != "\n":
                    self._advance()
                continue
            # block comment: /* ... */
            if ch == "/" and self._peek(1) == "*":
                start_line, start_col = self.line, self.column
                self._advance()
                self._advance()
                closed = False
                while self.pos < self.length:
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance()
                        self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    raise LexError(
                        "Unterminated block comment.",
                        start_line,
                        start_col,
                        code="LEX005",
                        suggestion="Close the comment with '*/'.",
                    )
                continue
            break

    def _read_string(self) -> Token:
        start_line, start_col = self.line, self.column
        start = self.pos
        quote = self._advance()  # opening quote
        chars: list[str] = []
        while self.pos < self.length:
            ch = self._peek()
            if ch == quote:
                # Escaped quote by doubling: '' or ""
                if self._peek(1) == quote:
                    chars.append(quote)
                    self._advance()
                    self._advance()
                    continue
                self._advance()
                lexeme = self.source[start : self.pos]
                return Token(
                    type=TokenType.STRING,
                    lexeme=lexeme,
                    line=start_line,
                    column=start_col,
                    value="".join(chars),
                )
            if ch == "\n":
                break
            chars.append(self._advance())
        raise LexError(
            "Unterminated string literal.",
            start_line,
            start_col,
            code="LEX004",
            suggestion="Add a closing quote to terminate the string.",
        )

    def _read_number(self) -> Token:
        start_line, start_col = self.line, self.column
        start = self.pos
        while self._peek() in _DIGITS:
            self._advance()
        is_float = False
        if self._peek() == "." and self._peek(1) in _DIGITS:
            is_float = True
            self._advance()  # dot
            while self._peek() in _DIGITS:
                self._advance()
        if self._peek() in ("e", "E"):
            nxt = self._peek(1)
            sign = self._peek(2)
            if nxt in _DIGITS or (nxt in "+-" and sign in _DIGITS):
                is_float = True
                self._advance()  # e
                if self._peek() in "+-":
                    self._advance()
                while self._peek() in _DIGITS:
                    self._advance()
        lexeme = self.source[start : self.pos]
        if is_float:
            return Token(
                TokenType.FLOAT, lexeme, start_line, start_col, float(lexeme)
            )
        return Token(TokenType.INTEGER, lexeme, start_line, start_col, int(lexeme))

    def _read_identifier_or_keyword(self) -> Token:
        start_line, start_col = self.line, self.column
        start = self.pos
        while self._peek() in _IDENT_PART:
            self._advance()
        lexeme = self.source[start : self.pos]
        upper = lexeme.upper()
        if upper in KEYWORDS:
            return Token(KEYWORDS[upper], lexeme, start_line, start_col, upper)
        return Token(TokenType.IDENTIFIER, lexeme, start_line, start_col, lexeme)

    # -- public API ----------------------------------------------------------
    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_whitespace_and_comments()
            if self.pos >= self.length:
                break
            ch = self._peek()
            if ch in "'\"":
                tokens.append(self._read_string())
                continue
            if ch in _DIGITS:
                tokens.append(self._read_number())
                continue
            if ch in _IDENT_START:
                tokens.append(self._read_identifier_or_keyword())
                continue
            two = self.source[self.pos : self.pos + 2]
            if two in _TWO_CHAR_OPS:
                line, col = self.line, self.column
                self._advance()
                self._advance()
                tokens.append(Token(_TWO_CHAR_OPS[two], two, line, col, two))
                continue
            if ch in _SINGLE_CHAR_OPS:
                line, col = self.line, self.column
                self._advance()
                tokens.append(
                    Token(_SINGLE_CHAR_OPS[ch], ch, line, col, ch)
                )
                continue
            raise LexError(
                f"Unexpected character {ch!r}.",
                self.line,
                self.column,
                code="LEX002",
                suggestion="Remove the character or escape it inside a string literal.",
            )

        tokens.append(
            Token(TokenType.EOF, "", self.line, self.column, None)
        )
        return tokens


def tokenize(source: str) -> list[Token]:
    """Module-level convenience wrapper around :class:`Lexer`."""
    return Lexer(source).tokenize()
