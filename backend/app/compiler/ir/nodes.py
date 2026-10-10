"""Relational algebra intermediate representation.

Each operator exposes its children, the columns it produces and a
human-readable label. Expressions (predicates, join conditions) are kept as AST
nodes so the optimizer can rewrite them structurally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..ast import nodes as ast


@dataclass
class IRNode:
    op: str = "IRNode"
    children: list["IRNode"] = field(default_factory=list)
    output_columns: list[str] = field(default_factory=list)

    def label(self) -> str:
        return self.op

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "label": self.label(),
            "outputColumns": self.output_columns,
            "children": [c.to_dict() for c in self.children],
        }

    def accept(self, visitor):
        for child in self.children:
            child.accept(visitor)
        return visitor(self)


@dataclass
class Scan(IRNode):
    table: str = ""
    alias: Optional[str] = None
    columns: Optional[list[str]] = None
    available_indexes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.op = "Scan"

    @property
    def source(self) -> str:
        return self.alias or self.table

    def label(self) -> str:
        cols = "*" if self.columns is None else ", ".join(self.columns)
        suffix = f" ({cols})" if self.columns is not None else ""
        return f"SCAN {self.table}" + (f" AS {self.alias}" if self.alias else "") + suffix

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "table": self.table,
                "alias": self.alias,
                "columns": self.columns,
                "availableIndexes": self.available_indexes,
            }
        )
        return data


@dataclass
class Filter(IRNode):
    condition: Optional[ast.Node] = None

    def __post_init__(self) -> None:
        self.op = "Filter"

    def label(self) -> str:
        from .expr import render

        return f"FILTER {render(self.condition)}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["condition"] = self.condition.to_dict() if self.condition else None
        return data


@dataclass
class Project(IRNode):
    expressions: list[ast.Node] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.op = "Project"

    def label(self) -> str:
        from .expr import render

        if self.expressions:
            return "PROJECT " + ", ".join(render(e) for e in self.expressions)
        return "PROJECT " + ", ".join(self.names)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["expressions"] = [e.to_dict() for e in self.expressions]
        data["names"] = self.names
        return data


@dataclass
class Join(IRNode):
    left: Optional[IRNode] = None
    right: Optional[IRNode] = None
    condition: Optional[ast.Node] = None
    join_type: str = "INNER"

    def __post_init__(self) -> None:
        self.op = "Join"
        self.children = [c for c in (self.left, self.right) if c is not None]

    def label(self) -> str:
        from .expr import render

        return f"{self.join_type} JOIN ON {render(self.condition)}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "joinType": self.join_type,
                "condition": self.condition.to_dict() if self.condition else None,
            }
        )
        return data


@dataclass
class Aggregate(IRNode):
    functions: list[ast.FunctionCall] = field(default_factory=list)
    group_by: list[ast.Column] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.op = "Aggregate"

    def label(self) -> str:
        from .expr import render

        funcs = ", ".join(render(f) for f in self.functions)
        groups = ", ".join(render(g) for g in self.group_by)
        parts = []
        if funcs:
            parts.append(funcs)
        if groups:
            parts.append(f"GROUP BY {groups}")
        return "AGGREGATE " + (" ".join(parts) if parts else "(none)")

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "functions": [f.to_dict() for f in self.functions],
                "groupBy": [g.to_dict() for g in self.group_by],
            }
        )
        return data


@dataclass
class Sort(IRNode):
    items: list[ast.OrderByItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.op = "Sort"

    def label(self) -> str:
        from .expr import render

        parts = [f"{render(i.column)} {i.direction}" for i in self.items]
        return "SORT " + ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["items"] = [i.to_dict() for i in self.items]
        return data


@dataclass
class Limit(IRNode):
    count: int = 0

    def __post_init__(self) -> None:
        self.op = "Limit"

    def label(self) -> str:
        return f"LIMIT {self.count}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["count"] = self.count
        return data


@dataclass
class Distinct(IRNode):
    expressions: list[ast.Node] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.op = "Distinct"

    def label(self) -> str:
        from .expr import render

        if self.expressions:
            return "DISTINCT " + ", ".join(render(e) for e in self.expressions)
        return "DISTINCT"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["expressions"] = [e.to_dict() for e in self.expressions]
        return data
