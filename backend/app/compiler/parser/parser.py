"""Recursive-descent parser for the supported SQL subset.

Grammar (EBNF) is documented in ``docs/grammar.md``. The parser consumes the
token stream produced by the lexer and builds a typed AST.
"""
from __future__ import annotations

from typing import Optional

from ..ast import nodes as ast
from ..lexer.errors import ParseError
from ..lexer.tokens import Token, TokenType

_COMPARISON_TOKENS = {
    TokenType.EQ: "=",
    TokenType.NEQ: "<>",
    TokenType.LT: "<",
    TokenType.LTE: "<=",
    TokenType.GT: ">",
    TokenType.GTE: ">=",
}

_ADDITIVE_TOKENS = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
}

_MULTIPLICATIVE_TOKENS = {
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.PERCENT: "%",
}

_AGGREGATE_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


class Parser:
    """Parses a SQL string into an :class:`ast.Query`."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # -- token helpers -------------------------------------------------------
    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        token = self.current
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def _check(self, *types: TokenType) -> bool:
        return self.current.type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self.current.type in types:
            return self._advance()
        return None

    def _expect(self, token_type: TokenType, what: str) -> Token:
        if self.current.type != token_type:
            raise ParseError(
                f"Expected {what} but found '{self.current.lexeme or self.current.type.value}'.",
                self.current.line,
                self.current.column,
                code="PAR002",
                suggestion=f"Insert {what} here.",
            )
        return self._advance()

    def _error(self, message: str, code: str = "PAR001", suggestion: Optional[str] = None) -> ParseError:
        return ParseError(
            message,
            self.current.line,
            self.current.column,
            code=code,
            suggestion=suggestion,
        )

    # -- entry point ---------------------------------------------------------
    def parse(self) -> ast.Query:
        query = self._parse_query()
        self._match(TokenType.SEMICOLON)
        if self.current.type != TokenType.EOF:
            raise self._error(
                f"Unexpected token '{self.current.lexeme}' after end of query.",
                code="PAR003",
                suggestion="Remove the trailing tokens or start a new statement with ';'.",
            )
        return query

    # -- query ---------------------------------------------------------------
    def _parse_query(self) -> ast.Query:
        start = self.current
        select = self._parse_select()
        self._expect(TokenType.FROM, "FROM")
        from_clause = self._parse_from()

        joins: list[ast.Join] = []
        while self._check(TokenType.JOIN, TokenType.INNER, TokenType.LEFT, TokenType.RIGHT):
            joins.append(self._parse_join())

        where = None
        if self._match(TokenType.WHERE):
            where = ast.Where(condition=self._parse_expression(), line=self.current.line, col=self.current.column)

        group_by = None
        if self._check(TokenType.GROUP):
            group_by = self._parse_group_by()

        having = None
        if self._check(TokenType.HAVING):
            having = self._parse_having()

        order_by = None
        if self._check(TokenType.ORDER):
            order_by = self._parse_order_by()

        limit = None
        if self._check(TokenType.LIMIT):
            limit = self._parse_limit()

        return ast.Query(
            select=select,
            from_clause=from_clause,
            joins=joins,
            where=where,
            group_by=group_by,
            having=having,
            order_by=order_by,
            limit=limit,
            line=start.line,
            col=start.column,
        )

    def _parse_select(self) -> ast.Select:
        start = self._expect(TokenType.SELECT, "SELECT")
        distinct = self._match(TokenType.DISTINCT) is not None
        columns = [self._parse_select_item()]
        while self._match(TokenType.COMMA):
            columns.append(self._parse_select_item())
        return ast.Select(columns=columns, distinct=distinct, line=start.line, col=start.column)

    def _parse_select_item(self) -> ast.Node:
        if self._check(TokenType.STAR):
            tok = self._advance()
            return ast.Column(name="*", line=tok.line, col=tok.column)
        expr = self._parse_expression()
        alias = self._parse_optional_alias()
        if alias is not None and isinstance(expr, ast.Column):
            expr.alias = alias
            return expr
        if alias is not None and isinstance(expr, ast.FunctionCall):
            expr.alias = alias
            return expr
        if alias is not None:
            return ast.Column(name=expr.kind, table=None, alias=alias, line=expr.line, col=expr.col)
        return expr

    def _parse_optional_alias(self) -> Optional[ast.Alias]:
        if self._match(TokenType.AS):
            tok = self._expect(TokenType.IDENTIFIER, "an alias name")
            return ast.Alias(name=tok.lexeme, line=tok.line, col=tok.column)
        if self._check(TokenType.IDENTIFIER):
            tok = self._advance()
            return ast.Alias(name=tok.lexeme, line=tok.line, col=tok.column)
        return None

    def _parse_from(self) -> ast.From:
        table = self._parse_table_ref()
        return ast.From(table=table, line=table.line, col=table.col)

    def _parse_table_ref(self) -> ast.Table:
        name_tok = self._expect(TokenType.IDENTIFIER, "a table name")
        alias = self._parse_optional_alias()
        return ast.Table(name=name_tok.lexeme, alias=alias, line=name_tok.line, col=name_tok.column)

    def _parse_join(self) -> ast.Join:
        start = self.current
        join_type = "INNER"
        if self._match(TokenType.INNER):
            join_type = "INNER"
            self._expect(TokenType.JOIN, "JOIN")
        elif self._match(TokenType.LEFT):
            join_type = "LEFT"
            self._match(TokenType.OUTER)
            self._expect(TokenType.JOIN, "JOIN")
        elif self._match(TokenType.RIGHT):
            join_type = "RIGHT"
            self._match(TokenType.OUTER)
            self._expect(TokenType.JOIN, "JOIN")
        else:
            self._expect(TokenType.JOIN, "JOIN")

        table = self._parse_table_ref()
        condition = None
        if self._match(TokenType.ON):
            condition = self._parse_expression()
        else:
            raise self._error(
                "JOIN requires an ON condition.",
                code="PAR004",
                suggestion="Add 'ON <left.column> = <right.column>'.",
            )
        return ast.Join(join_type=join_type, table=table, condition=condition, line=start.line, col=start.column)

    def _parse_group_by(self) -> ast.GroupBy:
        start = self._expect(TokenType.GROUP, "GROUP")
        self._expect(TokenType.BY, "BY")
        columns = [self._parse_column_ref()]
        while self._match(TokenType.COMMA):
            columns.append(self._parse_column_ref())
        return ast.GroupBy(columns=columns, line=start.line, col=start.column)

    def _parse_having(self) -> ast.Having:
        start = self._expect(TokenType.HAVING, "HAVING")
        return ast.Having(condition=self._parse_expression(), line=start.line, col=start.column)

    def _parse_order_by(self) -> ast.OrderBy:
        start = self._expect(TokenType.ORDER, "ORDER")
        self._expect(TokenType.BY, "BY")
        items = [self._parse_order_item()]
        while self._match(TokenType.COMMA):
            items.append(self._parse_order_item())
        return ast.OrderBy(items=items, line=start.line, col=start.column)

    def _parse_order_item(self) -> ast.OrderByItem:
        column = self._parse_column_ref()
        direction = "ASC"
        if self._match(TokenType.ASC):
            direction = "ASC"
        elif self._match(TokenType.DESC):
            direction = "DESC"
        return ast.OrderByItem(column, direction, line=column.line, col=column.col)

    def _parse_limit(self) -> ast.Limit:
        start = self._expect(TokenType.LIMIT, "LIMIT")
        count_tok = self._expect(TokenType.INTEGER, "an integer row count")
        return ast.Limit(count=int(count_tok.value), line=start.line, col=start.column)

    # -- expressions ---------------------------------------------------------
    def _parse_expression(self) -> ast.Node:
        return self._parse_or()

    def _parse_or(self) -> ast.Node:
        left = self._parse_and()
        while self._check(TokenType.OR):
            tok = self._advance()
            right = self._parse_and()
            left = ast.LogicalExpression(left=left, operator="OR", right=right, line=tok.line, col=tok.column)
        return left

    def _parse_and(self) -> ast.Node:
        left = self._parse_not()
        while self._check(TokenType.AND):
            tok = self._advance()
            right = self._parse_not()
            left = ast.LogicalExpression(left=left, operator="AND", right=right, line=tok.line, col=tok.column)
        return left

    def _parse_not(self) -> ast.Node:
        if self._check(TokenType.NOT):
            tok = self._advance()
            operand = self._parse_not()
            return ast.BinaryExpression(left=None, operator="NOT", right=operand, line=tok.line, col=tok.column)
        return self._parse_comparison()

    def _parse_comparison(self) -> ast.Node:
        left = self._parse_additive()
        if self.current.type in _COMPARISON_TOKENS:
            tok = self._advance()
            right = self._parse_additive()
            return ast.Comparison(
                left=left,
                operator=_COMPARISON_TOKENS[tok.type],
                right=right,
                line=tok.line,
                col=tok.column,
            )
        return left

    def _parse_additive(self) -> ast.Node:
        left = self._parse_multiplicative()
        while self.current.type in _ADDITIVE_TOKENS:
            tok = self._advance()
            right = self._parse_multiplicative()
            left = ast.BinaryExpression(
                left=left,
                operator=_ADDITIVE_TOKENS[tok.type],
                right=right,
                line=tok.line,
                col=tok.column,
            )
        return left

    def _parse_multiplicative(self) -> ast.Node:
        left = self._parse_primary()
        while self.current.type in _MULTIPLICATIVE_TOKENS:
            tok = self._advance()
            right = self._parse_primary()
            left = ast.BinaryExpression(
                left=left,
                operator=_MULTIPLICATIVE_TOKENS[tok.type],
                right=right,
                line=tok.line,
                col=tok.column,
            )
        return left

    def _parse_primary(self) -> ast.Node:
        token = self.current

        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, "')'")
            return expr

        if token.type == TokenType.INTEGER:
            self._advance()
            return ast.Literal(value=token.value, literal_type="integer", line=token.line, col=token.column)

        if token.type == TokenType.FLOAT:
            self._advance()
            return ast.Literal(value=token.value, literal_type="float", line=token.line, col=token.column)

        if token.type == TokenType.STRING:
            self._advance()
            return ast.Literal(value=token.value, literal_type="string", line=token.line, col=token.column)

        if token.type == TokenType.IDENTIFIER:
            # function call?
            if self._peek().type == TokenType.LPAREN:
                return self._parse_function_call()
            return self._parse_column_ref()

        raise self._error(
            f"Unexpected token '{token.lexeme or token.type.value}' in expression.",
            code="PAR005",
            suggestion="Expected a column, literal, function call or parenthesised expression.",
        )

    def _parse_function_call(self) -> ast.FunctionCall:
        name_tok = self._expect(TokenType.IDENTIFIER, "a function name")
        self._expect(TokenType.LPAREN, "'('")
        distinct = self._match(TokenType.DISTINCT) is not None
        args: list[ast.Node] = []
        star = False
        if self._check(TokenType.STAR):
            self._advance()
            star = True
        else:
            args.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                args.append(self._parse_expression())
        self._expect(TokenType.RPAREN, "')'")
        return ast.FunctionCall(
            name=name_tok.lexeme.upper(),
            args=args,
            distinct=distinct,
            star=star,
            line=name_tok.line,
            col=name_tok.column,
        )

    def _parse_column_ref(self) -> ast.Column:
        first = self._expect(TokenType.IDENTIFIER, "a column name")
        if self._match(TokenType.DOT):
            second = self._expect(TokenType.IDENTIFIER, "a column name after '.'")
            return ast.Column(name=second.lexeme, table=first.lexeme, line=first.line, col=first.column)
        return ast.Column(name=first.lexeme, table=None, line=first.line, col=first.column)


def parse(tokens: list[Token]) -> ast.Query:
    """Parse a token list into an AST query."""
    return Parser(tokens).parse()
