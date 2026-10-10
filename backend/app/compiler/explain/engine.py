"""Explainability engine.

Turns optimization records and plan evaluations into human-readable
explanations. This is the project's primary novelty: the optimizer never
changes a plan without saying *what* it changed, *why*, and *what the estimated
impact was*.
"""
from __future__ import annotations

from typing import Any

from ..optimizer.records import OptimizationRecord
from ..planner.selector import SelectionResult


class ExplainEngine:
    # -- per-rule explanations ----------------------------------------------
    def explain_optimizations(self, records: list[OptimizationRecord]) -> list[dict[str, Any]]:
        explanations: list[dict[str, Any]] = []
        for record in records:
            impact = record.estimated_impact
            rows_before = impact.get("estimatedRowsBefore", 0)
            rows_after = impact.get("estimatedRowsAfter", 0)
            cost_before = impact.get("estimatedCostBefore", 0)
            cost_after = impact.get("estimatedCostAfter", 0)
            pct = impact.get("rowReductionPercent", 0)
            metric_label = impact.get("metricLabel", "estimated plan output rows")

            narrative = (
                f"{record.rule} was applied to the {record.target or 'plan'}. "
                f"{record.reason} "
                f"The {metric_label} changed from {rows_before:,.0f} to {rows_after:,.0f} "
                f"({pct:.1f}% reduction) and the estimated logical cost changed from "
                f"{cost_before:,.2f} to {cost_after:,.2f}."
            )
            explanations.append(
                {
                    "rule": record.rule,
                    "target": record.target,
                    "before": record.before,
                    "after": record.after,
                    "reason": record.reason,
                    "metricLabel": metric_label,
                    "estimatedRowsBefore": rows_before,
                    "estimatedRowsAfter": rows_after,
                    "rowReduction": impact.get("rowReduction", 0),
                    "rowReductionPercent": pct,
                    "estimatedCostBefore": cost_before,
                    "estimatedCostAfter": cost_after,
                    "costReduction": impact.get("costReduction", 0),
                    "narrative": narrative,
                }
            )
        return explanations

    # -- plan selection explanation -----------------------------------------
    def explain_selection(self, selection: SelectionResult) -> dict[str, Any]:
        if selection.selected is None:
            return {
                "selectedPlan": None,
                "reason": "No valid candidate plan could be generated.",
                "comparison": [],
            }

        ranked = sorted(selection.evaluations, key=lambda e: e.estimated_cost)
        winner = ranked[0]
        others = ranked[1:]

        if others:
            comparisons = ", ".join(
                f"{o.candidate.name} ({o.estimated_cost:,.2f})" for o in others
            )
            reason = (
                f"{winner.candidate.name} was selected because its estimated cost of "
                f"{winner.estimated_cost:,.2f} is lower than {comparisons}. "
                f"It uses {winner.candidate.description} and is estimated to produce "
                f"{winner.estimated_rows:,.0f} rows."
            )
        else:
            reason = (
                f"{winner.candidate.name} was selected as the only valid candidate, "
                f"with an estimated cost of {winner.estimated_cost:,.2f}."
            )

        savings = None
        if others:
            savings = round(others[0].estimated_cost - winner.estimated_cost, 2)

        return {
            "selectedPlan": winner.candidate.name,
            "selectedPlanId": winner.candidate.plan_id,
            "reason": reason,
            "estimatedCost": round(winner.estimated_cost, 2),
            "estimatedRows": round(winner.estimated_rows, 2),
            "estimatedMemory": round(winner.estimated_memory, 2),
            "estimatedOperations": round(winner.estimated_operations, 2),
            "savingsVsNextBest": savings,
            "comparison": selection.cost_comparison,
        }

    # -- whole-pipeline summary ---------------------------------------------
    def summary(
        self,
        optimization_count: int,
        rules_used: list[str],
        selection: SelectionResult,
    ) -> str:
        if selection.selected is None:
            return "The query was analyzed but no candidate plan could be generated."
        return (
            f"Applied {optimization_count} optimization step(s) using "
            f"{len(rules_used)} rule(s) ({', '.join(rules_used) or 'none'}). "
            f"{len(selection.evaluations)} candidate physical plan(s) were costed and "
            f"{selection.selected.candidate.name} was chosen with an estimated cost of "
            f"{selection.selected.estimated_cost:,.2f}."
        )

    def explain(
        self,
        records: list[OptimizationRecord],
        selection: SelectionResult,
        rules_used: list[str],
    ) -> dict[str, Any]:
        return {
            "summary": self.summary(len(records), rules_used, selection),
            "optimizationExplanations": self.explain_optimizations(records),
            "planSelection": self.explain_selection(selection),
        }
