"""Semantic analyzer.

Validates the AST against the catalog and resolves every column reference to a
concrete (table, column, type) triple. Unlike the lexer/parser, the analyzer
collects *all* errors instead of failing on the first one, producing a list of
compiler-style diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..ast import nodes as ast
from ..lexer.errors import CompilerError
from .catalog import Catalog, ColumnDef, TableDef

_AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
_NUMERIC_TYPES = {"integer", "float", "bigint", "numeric"}
_STRING_TYPES = {"text", "varchar", "char", "character", "string"}
_COMPARISON_OPS = {"=", "<>", "<", "<=", ">", ">="}
_ARITHMETIC_OPS = {"+", "-", "*", "/", "%"}


def _type_category(data_type: str) -> str:
    if data_type in _NUMERIC_TYPES:
        return "numeric"
    if data_type in _STRING_TYPES:
        return "string"
    return data_type


@dataclass
class ResolvedColumn:
    table: str
    name: str
    data_type: str
    alias: Optional[str] = None

    @property
    def qualified(self) -> str:
        return f"{self.table}.{self.name}"


@dataclass
class OutputColumn:
    name: str
    table: Optional[str]
    data_type: str
    source: str
    aggregate: bool = False


@dataclass
class SemanticResult:
    valid: bool = True
    errors: list[CompilerError] = field(default_factory=list)
    output_columns: list[OutputColumn] = field(default_factory=list)
    resolution: dict[int, ResolvedColumn] = field(default_factory=dict)
    scope: dict[str, str] = field(default_factory=dict)  # alias -> table name
    referenced_tables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "outputColumns": [
                {
                    "name": c.name,
                    "table": c.table,
                    "dataType": c.data_type,
                    "source": c.source,
                    "aggregate": c.aggregate,
                }
                for c in self.output_columns
            ],
            "scope": self.scope,
            "referencedTables": self.referenced_tables,
        }


class SemanticAnalyzer:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.errors: list[CompilerError] = []
        self.scope: dict[str, TableDef] = {}
        self.scope_order: list[str] = []
        self.resolution: dict[int, ResolvedColumn] = {}
        self.referenced_tables: list[str] = []

    # -- diagnostics ---------------------------------------------------------
    def _err(self, code: str, message: str, node: ast.Node, suggestion: Optional[str] = None) -> None:
        self.errors.append(
            CompilerError(
                code=code,
                message=message,
                stage="semantic",
                line=node.line,
                column=node.col,
                suggestion=suggestion,
            )
        )

    # -- scope ---------------------------------------------------------------
    def _add_table(self, table: ast.Table) -> None:
        name = table.name.lower()
        alias = table.alias.name if table.alias else None
        key = (alias or name).lower()

        if alias and key in self.scope:
            self._err(
                "SEM001",
                f"Duplicate alias '{alias}'. Alias '{alias}' is already bound to table '{self.scope[key].name}'.",
                table.alias or table,
                suggestion="Use a unique alias for each table reference.",
            )
            return

        if not self.catalog.exists(name):
            self._err(
                "SEM002",
                f"Unknown table '{table.name}'.",
                table,
                suggestion=f"Available tables: {', '.join(self.catalog.table_names())}.",
            )
            return

        tdef = self.catalog.get(name)
        assert tdef is not None
        self.scope[key] = tdef
        self.scope_order.append(key)
        if tdef.name not in self.referenced_tables:
            self.referenced_tables.append(tdef.name)

    # -- column resolution ---------------------------------------------------
    def _resolve(self, column: ast.Column) -> Optional[ResolvedColumn]:
        if column.name == "*":
            return None

        if column.table:
            key = column.table.lower()
            tdef = self.scope.get(key)
            if tdef is None:
                self._err(
                    "SEM003",
                    f"Unknown table or alias '{column.table}' used to qualify column '{column.name}'.",
                    column,
                    suggestion=f"Known aliases/tables: {', '.join(self.scope_order) or 'none'}.",
                )
                return None
            cdef = tdef.column(column.name)
            if cdef is None:
                self._err(
                    "SEM004",
                    f"Column '{column.name}' does not exist in table '{tdef.name}'.",
                    column,
                    suggestion=f"Available columns: {', '.join(tdef.column_names())}.",
                )
                return None
            resolved = ResolvedColumn(tdef.name, cdef.name, cdef.data_type)
            self.resolution[id(column)] = resolved
            return resolved

        # unqualified: search the whole scope
        matches: list[tuple[TableDef, ColumnDef]] = []
        for tdef in self.scope.values():
            cdef = tdef.column(column.name)
            if cdef is not None:
                matches.append((tdef, cdef))

        if not matches:
            self._err(
                "SEM005",
                f"Unknown column '{column.name}'.",
                column,
                suggestion="Check the column name or qualify it with a table alias.",
            )
            return None
        if len(matches) > 1:
            tables = ", ".join(t.name for t, _ in matches)
            self._err(
                "SEM006",
                f"Ambiguous column '{column.name}' exists in multiple tables: {tables}.",
                column,
                suggestion="Qualify the column with a table alias, e.g. 'alias.column'.",
            )
            return None
        tdef, cdef = matches[0]
        resolved = ResolvedColumn(tdef.name, cdef.name, cdef.data_type)
        self.resolution[id(column)] = resolved
        return resolved

    # -- expression typing ---------------------------------------------------
    def _type_of(self, node: ast.Node, inside_aggregate: bool = False) -> str:
        if isinstance(node, ast.Literal):
            if node.literal_type in ("integer", "float"):
                return "numeric"
            if node.literal_type == "string":
                return "string"
            return "unknown"

        if isinstance(node, ast.Column):
            resolved = self._resolve(node)
            return resolved.data_type if resolved else "unknown"

        if isinstance(node, ast.FunctionCall):
            if node.name not in _AGGREGATES:
                self._err(
                    "SEM007",
                    f"Unknown function '{node.name}'.",
                    node,
                    suggestion=f"Supported functions: {', '.join(sorted(_AGGREGATES))}.",
                )
                return "unknown"
            if node.star and node.name != "COUNT":
                self._err(
                    "SEM008",
                    f"Function '{node.name}(*)' is not allowed. Only COUNT(*) supports '*'.",
                    node,
                    suggestion=f"Provide an explicit column argument to {node.name}.",
                )
            if node.args:
                arg_type = self._type_of(node.args[0], inside_aggregate=True)
                if node.name in {"SUM", "AVG"} and arg_type not in _NUMERIC_TYPES and arg_type != "unknown":
                    self._err(
                        "SEM009",
                        f"Function {node.name} requires a numeric argument but received '{arg_type}'.",
                        node,
                        suggestion="Use SUM/AVG on numeric columns such as cgpa or credits.",
                    )
            return "numeric" if node.name in {"COUNT", "SUM", "AVG"} else "unknown"

        if isinstance(node, ast.Comparison):
            left = self._type_of(node.left, inside_aggregate) if node.left else "unknown"
            right = self._type_of(node.right, inside_aggregate) if node.right else "unknown"
            if left != "unknown" and right != "unknown":
                left_cat = _type_category(left)
                right_cat = _type_category(right)
                if left_cat != right_cat:
                    self._err(
                        "SEM010",
                        f"Cannot compare incompatible types '{left}' and '{right}' with '{node.operator}'.",
                        node,
                        suggestion="Compare values of the same type (numeric with numeric, string with string).",
                    )
            return "boolean"

        if isinstance(node, ast.LogicalExpression):
            self._type_of(node.left, inside_aggregate)
            self._type_of(node.right, inside_aggregate)
            return "boolean"

        if isinstance(node, ast.BinaryExpression):
            if node.operator == "NOT":
                self._type_of(node.right, inside_aggregate)
                return "boolean"
            left = self._type_of(node.left, inside_aggregate) if node.left else "unknown"
            right = self._type_of(node.right, inside_aggregate) if node.right else "unknown"
            if node.operator in _ARITHMETIC_OPS:
                if (left not in _NUMERIC_TYPES and left != "unknown") or (
                    right not in _NUMERIC_TYPES and right != "unknown"
                ):
                    self._err(
                        "SEM011",
                        f"Arithmetic operator '{node.operator}' requires numeric operands but received '{left}' and '{right}'.",
                        node,
                        suggestion="Use arithmetic only on numeric columns.",
                    )
                return "numeric"
            return "unknown"

        return "unknown"

    def _collect_aggregates(self, node: Optional[ast.Node]) -> list[ast.FunctionCall]:
        found: list[ast.FunctionCall] = []
        if node is None:
            return found
        if isinstance(node, ast.FunctionCall):
            if node.name in _AGGREGATES:
                found.append(node)
            for a in node.args:
                found.extend(self._collect_aggregates(a))
        elif isinstance(node, ast.BinaryExpression):
            found.extend(self._collect_aggregates(node.left))
            found.extend(self._collect_aggregates(node.right))
        elif isinstance(node, ast.Comparison):
            found.extend(self._collect_aggregates(node.left))
            found.extend(self._collect_aggregates(node.right))
        elif isinstance(node, ast.LogicalExpression):
            found.extend(self._collect_aggregates(node.left))
            found.extend(self._collect_aggregates(node.right))
        return found

    def _collect_columns(self, node: Optional[ast.Node]) -> list[ast.Column]:
        found: list[ast.Column] = []
        if node is None:
            return found
        if isinstance(node, ast.Column):
            found.append(node)
        elif isinstance(node, ast.FunctionCall):
            for a in node.args:
                found.extend(self._collect_columns(a))
        elif isinstance(node, ast.BinaryExpression):
            found.extend(self._collect_columns(node.left))
            found.extend(self._collect_columns(node.right))
        elif isinstance(node, ast.Comparison):
            found.extend(self._collect_columns(node.left))
            found.extend(self._collect_columns(node.right))
        elif isinstance(node, ast.LogicalExpression):
            found.extend(self._collect_columns(node.left))
            found.extend(self._collect_columns(node.right))
        return found

    # -- main ----------------------------------------------------------------
    def analyze(self, query: ast.Query) -> SemanticResult:
        # 1. Build scope from FROM + JOINs
        if query.from_clause and query.from_clause.table:
            self._add_table(query.from_clause.table)
        for join in query.joins:
            if join.table:
                self._add_table(join.table)

        if not self.scope and not self.errors:
            self._err(
                "SEM012",
                "Query must reference at least one valid table.",
                query,
                suggestion="Add a FROM clause with an existing table.",
            )

        # 2. Join conditions
        for join in query.joins:
            if join.join_type != "INNER":
                self._err(
                    "SEM017",
                    f"Outer joins ({join.join_type} JOIN) are not supported by the queryX optimizer.",
                    join,
                    suggestion="Rewrite the query using INNER JOIN, which the cost-based optimizer can reorder and plan.",
                )
                continue
            if join.condition is None:
                self._err(
                    "SEM013",
                    "JOIN is missing an ON condition.",
                    join,
                    suggestion="Add 'ON <left.column> = <right.column>'.",
                )
                continue
            if not isinstance(join.condition, ast.Comparison):
                self._err(
                    "SEM014",
                    "JOIN condition must be a comparison between columns of the joined tables.",
                    join.condition,
                    suggestion="Use 'ON left_table.column = right_table.column'.",
                )
            self._type_of(join.condition)

        # 3. WHERE
        if query.where and query.where.condition:
            aggs = self._collect_aggregates(query.where.condition)
            for agg in aggs:
                self._err(
                    "SEM015",
                    f"Aggregate function '{agg.name}' is not allowed in WHERE.",
                    agg,
                    suggestion="Move the aggregate into the SELECT list and filter groups with GROUP BY.",
                )
            self._type_of(query.where.condition)

        # 4. GROUP BY columns
        group_keys: set[str] = set()
        if query.group_by:
            for col in query.group_by.columns:
                resolved = self._resolve(col)
                if resolved:
                    group_keys.add(resolved.qualified)

        # 5. SELECT list
        output_columns: list[OutputColumn] = []
        select = query.select
        has_aggregate = False
        if select:
            # Pre-pass: does any select item contain an aggregate function?
            for item in select.columns:
                if self._collect_aggregates(item):
                    has_aggregate = True
                    break

            for item in select.columns:
                if isinstance(item, ast.Column) and item.name == "*":
                    if has_aggregate:
                        self._err(
                            "SEM016",
                            "SELECT * cannot be combined with aggregate functions.",
                            item,
                            suggestion="List the grouped columns explicitly, or remove the aggregate function.",
                        )
                    for tdef in self.scope.values():
                        for cdef in tdef.columns.values():
                            output_columns.append(
                                OutputColumn(cdef.name, tdef.name, cdef.data_type, f"{tdef.name}.{cdef.name}")
                            )
                    continue
                item_type = self._type_of(item)
                if isinstance(item, ast.Column):
                    resolved = self._resolve(item)
                    if resolved:
                        alias = item.alias.name if item.alias else None
                        output_columns.append(
                            OutputColumn(
                                alias or resolved.name,
                                resolved.table,
                                resolved.data_type,
                                resolved.qualified,
                            )
                        )
                        # aggregate/group-by validation
                        if (has_aggregate or group_keys) and resolved.qualified not in group_keys:
                            self._err(
                                "SEM016",
                                f"Column '{resolved.qualified}' must appear in the GROUP BY clause or be used in an aggregate function.",
                                item,
                                suggestion=f"Add '{resolved.qualified}' to GROUP BY.",
                            )
                else:
                    name = item.alias.name if isinstance(item, ast.Column) and item.alias else item.kind
                    if isinstance(item, ast.FunctionCall):
                        out_name = item.alias.name if item.alias else item.name.lower()
                        output_columns.append(
                            OutputColumn(out_name, None, item_type, item.name, aggregate=True)
                        )
                    else:
                        output_columns.append(OutputColumn(name, None, item_type, item.kind))

        # 6. ORDER BY (may reference select aliases/output names)
        if query.order_by:
            orderable_names: set[str] = set()
            for out in output_columns:
                orderable_names.add(out.name.lower())
                if out.source and "." in out.source:
                    orderable_names.add(out.source.split(".")[-1].lower())
            for order_item in query.order_by.items:
                column = order_item.column
                if column is None:
                    continue
                if not column.table and column.name.lower() in orderable_names:
                    continue
                self._resolve(column)

        valid = not self.errors
        return SemanticResult(
            valid=valid,
            errors=self.errors,
            output_columns=output_columns,
            resolution=self.resolution,
            scope={k: v.name for k, v in self.scope.items()},
            referenced_tables=self.referenced_tables,
        )
