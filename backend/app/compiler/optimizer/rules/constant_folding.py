"""Constant folding: evaluate constant sub-expressions at optimization time."""
from __future__ import annotations

from typing import Optional

from ...ast import nodes as ast
from ...ir import nodes as ir
from ...ir.expr import NO_VALUE, evaluate_constant, make_literal, render
from ..context import OptimizerContext
from ..records import RuleFinding
from .base import Rule


class ConstantFolding(Rule):
    name = "Constant Folding"
    description = (
        "Evaluate expressions whose operands are all literals during "
        "optimization instead of at execution time."
    )

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        findings: list[RuleFinding] = []
        new_root = self._visit(root, findings)
        return new_root, findings

    def _visit(self, node: ir.IRNode, findings: list[RuleFinding]) -> ir.IRNode:
        node.children = [self._visit(c, findings) for c in node.children]

        if isinstance(node, ir.Join):
            node.left, node.right = node.children[0], node.children[1]
            if node.condition is not None:
                node.condition = self._fold(node.condition, findings)
        elif isinstance(node, ir.Filter):
            if node.condition is not None:
                folded = self._fold(node.condition, findings)
                node.condition = folded
                if isinstance(folded, ast.Literal) and folded.literal_type == "boolean" and folded.value is True:
                    findings.append(
                        RuleFinding(
                            rule=self.name,
                            before=f"FILTER({render(node.condition)})",
                            after="(filter removed)",
                            reason="Predicate folded to TRUE, so the filter is redundant and removed.",
                            target="filter",
                        )
                    )
                    return node.children[0]
        elif isinstance(node, ir.Project):
            node.expressions = [self._fold(e, findings) for e in node.expressions]
        elif isinstance(node, ir.Sort):
            for item in node.items:
                item.column = self._fold(item.column, findings)
        elif isinstance(node, ir.Aggregate):
            node.functions = [self._fold(f, findings) for f in node.functions]
            node.group_by = [self._fold(g, findings) for g in node.group_by]

        return node

    def _fold(self, node: Optional[ast.Node], findings: list[RuleFinding]) -> Optional[ast.Node]:
        if node is None:
            return None
        before = render(node)

        if isinstance(node, ast.BinaryExpression):
            node.left = self._fold(node.left, findings)
            node.right = self._fold(node.right, findings)
        elif isinstance(node, (ast.Comparison, ast.LogicalExpression)):
            node.left = self._fold(node.left, findings)
            node.right = self._fold(node.right, findings)
        elif isinstance(node, ast.FunctionCall):
            node.args = [self._fold(a, findings) for a in node.args]

        value = evaluate_constant(node)
        if value is not NO_VALUE and not isinstance(node, ast.Literal):
            folded = make_literal(value)
            findings.append(
                RuleFinding(
                    rule=self.name,
                    before=before,
                    after=render(folded),
                    reason=f"Expression '{before}' only involves literals and was evaluated to {render(folded)}.",
                    target="expression",
                )
            )
            return folded
        return node
