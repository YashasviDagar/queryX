"""Rule-based optimizer engine.

Applies each rule in a fixed order, capturing an :class:`OptimizationRecord`
for every transformation together with the estimated row-count impact.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..cost.config import CostConfig
from ..cost.logical import estimate_ir_cost, estimate_ir_rows
from ..cost.statistics import StatsStore
from ..ir import nodes as ir
from ..ir.expr import ExprContext
from .context import OptimizerContext
from .records import OptimizationRecord
from .rules import default_rules


@dataclass
class OptimizeResult:
    root: ir.IRNode
    records: list[OptimizationRecord] = field(default_factory=list)

    @property
    def rules_applied(self) -> int:
        return len(self.records)

    def rules_used(self) -> list[str]:
        seen: list[str] = []
        for record in self.records:
            if record.rule not in seen:
                seen.append(record.rule)
        return seen


class OptimizerEngine:
    def __init__(
        self,
        stats: StatsStore,
        config: CostConfig,
        expr_ctx: ExprContext,
        rules=None,
    ) -> None:
        self.ctx = OptimizerContext(stats, config, expr_ctx)
        self.rules = rules if rules is not None else default_rules()

    def optimize(self, root: ir.IRNode) -> OptimizeResult:
        current = copy.deepcopy(root)
        records: list[OptimizationRecord] = []
        estimator = self.ctx.cardinality

        for rule in self.rules:
            before_rows = estimate_ir_rows(current, estimator)
            before_cost = estimate_ir_cost(current, estimator, self.ctx.config)
            new_root, findings = rule.apply(current, self.ctx)
            after_rows = estimate_ir_rows(new_root, estimator)
            after_cost = estimate_ir_cost(new_root, estimator, self.ctx.config)

            reduction = before_rows - after_rows
            percent = (reduction / before_rows * 100.0) if before_rows else 0.0
            for finding in findings:
                impact = {
                    "metricLabel": finding.metric_label or "estimated plan output rows",
                    "estimatedRowsBefore": round(before_rows, 2),
                    "estimatedRowsAfter": round(after_rows, 2),
                    "rowReduction": round(reduction, 2),
                    "rowReductionPercent": round(percent, 2),
                    "estimatedCostBefore": round(before_cost, 2),
                    "estimatedCostAfter": round(after_cost, 2),
                    "costReduction": round(before_cost - after_cost, 2),
                }
                if finding.impact:
                    impact.update(finding.impact)
                    if "estimatedRowsBefore" in finding.impact or "estimatedRowsAfter" in finding.impact:
                        rows_b = impact["estimatedRowsBefore"]
                        rows_a = impact["estimatedRowsAfter"]
                        impact["rowReduction"] = round(rows_b - rows_a, 2)
                        impact["rowReductionPercent"] = (
                            round((rows_b - rows_a) / rows_b * 100.0, 2) if rows_b else 0.0
                        )
                records.append(
                    OptimizationRecord(
                        rule=finding.rule,
                        before=finding.before,
                        after=finding.after,
                        reason=finding.reason,
                        target=finding.target,
                        estimated_impact=impact,
                    )
                )
            current = new_root

        return OptimizeResult(root=current, records=records)
