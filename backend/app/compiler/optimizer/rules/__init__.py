"""Default optimizer rule pipeline.

Order matters: constant folding and redundant-condition removal simplify the
predicates, predicate pushdown moves them next to the scans, projection pruning
narrows tuple width, and join reordering picks a cheaper join order.
"""
from __future__ import annotations

from .base import Rule
from .constant_folding import ConstantFolding
from .join_reordering import JoinReordering
from .predicate_pushdown import PredicatePushdown
from .projection_pruning import ProjectionPruning
from .redundant_conditions import RedundantConditionRemoval


def default_rules() -> list[Rule]:
    return [
        ConstantFolding(),
        RedundantConditionRemoval(),
        PredicatePushdown(),
        ProjectionPruning(),
        JoinReordering(),
    ]


__all__ = [
    "Rule",
    "ConstantFolding",
    "RedundantConditionRemoval",
    "PredicatePushdown",
    "ProjectionPruning",
    "JoinReordering",
    "default_rules",
]
