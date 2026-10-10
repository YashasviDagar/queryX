"""Optimizer execution context shared by all rules."""
from __future__ import annotations

from dataclasses import dataclass

from ..cost.cardinality import CardinalityEstimator
from ..cost.config import CostConfig
from ..cost.statistics import StatsStore
from ..ir.expr import ExprContext


@dataclass
class OptimizerContext:
    stats: StatsStore
    config: CostConfig
    expr: ExprContext

    @property
    def cardinality(self) -> CardinalityEstimator:
        return CardinalityEstimator(self.stats, self.config, self.expr)
