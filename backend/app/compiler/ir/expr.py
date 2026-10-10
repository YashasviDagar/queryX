"""Expression utilities shared by the IR builder and optimizer.

These helpers keep expression trees (predicates, join conditions, projections)
easy to inspect, split, combine and render without coupling the optimizer to
the AST module internals.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

from ..ast import nodes as ast
from ..semantic.analyzer import ResolvedColumn


@dataclass
class ExprContext:
    """Maps column references to the scan key (alias-or-table) they belong to."""

    resolution: dict[int, ResolvedColumn]
    alias_to_table: dict[str, str]
    table_to_alias: dict[str, str]

    @classmethod
    def from_semantic(cls, resolution: dict[int, ResolvedColumn], scope: dict[str, str]) -> "ExprContext":
        alias_to_table = {a.lower(): t for a, t in scope.items()}
        table_to_alias: dict[str, str] = {}
        for alias, table in alias_to_table.items():
            table_to_alias.setdefault(table.lower(), alias)
        return cls(resolution, alias_to_table, table_to_alias)

    def source_of(self, column: ast.Column) -> Optional[str]:
        if column.table:
            return column.table.lower()
        resolved = self.resolution.get(id(column))
        if resolved:
            return self.table_to_alias.get(resolved.table.lower(), resolved.table.lower())
        return None


def render(node: Optional[ast.Node]) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Literal):
        if node.literal_type == "string":
            return f"'{node.value}'"
        return str(node.value)
    if isinstance(node, ast.Column):
        return node.qualified_name
    if isinstance(node, ast.FunctionCall):
        distinct = "DISTINCT " if node.distinct else ""
        if node.star:
            inner = "*"
        else:
            inner = ", ".join(render(a) for a in node.args)
        return f"{node.name}({distinct}{inner})"
    if isinstance(node, ast.Comparison):
        return f"{render(node.left)} {node.operator} {render(node.right)}"
    if isinstance(node, ast.LogicalExpression):
        return f"{render(node.left)} {node.operator} {render(node.right)}"
    if isinstance(node, ast.BinaryExpression):
        if node.operator == "NOT":
            return f"NOT {render(node.right)}"
        return f"{render(node.left)} {node.operator} {render(node.right)}"
    return node.kind


def clone(node: Optional[ast.Node]) -> Optional[ast.Node]:
    if node is None:
        return None
    return copy.deepcopy(node)


def conjuncts(node: Optional[ast.Node]) -> list[ast.Node]:
    """Split an AND-chain into its individual predicates."""
    if node is None:
        return []
    if isinstance(node, ast.LogicalExpression) and node.operator == "AND":
        return conjuncts(node.left) + conjuncts(node.right)
    return [node]


def combine_and(predicates: list[ast.Node]) -> Optional[ast.Node]:
    """Combine predicates into a single AND-chain."""
    predicates = [p for p in predicates if p is not None]
    if not predicates:
        return None
    result = predicates[0]
    for pred in predicates[1:]:
        result = ast.LogicalExpression(left=result, operator="AND", right=pred)
    return result


def referenced_sources(node: Optional[ast.Node], ctx: ExprContext) -> set[str]:
    """Return the set of scan keys referenced by an expression."""
    sources: set[str] = set()
    if node is None:
        return sources
    if isinstance(node, ast.Column):
        source = ctx.source_of(node)
        if source:
            sources.add(source)
    elif isinstance(node, ast.FunctionCall):
        for arg in node.args:
            sources |= referenced_sources(arg, ctx)
    elif isinstance(node, (ast.Comparison, ast.LogicalExpression, ast.BinaryExpression)):
        sources |= referenced_sources(node.left, ctx)
        sources |= referenced_sources(node.right, ctx)
    return sources


def columns_in(node: Optional[ast.Node]) -> list[ast.Column]:
    found: list[ast.Column] = []
    if node is None:
        return found
    if isinstance(node, ast.Column):
        found.append(node)
    elif isinstance(node, ast.FunctionCall):
        for arg in node.args:
            found.extend(columns_in(arg))
    elif isinstance(node, (ast.Comparison, ast.LogicalExpression, ast.BinaryExpression)):
        found.extend(columns_in(node.left))
        found.extend(columns_in(node.right))
    return found


_NO_VALUE = object()
# Public alias so other stages can test for "not a constant".
NO_VALUE = _NO_VALUE


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_constant(node: Optional[ast.Node]) -> Any:
    """Evaluate a fully-constant expression, returning ``_NO_VALUE`` otherwise."""
    if node is None:
        return _NO_VALUE
    if isinstance(node, ast.Literal):
        return node.value
    if isinstance(node, ast.BinaryExpression):
        if node.operator == "NOT":
            operand = evaluate_constant(node.right)
            if operand is _NO_VALUE or not isinstance(operand, bool):
                return _NO_VALUE
            return not operand
        left = evaluate_constant(node.left)
        right = evaluate_constant(node.right)
        if left is _NO_VALUE or right is _NO_VALUE:
            return _NO_VALUE
        try:
            if node.operator == "+":
                return left + right
            if node.operator == "-":
                return left - right
            if node.operator == "*":
                return left * right
            if node.operator == "/":
                return left / right if right else _NO_VALUE
            if node.operator == "%":
                return left % right if right else _NO_VALUE
        except TypeError:
            return _NO_VALUE
        return _NO_VALUE
    if isinstance(node, ast.Comparison):
        left = evaluate_constant(node.left)
        right = evaluate_constant(node.right)
        if left is _NO_VALUE or right is _NO_VALUE:
            return _NO_VALUE
        try:
            if node.operator == "=":
                return left == right
            if node.operator == "<>":
                return left != right
            if node.operator == "<":
                return left < right
            if node.operator == "<=":
                return left <= right
            if node.operator == ">":
                return left > right
            if node.operator == ">=":
                return left >= right
        except TypeError:
            return _NO_VALUE
        return _NO_VALUE
    if isinstance(node, ast.LogicalExpression):
        left = evaluate_constant(node.left)
        right = evaluate_constant(node.right)
        if left is _NO_VALUE or right is _NO_VALUE:
            return _NO_VALUE
        if node.operator == "AND":
            return bool(left) and bool(right)
        if node.operator == "OR":
            return bool(left) or bool(right)
        return _NO_VALUE
    return _NO_VALUE


def is_constant(node: Optional[ast.Node]) -> bool:
    return evaluate_constant(node) is not _NO_VALUE


def make_literal(value: Any) -> ast.Literal:
    if isinstance(value, bool):
        return ast.Literal(value=value, literal_type="boolean")
    if isinstance(value, int):
        return ast.Literal(value=value, literal_type="integer")
    if isinstance(value, float):
        return ast.Literal(value=value, literal_type="float")
    if isinstance(value, str):
        return ast.Literal(value=value, literal_type="string")
    return ast.Literal(value=value, literal_type="unknown")


def canonical(node: Optional[ast.Node]) -> str:
    """A normalised string key used to detect redundant predicates."""
    return render(node).replace(" ", "").lower()


def render_tree(node, indent: int = 0) -> str:
    """Render an IR subtree as an indented multi-line string."""
    lines = ["  " * indent + node.label()]
    for child in node.children:
        lines.append(render_tree(child, indent + 1))
    return "\n".join(lines)
