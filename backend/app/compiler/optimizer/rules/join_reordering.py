"""Join reordering: choose a cheaper join order for inner-join queries."""
from __future__ import annotations

from ...ir import nodes as ir
from ...ir.expr import render_tree
from ...cost.logical import estimate_ir_rows
from ..context import OptimizerContext
from ..join_utils import build_left_deep_join, flatten_inner_joins
from ..records import RuleFinding
from .base import Rule


class JoinReordering(Rule):
    name = "Join Reordering"
    description = (
        "For inner-join queries, enumerate the participating relations and "
        "build a left-deep join order that starts from the most selective "
        "relations, so smaller intermediate results feed the joins."
    )

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        findings: list[RuleFinding] = []
        new_root = self._visit(root, ctx, findings)
        return new_root, findings

    def _visit(self, node: ir.IRNode, ctx: OptimizerContext, findings: list[RuleFinding]) -> ir.IRNode:
        node.children = [self._visit(c, ctx, findings) for c in node.children]
        if isinstance(node, ir.Join):
            node.left, node.right = node.children[0], node.children[1]

        if isinstance(node, ir.Join) and self._is_inner_join_tree(node):
            relations, predicates = flatten_inner_joins(node)
            if len(relations) > 1:
                estimator = ctx.cardinality
                ordered = sorted(relations, key=lambda r: estimate_ir_rows(r, estimator))
                ordered_sources = [self._source(r) for r in ordered]
                # Compare by identity: outer-join subtrees share a generic label.
                if [id(r) for r in ordered] != [id(r) for r in relations]:
                    rebuilt = build_left_deep_join(ordered, predicates, ctx.expr)
                    findings.append(
                        RuleFinding(
                            rule=self.name,
                            before=render_tree(node),
                            after=render_tree(rebuilt),
                            reason=(
                                "Reordered inner joins by ascending estimated cardinality "
                                f"({ordered_sources}); starting from the smallest relations "
                                "reduces the size of intermediate join results."
                            ),
                            target="join tree",
                        )
                    )
                    return rebuilt
        return node

    def _is_inner_join_tree(self, node: ir.IRNode) -> bool:
        if isinstance(node, ir.Join):
            if node.join_type != "INNER":
                return False
            return self._is_inner_join_tree(node.left) and self._is_inner_join_tree(node.right)
        return True

    def _source(self, node: ir.IRNode) -> str:
        if isinstance(node, ir.Scan):
            return (node.alias or node.table).lower()
        if isinstance(node, ir.Filter) and node.children:
            return self._source(node.children[0])
        return node.op.lower()
