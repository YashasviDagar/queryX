"""Cardinality (row-count) estimation.

Implements a simple, well-documented selectivity model:
  * equality on a column   -> 1 / distinct(column)
  * equality between columns -> 1 / max(distinct(left), distinct(right))
  * range predicate        -> configurable uniform assumption
  * AND                    -> product of selectivities (independence assumption)
  * OR                     -> s1 + s2 - s1*s2
"""
from __future__ import annotations

import math
from typing import Optional

from ..ast import nodes as ast
from ..ir.expr import NO_VALUE, ExprContext, evaluate_constant, conjuncts
from .config import CostConfig
from .statistics import StatsStore


class CardinalityEstimator:
    def __init__(self, stats: StatsStore, config: CostConfig, ctx: ExprContext) -> None:
        self.stats = stats
        self.config = config
        self.ctx = ctx

    # -- column metadata -----------------------------------------------------
    def distinct(self, column: ast.Column) -> Optional[int]:
        source = self.ctx.source_of(column)
        if source is None:
            return None
        table_name = self.ctx.alias_to_table.get(source, source)
        table = self.stats.get(table_name)
        if table is None:
            return None
        col = table.column(column.name)
        if col is None:
            return None
        return max(col.distinct, 1)

    def _table_of(self, column: ast.Column):
        source = self.ctx.source_of(column)
        if source is None:
            return None
        return self.stats.get(self.ctx.alias_to_table.get(source, source))

    # -- selectivity ---------------------------------------------------------
    def predicate_selectivity(self, node: Optional[ast.Node]) -> float:
        if node is None:
            return 1.0

        constant = evaluate_constant(node)
        if constant is not NO_VALUE:
            return 1.0 if bool(constant) else 0.0

        if isinstance(node, ast.LogicalExpression):
            left = self.predicate_selectivity(node.left)
            right = self.predicate_selectivity(node.right)
            if node.operator == "AND":
                return left * right
            if node.operator == "OR":
                return left + right - left * right
            return self.config.default_selectivity

        if isinstance(node, ast.BinaryExpression) and node.operator == "NOT":
            return max(0.0, 1.0 - self.predicate_selectivity(node.right))

        if isinstance(node, ast.Comparison):
            return self._comparison_selectivity(node)

        return self.config.default_selectivity

    def _comparison_selectivity(self, node: ast.Comparison) -> float:
        left, right = node.left, node.right
        op = node.operator

        # column vs column
        if isinstance(left, ast.Column) and isinstance(right, ast.Column):
            dl = self.distinct(left) or 0
            dr = self.distinct(right) or 0
            denom = max(dl, dr, 1)
            return 1.0 / denom

        # column vs literal (either order)
        column = left if isinstance(left, ast.Column) else right if isinstance(right, ast.Column) else None
        if column is None:
            return self.config.default_selectivity

        distinct = self.distinct(column)

        if op in ("=", "<>"):
            if distinct:
                base = 1.0 / distinct
            else:
                base = self.config.equality_selectivity or self.config.default_selectivity
            return base if op == "=" else max(0.0, 1.0 - base)

        if op in ("<", "<=", ">", ">="):
            return self.config.range_selectivity

        return self.config.default_selectivity

    # -- operator outputs ----------------------------------------------------
    def apply_filter(self, input_rows: float, condition: Optional[ast.Node]) -> float:
        rows = input_rows * self.predicate_selectivity(condition)
        return max(self.config.min_rows, rows)

    def join_rows(self, left_rows: float, right_rows: float, condition: Optional[ast.Node]) -> float:
        selectivity = 1.0
        for predicate in conjuncts(condition):
            if isinstance(predicate, ast.Comparison):
                selectivity *= self._comparison_selectivity(predicate)
            else:
                selectivity *= self.config.default_selectivity
        rows = left_rows * right_rows * selectivity
        return max(self.config.min_rows, rows)

    def aggregate_groups(
        self, input_rows: float, group_by: list[ast.Column]
    ) -> float:
        if not group_by:
            return 1.0
        groups = 1.0
        for column in group_by:
            groups *= self.distinct(column) or 1
        return max(self.config.min_rows, min(input_rows, groups))

    def sort_rows(self, input_rows: float) -> float:
        return input_rows

    def distinct_rows(self, input_rows: float, expressions: list[ast.Node]) -> float:
        """Estimate the output of a DISTINCT over the given projected expressions.

        When every expression is a base column with known cardinality the result
        is the product of the distinct counts, capped at the input size. If any
        expression is computed (and therefore has no statistics), we conservatively
        assume no reduction.
        """
        if not expressions:
            return max(self.config.min_rows, input_rows)
        groups = 1.0
        for expression in expressions:
            if not isinstance(expression, ast.Column):
                return max(self.config.min_rows, input_rows)
            distinct = self.distinct(expression)
            if not distinct:
                return max(self.config.min_rows, input_rows)
            groups *= distinct
        return max(self.config.min_rows, min(input_rows, groups))

    def limit_rows(self, input_rows: float, count: int) -> float:
        return max(0.0, min(input_rows, count))
