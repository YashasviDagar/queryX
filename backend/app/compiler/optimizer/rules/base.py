"""Base class for rule-based optimizer transformations."""
from __future__ import annotations

from ...ir import nodes as ir
from ..context import OptimizerContext
from ..records import RuleFinding


class Rule:
    name: str = "Rule"
    description: str = ""

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        raise NotImplementedError
