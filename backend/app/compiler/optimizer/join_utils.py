"""Shared helpers for flattening and rebuilding inner-join trees."""
from __future__ import annotations

from ..ast import nodes as ast
from ..ir import nodes as ir
from ..ir.expr import ExprContext, combine_and, conjuncts, referenced_sources


def flatten_inner_joins(node: ir.IRNode) -> tuple[list[ir.IRNode], list[ast.Node]]:
    """Flatten a left-deep tree of INNER joins into relations + predicates."""
    relations: list[ir.IRNode] = []
    predicates: list[ast.Node] = []

    def walk(current: ir.IRNode) -> None:
        if isinstance(current, ir.Join) and current.join_type == "INNER" and current.left and current.right:
            walk(current.left)
            walk(current.right)
            predicates.extend(conjuncts(current.condition))
        else:
            relations.append(current)

    walk(node)
    return relations, predicates


def build_left_deep_join(
    relations: list[ir.IRNode],
    predicates: list[ast.Node],
    ctx: ExprContext,
) -> ir.IRNode:
    """Rebuild a left-deep inner-join tree, applying predicates ASAP."""
    if not relations:
        raise ValueError("Cannot build a join tree without relations.")
    if len(relations) == 1:
        return relations[0]

    remaining = list(predicates)
    tree = relations[0]
    joined_sources = set(referenced_sources_ir(relations[0], ctx))

    for relation in relations[1:]:
        tree = ir.Join(
            left=tree,
            right=relation,
            condition=None,
            join_type="INNER",
            output_columns=list(tree.output_columns) + list(relation.output_columns),
        )
        joined_sources |= set(referenced_sources_ir(relation, ctx))
        applicable = [p for p in remaining if referenced_sources(p, ctx) <= joined_sources]
        for predicate in applicable:
            remaining.remove(predicate)
        tree.condition = combine_and(applicable)

    # Any predicates left over (should not happen for valid inner joins) are
    # attached as a filter above the join.
    if remaining:
        from ..ir.nodes import Filter

        return Filter(
            condition=combine_and(remaining),
            children=[tree],
            output_columns=list(tree.output_columns),
        )
    return tree


def referenced_sources_ir(node: ir.IRNode, ctx: ExprContext) -> set[str]:
    """Return the scan keys referenced by an IR subtree."""
    sources: set[str] = set()
    if isinstance(node, ir.Scan):
        sources.add((node.alias or node.table).lower())
    if isinstance(node, ir.Filter) and node.condition is not None:
        sources |= referenced_sources(node.condition, ctx)
    if isinstance(node, ir.Join) and node.condition is not None:
        sources |= referenced_sources(node.condition, ctx)
    if isinstance(node, ir.Aggregate):
        for f in node.functions:
            sources |= referenced_sources(f, ctx)
        for g in node.group_by:
            sources |= referenced_sources(g, ctx)
    if isinstance(node, ir.Project):
        for e in node.expressions:
            sources |= referenced_sources(e, ctx)
    if isinstance(node, ir.Sort):
        for item in node.items:
            sources |= referenced_sources(item.column, ctx)
    for child in node.children:
        sources |= referenced_sources_ir(child, ctx)
    return sources
