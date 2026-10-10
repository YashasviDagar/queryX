"""Builds the relational algebra IR from a validated AST."""
from __future__ import annotations

from typing import Optional

from ..ast import nodes as ast
from ..semantic.analyzer import ResolvedColumn, SemanticResult
from ..semantic.catalog import Catalog
from . import nodes as ir
from .expr import ExprContext, columns_in


class IRBuilder:
    def __init__(self, catalog: Catalog, semantic: SemanticResult) -> None:
        self.catalog = catalog
        self.semantic = semantic
        self.ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)

    # -- helpers -------------------------------------------------------------
    def _source_key(self, table: ast.Table) -> str:
        return (table.alias.name if table.alias else table.name).lower()

    def _scan(self, table: ast.Table) -> ir.Scan:
        tdef = self.catalog.get(table.name)
        columns = tdef.column_names() if tdef else []
        key = self._source_key(table)
        indexes = [i for i in (tdef.indexes if tdef else [])]
        return ir.Scan(
            table=table.name,
            alias=table.alias.name if table.alias else None,
            columns=None,
            available_indexes=indexes,
            output_columns=[f"{key}.{c}" for c in columns],
        )

    def _expand_star(self, child_columns: list[str]) -> list[ast.Column]:
        cols: list[ast.Column] = []
        for qualified in child_columns:
            if "." in qualified:
                table, name = qualified.split(".", 1)
                cols.append(ast.Column(name=name, table=table))
            else:
                cols.append(ast.Column(name=qualified))
        return cols

    def _collect_aggregates(self, node: Optional[ast.Node]) -> list[ast.FunctionCall]:
        found: list[ast.FunctionCall] = []
        if node is None:
            return found
        if isinstance(node, ast.FunctionCall):
            if node.name in {"COUNT", "SUM", "AVG", "MIN", "MAX"}:
                found.append(node)
            for a in node.args:
                found.extend(self._collect_aggregates(a))
        elif isinstance(node, (ast.Comparison, ast.LogicalExpression, ast.BinaryExpression)):
            found.extend(self._collect_aggregates(node.left))
            found.extend(self._collect_aggregates(node.right))
        return found

    def _projection(self, child_columns: list[str]) -> tuple[list[ast.Node], list[str]]:
        query_select = self.query.select
        expressions: list[ast.Node] = []
        names: list[str] = []
        assert query_select is not None
        for item in query_select.columns:
            if isinstance(item, ast.Column) and item.name == "*":
                for col in self._expand_star(child_columns):
                    expressions.append(col)
                    names.append(col.name)
                continue
            expressions.append(item)
            if isinstance(item, ast.Column):
                names.append(item.alias.name if item.alias else item.name)
            elif isinstance(item, ast.FunctionCall):
                names.append(item.alias.name if item.alias else item.name.lower())
            else:
                names.append(item.kind)
        return expressions, names

    # -- main ----------------------------------------------------------------
    def build(self, query: ast.Query) -> ir.IRNode:
        self.query = query
        assert query.from_clause and query.from_clause.table
        root: ir.IRNode = self._scan(query.from_clause.table)

        for join in query.joins:
            assert join.table is not None
            right = self._scan(join.table)
            root = ir.Join(
                left=root,
                right=right,
                condition=join.condition,
                join_type=join.join_type,
                output_columns=root.output_columns + right.output_columns,
            )

        if query.where and query.where.condition is not None:
            root = ir.Filter(
                condition=query.where.condition,
                children=[root],
                output_columns=list(root.output_columns),
            )

        # Aggregate / project
        select_columns = query.select.columns if query.select else []
        aggregates: list[ast.FunctionCall] = []
        for item in select_columns:
            aggregates.extend(self._collect_aggregates(item))

        if aggregates or query.group_by:
            group_by = query.group_by.columns if query.group_by else []
            group_columns = [self._qualified(c) for c in group_by]
            agg_output = sorted(set(group_columns + [f.name.lower() for f in aggregates]))
            root = ir.Aggregate(
                functions=aggregates,
                group_by=group_by,
                children=[root],
                output_columns=agg_output,
            )

        expressions, names = self._projection(root.output_columns)
        root = ir.Project(
            expressions=expressions,
            names=names,
            children=[root],
            output_columns=[n for n in names],
        )

        if query.select and query.select.distinct:
            root = ir.Distinct(
                expressions=list(expressions),
                children=[root],
                output_columns=list(root.output_columns),
            )

        if query.order_by:
            root = ir.Sort(
                items=query.order_by.items,
                children=[root],
                output_columns=list(root.output_columns),
            )

        if query.limit:
            root = ir.Limit(
                count=query.limit.count,
                children=[root],
                output_columns=list(root.output_columns),
            )

        return root

    def _qualified(self, column: ast.Column) -> str:
        source = self.ctx.source_of(column)
        if source:
            return f"{source}.{column.name}"
        return column.name


def build_ir(query: ast.Query, catalog: Catalog, semantic: SemanticResult) -> ir.IRNode:
    return IRBuilder(catalog, semantic).build(query)
