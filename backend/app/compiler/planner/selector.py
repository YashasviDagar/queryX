"""Cost-based plan selection.

Estimates every candidate plan with the cost model and selects the plan with
the lowest estimated cost, while keeping all candidates for comparison.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from ..cost.model import CostEstimator
from .generator import PlanCandidate


@dataclass
class PlanEvaluation:
    candidate: PlanCandidate
    estimated_cost: float
    estimated_rows: float
    estimated_memory: float
    estimated_operations: float
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.candidate.plan_id,
            "name": self.candidate.name,
            "description": self.candidate.description,
            "joinOrder": self.candidate.join_order,
            "joinAlgorithm": self.candidate.join_algorithm,
            "accessPaths": self.candidate.access_paths,
            "estimatedCost": round(self.estimated_cost, 2),
            "estimatedRows": round(self.estimated_rows, 2),
            "estimatedMemory": round(self.estimated_memory, 2),
            "estimatedOperations": round(self.estimated_operations, 2),
            "selected": self.selected,
            "tree": self.candidate.tree.to_dict(),
        }


@dataclass
class SelectionResult:
    evaluations: list[PlanEvaluation] = field(default_factory=list)
    selected: PlanEvaluation | None = None

    @property
    def cost_comparison(self) -> list[dict[str, Any]]:
        ranked = sorted(self.evaluations, key=lambda e: e.estimated_cost)
        return [
            {
                "id": e.candidate.plan_id,
                "name": e.candidate.name,
                "description": e.candidate.description,
                "joinAlgorithm": e.candidate.join_algorithm,
                "estimatedCost": round(e.estimated_cost, 2),
                "estimatedRows": round(e.estimated_rows, 2),
                "estimatedMemory": round(e.estimated_memory, 2),
                "estimatedOperations": round(e.estimated_operations, 2),
                "selected": e.selected,
            }
            for e in ranked
        ]


class PlanSelector:
    def __init__(self, estimator: CostEstimator) -> None:
        self.estimator = estimator

    def evaluate(self, candidates: list[PlanCandidate]) -> SelectionResult:
        evaluations: list[PlanEvaluation] = []
        for candidate in candidates:
            tree = copy.deepcopy(candidate.tree)
            self.estimator.estimate(tree)
            candidate.tree = tree
            evaluations.append(
                PlanEvaluation(
                    candidate=candidate,
                    estimated_cost=tree.estimated_cost,
                    estimated_rows=tree.estimated_rows,
                    estimated_memory=tree.total_memory(),
                    estimated_operations=tree.estimated_operations,
                )
            )

        result = SelectionResult(evaluations=evaluations)
        if evaluations:
            best = min(evaluations, key=lambda e: (e.estimated_cost, e.estimated_operations))
            best.selected = True
            result.selected = best
        return result
