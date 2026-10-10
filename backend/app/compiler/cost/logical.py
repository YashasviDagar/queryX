"""Logical (IR) cardinality estimation used by the optimizer.

Mirrors :class:`CostEstimator` but works on the relational IR so the optimizer
can report the row-count impact of each rule before any physical plan exists.
"""
from __future__ import annotations

import math

from ..ir import nodes as ir
from ..cost.cardinality import CardinalityEstimator
from .config import CostConfig


def estimate_ir_rows(node: ir.IRNode, estimator: CardinalityEstimator) -> float:
    if isinstance(node, ir.Scan):
        table = estimator.stats.get(node.table)
        return float(table.rows) if table else 0.0
    if isinstance(node, ir.Filter):
        child = estimate_ir_rows(node.children[0], estimator)
        return estimator.apply_filter(child, node.condition)
    if isinstance(node, ir.Project):
        return estimate_ir_rows(node.children[0], estimator)
    if isinstance(node, ir.Join):
        left = estimate_ir_rows(node.left, estimator) if node.left else 0.0
        right = estimate_ir_rows(node.right, estimator) if node.right else 0.0
        return estimator.join_rows(left, right, node.condition)
    if isinstance(node, ir.Aggregate):
        child = estimate_ir_rows(node.children[0], estimator)
        return estimator.aggregate_groups(child, node.group_by)
    if isinstance(node, ir.Sort):
        return estimate_ir_rows(node.children[0], estimator)
    if isinstance(node, ir.Distinct):
        child = estimate_ir_rows(node.children[0], estimator)
        return estimator.distinct_rows(child, node.expressions)
    if isinstance(node, ir.Limit):
        child = estimate_ir_rows(node.children[0], estimator)
        return estimator.limit_rows(child, node.count)
    return 0.0


def estimate_ir_cost(node: ir.IRNode, estimator: CardinalityEstimator, config: CostConfig) -> float:
    """A physical-choice-agnostic cost proxy for an IR subtree.

    Used to report the before/after cost of an optimization rule before any
    physical plan is selected. It assumes the pessimistic (nested-loop) join
    strategy, so predicate pushdown and join reordering show a clear benefit.
    """
    if isinstance(node, ir.Scan):
        rows = estimate_ir_rows(node, estimator)
        pages = math.ceil(rows / config.rows_per_page) if rows else 0
        return pages * config.seq_page_cost + rows * config.cpu_tuple_cost
    if isinstance(node, ir.Filter):
        child_rows = estimate_ir_rows(node.children[0], estimator)
        return estimate_ir_cost(node.children[0], estimator, config) + child_rows * config.cpu_operator_cost
    if isinstance(node, ir.Project):
        child_rows = estimate_ir_rows(node.children[0], estimator)
        return estimate_ir_cost(node.children[0], estimator, config) + child_rows * config.cpu_tuple_cost
    if isinstance(node, ir.Join):
        left_rows = estimate_ir_rows(node.left, estimator) if node.left else 0.0
        right_rows = estimate_ir_rows(node.right, estimator) if node.right else 0.0
        left_cost = estimate_ir_cost(node.left, estimator, config) if node.left else 0.0
        right_cost = estimate_ir_cost(node.right, estimator, config) if node.right else 0.0
        return left_cost + right_cost + left_rows * right_rows * config.cpu_tuple_cost
    if isinstance(node, ir.Aggregate):
        child_rows = estimate_ir_rows(node.children[0], estimator)
        return estimate_ir_cost(node.children[0], estimator, config) + child_rows * config.aggregate_cost
    if isinstance(node, ir.Sort):
        rows = estimate_ir_rows(node.children[0], estimator)
        comparisons = rows * math.log2(rows) if rows > 1 else 0.0
        return (
            estimate_ir_cost(node.children[0], estimator, config)
            + comparisons * config.sort_comparison_cost
            + rows * config.sort_cpu_cost
        )
    if isinstance(node, ir.Distinct):
        child_rows = estimate_ir_rows(node.children[0], estimator)
        return (
            estimate_ir_cost(node.children[0], estimator, config)
            + child_rows * (config.hash_build_cost + config.cpu_tuple_cost)
        )
    if isinstance(node, ir.Limit):
        rows = estimate_ir_rows(node, estimator)
        return estimate_ir_cost(node.children[0], estimator, config) + rows * config.cpu_tuple_cost
    return 0.0
