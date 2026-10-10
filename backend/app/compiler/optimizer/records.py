"""Data structures describing an optimization transformation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptimizationRecord:
    rule: str
    before: str
    after: str
    reason: str
    estimated_impact: dict[str, Any] = field(default_factory=dict)
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "estimatedImpact": self.estimated_impact,
        }


@dataclass
class RuleFinding:
    """A single transformation produced by a rule."""

    rule: str
    before: str
    after: str
    reason: str
    target: str = ""
    impact: dict[str, Any] = field(default_factory=dict)
    metric_label: str = ""
