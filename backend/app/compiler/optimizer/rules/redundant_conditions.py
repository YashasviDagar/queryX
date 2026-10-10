"""Redundant condition removal: drop duplicate predicates from AND-chains."""
from __future__ import annotations

from ...ast import nodes as ast
from ...ir import nodes as ir
from ...ir.expr import canonical, combine_and, conjuncts, render
from ..context import OptimizerContext
from ..records import RuleFinding
from .base import Rule


class RedundantConditionRemoval(Rule):
    name = "Redundant Condition Removal"
    description = (
        "Detect predicates that appear more than once in a conjunction and "
        "collapse them into a single evaluation."
    )

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        findings: list[RuleFinding] = []
        new_root = self._visit(root, findings)
        return new_root, findings

    def _visit(self, node: ir.IRNode, findings: list[RuleFinding]) -> ir.IRNode:
        node.children = [self._visit(c, findings) for c in node.children]
        if isinstance(node, ir.Join):
            node.left, node.right = node.children[0], node.children[1]
            node.condition = self._dedupe(node.condition, findings, "join condition")
        elif isinstance(node, ir.Filter):
            node.condition = self._dedupe(node.condition, findings, "filter")
            if node.condition is None:
                return node.children[0]
        return node

    def _dedupe(self, condition, findings: list[RuleFinding], target: str):
        if condition is None:
            return None
        predicates = conjuncts(condition)
        seen: dict[str, ast.Node] = {}
        removed: list[str] = []
        for pred in predicates:
            key = canonical(pred)
            if key in seen:
                removed.append(render(pred))
            else:
                seen[key] = pred
        if not removed:
            return condition
        findings.append(
            RuleFinding(
                rule=self.name,
                before=render(condition),
                after=render(combine_and(list(seen.values()))),
                reason=(
                    "Removed duplicate predicate(s) "
                    + ", ".join(f"'{r}'" for r in removed)
                    + "; each predicate only needs to be evaluated once."
                ),
                target=target,
            )
        )
        return combine_and(list(seen.values()))
