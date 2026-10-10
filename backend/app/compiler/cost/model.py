"""Transparent, educational cost model.

The model mirrors the spirit of classical cost-based optimizers (sequential vs
random I/O, per-tuple CPU, hash build/probe, sort comparisons) but uses small,
configurable constants. It is intended for *comparison and explanation*, not as
a prediction of real wall-clock execution time.
"""
from __future__ import annotations

import math
from typing import Optional

from ..ast import nodes as ast
from ..ir.expr import ExprContext, render
from ..planner.physical import PhysicalNode
from .cardinality import CardinalityEstimator
from .config import CostConfig
from .statistics import StatsStore


class CostEstimator:
    def __init__(self, stats: StatsStore, config: CostConfig, ctx: ExprContext) -> None:
        self.stats = stats
        self.config = config
        self.card = CardinalityEstimator(stats, config, ctx)

    # -- entry point ---------------------------------------------------------
    def estimate(self, plan: PhysicalNode) -> PhysicalNode:
        """Recursively annotate a physical plan with estimates."""
        for child in plan.children:
            self.estimate(child)

        op = plan.op
        handler = getattr(self, f"_cost_{op}", None)
        if handler is None:
            raise ValueError(f"No cost model implemented for operator '{op}'.")
        handler(plan)

        plan.estimated_cost = round(plan.estimated_cost, 2)
        plan.estimated_memory = round(plan.estimated_memory, 2)
        plan.estimated_operations = round(plan.estimated_operations, 2)
        return plan

    # -- scans ---------------------------------------------------------------
    def _cost_SeqScan(self, plan: PhysicalNode) -> None:
        table_name = plan.details.get("table", "")
        rows = float(self.stats.rows(table_name))
        pages = math.ceil(rows / self.config.rows_per_page) if rows else 0
        scan_cost = pages * self.config.seq_page_cost + rows * self.config.cpu_tuple_cost
        selectivity = plan.details.get("selectivity", 1.0)

        if selectivity < 1.0:
            # Predicate applied at scan time (pushdown into the access path).
            evaluated = rows
            output = max(self.config.min_rows, rows * selectivity)
            plan.estimated_cost = scan_cost + evaluated * self.config.cpu_operator_cost
            plan.estimated_operations = evaluated
        else:
            plan.estimated_cost = scan_cost
            plan.estimated_operations = rows
            output = rows

        plan.estimated_rows = output
        plan.estimated_memory = 0.0

    def _cost_IndexScan(self, plan: PhysicalNode) -> None:
        table_name = plan.details.get("table", "")
        rows = float(self.stats.rows(table_name))
        selectivity = plan.details.get("selectivity", 1.0)
        selected = max(self.config.min_rows, rows * selectivity)
        plan.estimated_cost = (
            self.config.index_startup_cost
            + selected * self.config.index_tuple_cost
            + selected * self.config.cpu_tuple_cost
        )
        plan.estimated_rows = selected
        plan.estimated_operations = selected
        plan.estimated_memory = 0.0

    # -- filter --------------------------------------------------------------
    def _cost_Filter(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        condition = plan.details.get("condition")
        selectivity = self.card.predicate_selectivity(condition)
        plan.estimated_rows = self.card.apply_filter(child.estimated_rows, condition)
        plan.estimated_cost = child.estimated_cost + child.estimated_rows * self.config.cpu_operator_cost
        plan.estimated_operations = child.estimated_rows
        plan.estimated_memory = child.estimated_memory

    # -- joins ---------------------------------------------------------------
    def _join_common(self, plan: PhysicalNode) -> tuple[PhysicalNode, PhysicalNode, float]:
        left, right = plan.children
        rows = self.card.join_rows(
            left.estimated_rows, right.estimated_rows, plan.details.get("condition")
        )
        return left, right, rows

    def _cost_NestedLoopJoin(self, plan: PhysicalNode) -> None:
        left, right, rows = self._join_common(plan)
        comparisons = left.estimated_rows * right.estimated_rows
        plan.estimated_cost = (
            left.estimated_cost
            + right.estimated_cost
            + comparisons * self.config.cpu_tuple_cost
        )
        plan.estimated_rows = rows
        plan.estimated_operations = comparisons
        plan.estimated_memory = max(left.estimated_memory, right.estimated_memory)

    def _cost_HashJoin(self, plan: PhysicalNode) -> None:
        left, right, rows = self._join_common(plan)
        build, probe = (left, right) if left.estimated_rows <= right.estimated_rows else (right, left)
        plan.estimated_cost = (
            left.estimated_cost
            + right.estimated_cost
            + build.estimated_rows * self.config.hash_build_cost
            + probe.estimated_rows * self.config.hash_probe_cost
            + rows * self.config.cpu_tuple_cost
        )
        plan.estimated_rows = rows
        plan.estimated_operations = left.estimated_rows + right.estimated_rows
        plan.estimated_memory = build.estimated_rows * self.config.bytes_per_row
        plan.details["buildSide"] = "left" if build is left else "right"

    def _cost_MergeJoin(self, plan: PhysicalNode) -> None:
        left, right, rows = self._join_common(plan)
        plan.estimated_cost = (
            left.estimated_cost
            + right.estimated_cost
            + (left.estimated_rows + right.estimated_rows) * self.config.merge_cost
            + rows * self.config.cpu_tuple_cost
        )
        plan.estimated_rows = rows
        plan.estimated_operations = left.estimated_rows + right.estimated_rows
        plan.estimated_memory = max(left.estimated_memory, right.estimated_memory)

    # -- sort / aggregate / project / limit ----------------------------------
    def _cost_Sort(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        rows = child.estimated_rows
        n = max(rows, 1.0)
        comparisons = n * math.log2(n) if n > 1 else 0.0
        plan.estimated_cost = (
            child.estimated_cost
            + comparisons * self.config.sort_comparison_cost
            + rows * self.config.sort_cpu_cost
        )
        plan.estimated_rows = rows
        plan.estimated_operations = rows
        plan.estimated_memory = rows * self.config.bytes_per_row

    def _cost_Aggregate(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        group_by = plan.details.get("groupBy", [])
        functions = plan.details.get("functions", [])
        has_distinct = any(getattr(function, "distinct", False) for function in functions)
        per_row = self.config.aggregate_cost * (2.0 if has_distinct else 1.0)
        plan.estimated_rows = self.card.aggregate_groups(child.estimated_rows, group_by)
        plan.estimated_cost = child.estimated_cost + child.estimated_rows * per_row
        plan.estimated_operations = child.estimated_rows
        plan.estimated_memory = plan.estimated_rows * self.config.bytes_per_row

    def _cost_Distinct(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        expressions = plan.details.get("expressions", [])
        plan.estimated_rows = self.card.distinct_rows(child.estimated_rows, expressions)
        plan.estimated_cost = (
            child.estimated_cost
            + child.estimated_rows * (self.config.hash_build_cost + self.config.cpu_tuple_cost)
        )
        plan.estimated_operations = child.estimated_rows
        plan.estimated_memory = plan.estimated_rows * self.config.bytes_per_row

    def _cost_Project(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        plan.estimated_rows = child.estimated_rows
        plan.estimated_cost = child.estimated_cost + child.estimated_rows * self.config.cpu_tuple_cost
        plan.estimated_operations = child.estimated_rows
        plan.estimated_memory = child.estimated_memory

    def _cost_Limit(self, plan: PhysicalNode) -> None:
        child = plan.children[0]
        count = int(plan.details.get("count", 0))
        plan.estimated_rows = self.card.limit_rows(child.estimated_rows, count)
        plan.estimated_cost = child.estimated_cost + plan.estimated_rows * self.config.cpu_tuple_cost
        plan.estimated_operations = plan.estimated_rows
        plan.estimated_memory = child.estimated_memory


def condition_text(node: Optional[ast.Node]) -> str:
    return render(node)
