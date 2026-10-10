"""Physical plan node definitions.

A physical plan is a tree of concrete access/execution operators (sequential
scan, index scan, nested-loop/hash/merge join, sort, aggregate, ...). Cost
fields are populated by :class:`~app.compiler.cost.model.CostEstimator`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..ir.nodes import IRNode


@dataclass
class PhysicalNode:
    op: str
    details: dict[str, Any] = field(default_factory=dict)
    children: list["PhysicalNode"] = field(default_factory=list)
    estimated_rows: float = 0.0
    estimated_cost: float = 0.0
    estimated_memory: float = 0.0
    estimated_operations: float = 0.0
    logical: Optional[IRNode] = None

    def label(self) -> str:
        op = self.op
        d = self.details
        if op == "SeqScan":
            cols = d.get("columns")
            col_text = "*" if not cols else ", ".join(cols)
            return f"Sequential Scan on {d.get('table')}" + (f" [{col_text}]" if cols is not None else "")
        if op == "IndexScan":
            return f"Index Scan on {d.get('table')} using {d.get('index')}"
        if op == "Filter":
            return f"Filter {d.get('conditionText', '')}"
        if op in ("NestedLoopJoin", "HashJoin", "MergeJoin"):
            return f"{op} ({d.get('joinType', 'INNER')}) on {d.get('conditionText', '')}"
        if op == "Sort":
            return f"Sort {d.get('keys', '')}"
        if op == "Aggregate":
            return f"Aggregate {d.get('text', '')}"
        if op == "Project":
            return f"Project {d.get('columns', '')}"
        if op == "Distinct":
            cols = d.get("columns")
            return "Hash Distinct" + (f" [{cols}]" if cols else "")
        if op == "Limit":
            return f"Limit {d.get('count', '')}"
        return op

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "label": self.label(),
            "details": self.details,
            "estimatedRows": round(self.estimated_rows, 2),
            "estimatedCost": round(self.estimated_cost, 2),
            "estimatedMemory": round(self.estimated_memory, 2),
            "estimatedOperations": round(self.estimated_operations, 2),
            "children": [c.to_dict() for c in self.children],
        }

    def total_memory(self) -> float:
        return max(
            [self.estimated_memory] + [c.total_memory() for c in self.children]
        )

    def to_lines(self, indent: int = 0) -> list[str]:
        lines = ["  " * indent + self.label()]
        for child in self.children:
            lines.extend(child.to_lines(indent + 1))
        return lines
