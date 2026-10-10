"""Typed Abstract Syntax Tree (AST) nodes.

Every node is a dataclass carrying an optional source position so the semantic
analyzer and frontend can point at the exact location of a construct.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Node:
    line: int = field(default=0, kw_only=True)
    col: int = field(default=0, kw_only=True)

    kind: str = field(default="Node", init=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


def _pos(node: "Node") -> dict[str, int]:
    return {"line": node.line, "column": node.col}


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------
@dataclass
class Literal(Node):
    value: Any = None
    literal_type: str = "unknown"

    def __post_init__(self) -> None:
        self.kind = "Literal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "literalType": self.literal_type,
            **_pos(self),
        }


@dataclass
class Column(Node):
    name: str = ""
    table: Optional[str] = None
    alias: Optional["Alias"] = None

    def __post_init__(self) -> None:
        self.kind = "Column"

    @property
    def qualified_name(self) -> str:
        return f"{self.table}.{self.name}" if self.table else self.name

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "table": self.table,
            "alias": self.alias.to_dict() if self.alias else None,
            **_pos(self),
        }


@dataclass
class Alias(Node):
    name: str = ""

    def __post_init__(self) -> None:
        self.kind = "Alias"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, **_pos(self)}


@dataclass
class Table(Node):
    name: str = ""
    alias: Optional[Alias] = None

    def __post_init__(self) -> None:
        self.kind = "Table"

    @property
    def effective_name(self) -> str:
        return self.alias.name if self.alias else self.name

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "alias": self.alias.to_dict() if self.alias else None,
            **_pos(self),
        }


@dataclass
class BinaryExpression(Node):
    left: Optional[Node] = None
    operator: str = ""
    right: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "BinaryExpression"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "operator": self.operator,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
            **_pos(self),
        }


@dataclass
class Comparison(Node):
    left: Optional[Node] = None
    operator: str = ""
    right: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "Comparison"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "operator": self.operator,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
            **_pos(self),
        }


@dataclass
class LogicalExpression(Node):
    left: Optional[Node] = None
    operator: str = ""
    right: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "LogicalExpression"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "operator": self.operator,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
            **_pos(self),
        }


@dataclass
class FunctionCall(Node):
    name: str = ""
    args: list[Node] = field(default_factory=list)
    distinct: bool = False
    star: bool = False
    alias: Optional["Alias"] = None

    def __post_init__(self) -> None:
        self.kind = "FunctionCall"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "distinct": self.distinct,
            "star": self.star,
            "alias": self.alias.to_dict() if self.alias else None,
            "args": [a.to_dict() for a in self.args],
            **_pos(self),
        }


# ---------------------------------------------------------------------------
# Query clauses
# ---------------------------------------------------------------------------
@dataclass
class Select(Node):
    columns: list[Node] = field(default_factory=list)
    distinct: bool = False

    def __post_init__(self) -> None:
        self.kind = "Select"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "distinct": self.distinct,
            "columns": [c.to_dict() for c in self.columns],
            **_pos(self),
        }


@dataclass
class From(Node):
    table: Optional[Table] = None

    def __post_init__(self) -> None:
        self.kind = "From"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "table": self.table.to_dict() if self.table else None,
            **_pos(self),
        }


@dataclass
class Join(Node):
    join_type: str = "INNER"
    table: Optional[Table] = None
    condition: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "Join"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "joinType": self.join_type,
            "table": self.table.to_dict() if self.table else None,
            "condition": self.condition.to_dict() if self.condition else None,
            **_pos(self),
        }


@dataclass
class Where(Node):
    condition: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "Where"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "condition": self.condition.to_dict() if self.condition else None,
            **_pos(self),
        }


@dataclass
class GroupBy(Node):
    columns: list[Node] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.kind = "GroupBy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "columns": [c.to_dict() for c in self.columns],
            **_pos(self),
        }


@dataclass
class Having(Node):
    condition: Optional[Node] = None

    def __post_init__(self) -> None:
        self.kind = "Having"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "condition": self.condition.to_dict() if self.condition else None,
            **_pos(self),
        }


@dataclass
class OrderByItem(Node):
    column: Optional[Node] = None
    direction: str = "ASC"

    def __post_init__(self) -> None:
        self.kind = "OrderByItem"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "column": self.column.to_dict() if self.column else None,
            "direction": self.direction,
            **_pos(self),
        }


@dataclass
class OrderBy(Node):
    items: list[OrderByItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.kind = "OrderBy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "items": [i.to_dict() for i in self.items],
            **_pos(self),
        }


@dataclass
class Limit(Node):
    count: int = 0

    def __post_init__(self) -> None:
        self.kind = "Limit"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "count": self.count, **_pos(self)}


@dataclass
class Query(Node):
    select: Optional[Select] = None
    from_clause: Optional[From] = None
    joins: list[Join] = field(default_factory=list)
    where: Optional[Where] = None
    group_by: Optional[GroupBy] = None
    having: Optional[Having] = None
    order_by: Optional[OrderBy] = None
    limit: Optional[Limit] = None

    def __post_init__(self) -> None:
        self.kind = "Query"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "select": self.select.to_dict() if self.select else None,
            "from": self.from_clause.to_dict() if self.from_clause else None,
            "joins": [j.to_dict() for j in self.joins],
            "where": self.where.to_dict() if self.where else None,
            "groupBy": self.group_by.to_dict() if self.group_by else None,
            "having": self.having.to_dict() if self.having else None,
            "orderBy": self.order_by.to_dict() if self.order_by else None,
            "limit": self.limit.to_dict() if self.limit else None,
            **_pos(self),
        }
