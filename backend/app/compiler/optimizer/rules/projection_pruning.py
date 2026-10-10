"""Projection pruning: only read the columns a query actually needs."""
from __future__ import annotations

from ...ast import nodes as ast
from ...ir import nodes as ir
from ...ir.expr import columns_in, render
from ..context import OptimizerContext
from ..records import RuleFinding
from .base import Rule


class ProjectionPruning(Rule):
    name = "Projection Pruning"
    description = (
        "Remove columns from scans that are never referenced by any filter, "
        "join condition, grouping or projection, reducing tuple width."
    )

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        findings: list[RuleFinding] = []
        required = self._gather(root, ctx)
        new_root = self._prune(root, ctx, required, findings)
        return new_root, findings

    # -- required columns ----------------------------------------------------
    def _gather(self, node: ir.IRNode, ctx: OptimizerContext) -> set[str]:
        required: set[str] = set()

        def add(expr):
            if expr is None:
                return
            for column in columns_in(expr):
                source = ctx.expr.source_of(column)
                if source:
                    required.add(f"{source}.{column.name}".lower())

        if isinstance(node, ir.Filter):
            add(node.condition)
        if isinstance(node, ir.Join):
            add(node.condition)
        if isinstance(node, ir.Project):
            for expr in node.expressions:
                add(expr)
        if isinstance(node, ir.Aggregate):
            for func in node.functions:
                add(func)
            for group in node.group_by:
                add(group)
        if isinstance(node, ir.Sort):
            for item in node.items:
                add(item.column)

        for child in node.children:
            required |= self._gather(child, ctx)
        return required

    # -- pruning -------------------------------------------------------------
    def _prune(
        self,
        node: ir.IRNode,
        ctx: OptimizerContext,
        required: set[str],
        findings: list[RuleFinding],
    ) -> ir.IRNode:
        node.children = [self._prune(c, ctx, required, findings) for c in node.children]
        if isinstance(node, ir.Join):
            node.left, node.right = node.children[0], node.children[1]

        if isinstance(node, ir.Scan):
            source = (node.alias or node.table).lower()
            table = ctx.stats.get(node.table)
            all_columns = list(table.columns.keys()) if table else []
            if node.columns is None:
                base = all_columns
            else:
                base = list(node.columns)
            needed = [c for c in base if f"{source}.{c}".lower() in required]
            if needed and len(needed) < len(base):
                findings.append(
                    RuleFinding(
                        rule=self.name,
                        before=f"SCAN {node.table} [{'*' if node.columns is None else ', '.join(base)}]",
                        after=f"SCAN {node.table} [{', '.join(needed)}]",
                        reason=(
                            f"Only columns {needed} of '{node.table}' are referenced by the query; "
                            f"the other {len(base) - len(needed)} column(s) are pruned from the scan."
                        ),
                        target=node.table,
                    )
                )
                node.columns = needed
        return node
