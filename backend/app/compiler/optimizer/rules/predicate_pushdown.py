"""Predicate pushdown: move filters closer to the scans they depend on."""
from __future__ import annotations

from ...ir import nodes as ir
from ...ir.expr import combine_and, conjuncts, contains_aggregate, referenced_sources, render
from ...cost.logical import estimate_ir_rows
from ..context import OptimizerContext
from ..records import RuleFinding
from .base import Rule


class PredicatePushdown(Rule):
    name = "Predicate Pushdown"
    description = (
        "Move WHERE predicates down the plan so they are evaluated as close to "
        "the base tables as possible, shrinking the number of rows that flow "
        "into joins and aggregations."
    )

    def apply(self, root: ir.IRNode, ctx: OptimizerContext) -> tuple[ir.IRNode, list[RuleFinding]]:
        findings: list[RuleFinding] = []
        new_root = self._visit(root, ctx, findings)
        return new_root, findings

    # -- traversal -----------------------------------------------------------
    def _visit(self, node: ir.IRNode, ctx: OptimizerContext, findings: list[RuleFinding]) -> ir.IRNode:
        if isinstance(node, ir.Filter):
            child = self._visit(node.children[0], ctx, findings)
            return self._push_down(child, conjuncts(node.condition), ctx, findings, origin="WHERE")

        node.children = [self._visit(c, ctx, findings) for c in node.children]
        if isinstance(node, ir.Join):
            node.left, node.right = node.children[0], node.children[1]
        return node

    # -- pushdown ------------------------------------------------------------
    def _push_down(
        self,
        node: ir.IRNode,
        predicates: list,
        ctx: OptimizerContext,
        findings: list[RuleFinding],
        origin: str = "WHERE",
    ) -> ir.IRNode:
        if not predicates:
            return node

        if isinstance(node, ir.Join):
            left, right = node.left, node.right
            assert left is not None and right is not None
            left_sources = referenced_sources_ir(left, ctx)
            right_sources = referenced_sources_ir(right, ctx)

            left_preds, right_preds, join_preds, stay = [], [], [], []
            for pred in predicates:
                refs = referenced_sources(pred, ctx.expr)
                if refs and refs <= left_sources:
                    left_preds.append(pred)
                elif refs and refs <= right_sources:
                    right_preds.append(pred)
                elif refs and (refs & left_sources) and (refs & right_sources):
                    join_preds.append(pred)
                else:
                    stay.append(pred)

            new_left = self._push_down(left, left_preds, ctx, findings, origin)
            new_right = self._push_down(right, right_preds, ctx, findings, origin)
            condition = combine_and(conjuncts(node.condition) + join_preds)
            result: ir.IRNode = ir.Join(
                left=new_left,
                right=new_right,
                condition=condition,
                join_type=node.join_type,
                output_columns=list(node.output_columns),
            )

            # Operator-level impact: rows flowing through the join before/after.
            estimator = ctx.cardinality
            left_before = estimate_ir_rows(left, estimator)
            right_before = estimate_ir_rows(right, estimator)
            left_after = estimate_ir_rows(new_left, estimator)
            right_after = estimate_ir_rows(new_right, estimator)
            if left_preds or right_preds:
                impact = {
                    "estimatedRowsBefore": round(left_before + right_before, 2),
                    "estimatedRowsAfter": round(left_after + right_after, 2),
                }
                metric_label = "rows entering the join"
            else:
                impact = {
                    "estimatedRowsBefore": round(estimator.join_rows(left_before, right_before, node.condition), 2),
                    "estimatedRowsAfter": round(estimator.join_rows(left_after, right_after, condition), 2),
                }
                metric_label = "rows leaving the join"

            for pred in left_preds:
                findings.append(
                    RuleFinding(
                        rule=self.name,
                        before=f"FILTER({render(pred)}) above JOIN",
                        after=f"FILTER({render(pred)}) pushed into LEFT input",
                        reason=(
                            f"Predicate '{render(pred)}' references only {sorted(left_sources)}; "
                            "evaluating it before the join reduces the rows entering the join."
                        ),
                        target="left input",
                        impact=dict(impact),
                        metric_label=metric_label,
                    )
                )
            for pred in right_preds:
                findings.append(
                    RuleFinding(
                        rule=self.name,
                        before=f"FILTER({render(pred)}) above JOIN",
                        after=f"FILTER({render(pred)}) pushed into RIGHT input",
                        reason=(
                            f"Predicate '{render(pred)}' references only {sorted(right_sources)}; "
                            "evaluating it before the join reduces the rows entering the join."
                        ),
                        target="right input",
                        impact=dict(impact),
                        metric_label=metric_label,
                    )
                )
            for pred in join_preds:
                findings.append(
                    RuleFinding(
                        rule=self.name,
                        before=f"FILTER({render(pred)}) above JOIN",
                        after=f"JOIN ON {render(pred)}",
                        reason=(
                            f"Predicate '{render(pred)}' references columns from both inputs, "
                            "so it is folded into the join condition."
                        ),
                        target="join condition",
                        impact=dict(impact),
                        metric_label=metric_label,
                    )
                )

            if stay:
                result = ir.Filter(
                    condition=combine_and(stay),
                    children=[result],
                    output_columns=list(node.output_columns),
                )
            return result

        if isinstance(node, ir.Project):
            new_child = self._push_down(node.children[0], predicates, ctx, findings, origin)
            node.children = [new_child]
            return node

        if isinstance(node, ir.Distinct):
            new_child = self._push_down(node.children[0], predicates, ctx, findings, origin)
            return ir.Distinct(
                expressions=node.expressions,
                children=[new_child],
                output_columns=list(node.output_columns),
            )

        if isinstance(node, ir.Sort):
            new_child = self._push_down(node.children[0], predicates, ctx, findings, origin)
            return ir.Sort(
                items=node.items,
                children=[new_child],
                output_columns=list(node.output_columns),
            )

        if isinstance(node, ir.Aggregate):
            group_sources: set[str] = set()
            for group in node.group_by:
                group_sources |= referenced_sources(group, ctx.expr)
            # Only predicates over grouping keys may move below the aggregate. A
            # predicate containing an aggregate call (e.g. HAVING COUNT(*) > 2)
            # depends on the groups themselves and must stay above it.
            pushable = [
                p
                for p in predicates
                if not contains_aggregate(p)
                and referenced_sources(p, ctx.expr)
                and referenced_sources(p, ctx.expr) <= group_sources
            ]
            rest = [p for p in predicates if p not in pushable]
            new_child = (
                self._push_down(node.children[0], pushable, ctx, findings, origin)
                if pushable
                else node.children[0]
            )
            new_agg = ir.Aggregate(
                functions=node.functions,
                group_by=node.group_by,
                children=[new_child],
                output_columns=list(node.output_columns),
            )
            if rest:
                return ir.Filter(
                    condition=combine_and(rest),
                    children=[new_agg],
                    output_columns=list(node.output_columns),
                )
            return new_agg

        # Scan or Limit: materialise the predicates as a filter above the node.
        return ir.Filter(
            condition=combine_and(predicates),
            children=[node],
            output_columns=list(node.output_columns),
        )


def referenced_sources_ir(node: ir.IRNode, ctx: OptimizerContext) -> set[str]:
    from ..join_utils import referenced_sources_ir as _refs

    return _refs(node, ctx.expr)
