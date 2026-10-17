"""Physical plan generator.

Turns the optimized relational IR into a set of *candidate* physical plans by
enumerating:
  * join orders (as-written and cardinality-sorted),
  * join algorithms (hash, nested loop, merge),
  * access paths (sequential scan, and index scan when an index applies).
"""
from __future__ import annotations

import string
from dataclasses import dataclass, field
from typing import Optional

from ..ast import nodes as ast
from ..cost.config import CostConfig
from ..cost.statistics import StatsStore
from ..ir import nodes as ir
from ..ir.expr import ExprContext, combine_and, conjuncts, referenced_sources, render
from ..cost.logical import estimate_ir_rows
from ..cost.cardinality import CardinalityEstimator
from ..cost.model import CostEstimator
from .physical import PhysicalNode

_JOIN_ALGORITHMS = ["HashJoin", "NestedLoopJoin", "MergeJoin"]
_PREFIX_OPS = (ir.Project, ir.Distinct, ir.Sort, ir.Limit, ir.Aggregate)
# Subset DP visits 2^n subsets; beyond this many relations fall back to heuristic orders.
_DP_MAX_RELATIONS = 8


@dataclass
class PlanCandidate:
    plan_id: str
    name: str
    description: str
    tree: PhysicalNode
    join_order: list[str] = field(default_factory=list)
    join_algorithm: str = ""
    access_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "joinOrder": self.join_order,
            "joinAlgorithm": self.join_algorithm,
            "accessPaths": self.access_paths,
            "tree": self.tree.to_dict(),
        }


class PhysicalPlanGenerator:
    def __init__(self, stats: StatsStore, config: CostConfig, expr_ctx: ExprContext) -> None:
        self.stats = stats
        self.config = config
        self.expr = expr_ctx
        self.cardinality = CardinalityEstimator(stats, config, expr_ctx)
        self.estimator = CostEstimator(stats, config, expr_ctx)

    # -- entry point ---------------------------------------------------------
    def generate(self, root: ir.IRNode) -> list[PlanCandidate]:
        prefix, core = self._split(root)
        candidates: list[PlanCandidate] = []

        if isinstance(core, ir.Join):
            relations, predicates = self._flatten(core)
            orders = self._join_orders(relations)
            best = self._dp_join_order(relations, predicates)
            if best is not None and [id(r) for r in best] not in [[id(r) for r in o] for o in orders]:
                orders.append(best)
            scan_modes = self._scan_modes(relations)
            for order in orders:
                for algorithm in _JOIN_ALGORITHMS:
                    for scan_mode in scan_modes:
                        tree = self._build_join_tree(order, predicates, algorithm, scan_mode)
                        full = self._apply_prefix(prefix, tree)
                        candidates.append(self._make_candidate(full, order, algorithm, scan_mode))
        else:
            relations = [core]
            for scan_mode in self._scan_modes(relations):
                tree = self._build_relation(core, scan_mode)
                full = self._apply_prefix(prefix, tree)
                candidates.append(self._make_candidate(full, relations, "None", scan_mode))

        return self._dedupe(candidates)

    # -- decomposition -------------------------------------------------------
    def _split(self, root: ir.IRNode) -> tuple[list[ir.IRNode], ir.IRNode]:
        prefix: list[ir.IRNode] = []
        node = root
        while True:
            if isinstance(node, _PREFIX_OPS):
                prefix.append(node)
                node = node.children[0]
                continue
            # A filter above a join or an aggregate (e.g. HAVING) is a prefix operator;
            # only a filter directly over a base scan belongs to the join core.
            if isinstance(node, ir.Filter) and node.children and not isinstance(node.children[0], ir.Scan):
                prefix.append(node)
                node = node.children[0]
                continue
            break
        return prefix, node

    def _flatten(self, node: ir.IRNode) -> tuple[list[ir.IRNode], list[ast.Node]]:
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

    # -- alternatives --------------------------------------------------------
    def _join_orders(self, relations: list[ir.IRNode]) -> list[list[ir.IRNode]]:
        estimator = self.cardinality
        as_written = list(relations)
        reordered = sorted(relations, key=lambda r: estimate_ir_rows(r, estimator))
        orders = [as_written]
        if [self._source(r) for r in reordered] != [self._source(r) for r in as_written]:
            orders.append(reordered)
        return orders

    def _dp_join_order(
        self, relations: list[ir.IRNode], predicates: list[ast.Node]
    ) -> Optional[list[ir.IRNode]]:
        """Selinger-style dynamic programming over left-deep join orders.

        Finds the order with the lowest estimated cost for hash joins over sequential
        scans, by extending the cheapest plan for each subset of relations one relation
        at a time. Returns ``None`` when there is nothing to choose between.
        """
        n = len(relations)
        if n < 3 or n > _DP_MAX_RELATIONS:
            return None
        sources = [self._relation_sources(r) for r in relations]
        best: dict[int, tuple[float, list[int]]] = {}
        for i in range(n):
            best[1 << i] = (self._subset_cost([i], relations, predicates, sources), [i])
        for mask in range(1, 1 << n):
            if mask.bit_count() < 2:
                continue
            options = []
            for i in range(n):
                prefix_mask = mask ^ (1 << i)
                if not mask & (1 << i) or prefix_mask not in best:
                    continue
                order = best[prefix_mask][1] + [i]
                options.append((self._subset_cost(order, relations, predicates, sources), order))
            if options:
                best[mask] = min(options, key=lambda option: option[0])
        return [relations[i] for i in best[(1 << n) - 1][1]]

    def _subset_cost(
        self,
        order: list[int],
        relations: list[ir.IRNode],
        predicates: list[ast.Node],
        sources: list[set[str]],
    ) -> float:
        members = [relations[i] for i in order]
        member_sources: set[str] = set().union(*(sources[i] for i in order))
        applicable = [p for p in predicates if referenced_sources(p, self.expr) <= member_sources]
        tree = self._build_join_tree(members, applicable, "HashJoin", "seq")
        return self.estimator.estimate(tree).estimated_cost

    def _scan_modes(self, relations: list[ir.IRNode]) -> list[str]:
        modes = ["seq"]
        if any(self._index_for(r) is not None for r in relations):
            modes.append("index")
        return modes

    # -- access paths --------------------------------------------------------
    def _relation_condition(self, relation: ir.IRNode) -> Optional[ast.Node]:
        if isinstance(relation, ir.Filter) and relation.children and isinstance(relation.children[0], ir.Scan):
            return relation.condition
        return None

    def _relation_scan(self, relation: ir.IRNode) -> ir.Scan:
        if isinstance(relation, ir.Filter):
            return relation.children[0]
        assert isinstance(relation, ir.Scan)
        return relation

    def _index_for(self, relation: ir.IRNode) -> Optional[tuple[str, str]]:
        condition = self._relation_condition(relation)
        if condition is None:
            return None
        scan = self._relation_scan(relation)
        table = self.stats.get(scan.table)
        if table is None:
            return None
        for predicate in conjuncts(condition):
            if not isinstance(predicate, ast.Comparison):
                continue
            for side in (predicate.left, predicate.right):
                if isinstance(side, ast.Column):
                    for index in table.indexes:
                        if index.columns and index.columns[0].lower() == side.name.lower():
                            return index.name, side.name
        return None

    def _build_relation(self, relation: ir.IRNode, scan_mode: str, algorithm: str = "HashJoin") -> PhysicalNode:
        if isinstance(relation, ir.Join):
            # An outer join is kept intact as one relation; its inputs are built recursively.
            return PhysicalNode(
                op=algorithm,
                details={
                    "condition": relation.condition,
                    "conditionText": render(relation.condition),
                    "joinType": relation.join_type,
                },
                children=[
                    self._build_relation(relation.left, scan_mode, algorithm),
                    self._build_relation(relation.right, scan_mode, algorithm),
                ],
                logical=relation,
            )
        condition = self._relation_condition(relation)
        scan = self._relation_scan(relation)
        selectivity = self.cardinality.predicate_selectivity(condition) if condition else 1.0
        index_info = self._index_for(relation) if scan_mode == "index" else None

        if index_info is not None:
            index_name, column = index_info
            return PhysicalNode(
                op="IndexScan",
                details={
                    "table": scan.table,
                    "alias": scan.alias,
                    "index": index_name,
                    "column": column,
                    "selectivity": selectivity,
                    "columns": scan.columns,
                    # Kept so code generation can recheck the full predicate per row.
                    "condition": condition,
                    "conditionText": render(condition),
                },
                logical=scan,
            )

        scan_node = PhysicalNode(
            op="SeqScan",
            details={
                "table": scan.table,
                "alias": scan.alias,
                "columns": scan.columns,
            },
            logical=scan,
        )
        if condition is not None:
            return PhysicalNode(
                op="Filter",
                details={
                    "condition": condition,
                    "conditionText": render(condition),
                    "selectivity": selectivity,
                },
                children=[scan_node],
                logical=relation,
            )
        return scan_node

    # -- join tree -----------------------------------------------------------
    def _build_join_tree(
        self,
        relations: list[ir.IRNode],
        predicates: list[ast.Node],
        algorithm: str,
        scan_mode: str,
    ) -> PhysicalNode:
        phys = [self._build_relation(r, scan_mode, algorithm) for r in relations]
        remaining = list(predicates)
        tree = phys[0]
        joined = set(self._relation_sources(relations[0]))

        for i in range(1, len(phys)):
            joined |= set(self._relation_sources(relations[i]))
            applicable = [p for p in remaining if referenced_sources(p, self.expr) <= joined]
            for predicate in applicable:
                remaining.remove(predicate)
            condition = combine_and(applicable)
            tree = PhysicalNode(
                op=algorithm,
                details={
                    "condition": condition,
                    "conditionText": render(condition),
                    "joinType": "INNER",
                },
                children=[tree, phys[i]],
            )

        if remaining:
            tree = PhysicalNode(
                op="Filter",
                details={
                    "condition": combine_and(remaining),
                    "conditionText": render(combine_and(remaining)),
                },
                children=[tree],
            )
        return tree

    def _apply_prefix(self, prefix: list[ir.IRNode], tree: PhysicalNode) -> PhysicalNode:
        for op in reversed(prefix):
            if isinstance(op, ir.Project):
                tree = PhysicalNode(
                    op="Project",
                    details={"columns": ", ".join(op.names)},
                    children=[tree],
                    logical=op,
                )
            elif isinstance(op, ir.Distinct):
                tree = PhysicalNode(
                    op="Distinct",
                    details={
                        "expressions": op.expressions,
                        "columns": ", ".join(op.output_columns),
                    },
                    children=[tree],
                    logical=op,
                )
            elif isinstance(op, ir.Sort):
                keys = ", ".join(f"{render(i.column)} {i.direction}" for i in op.items)
                tree = PhysicalNode(op="Sort", details={"keys": keys, "items": op.items}, children=[tree], logical=op)
            elif isinstance(op, ir.Aggregate):
                text = ", ".join(render(f) for f in op.functions)
                if op.group_by:
                    text += " GROUP BY " + ", ".join(render(g) for g in op.group_by)
                tree = PhysicalNode(
                    op="Aggregate",
                    details={"groupBy": op.group_by, "text": text, "functions": op.functions},
                    children=[tree],
                    logical=op,
                )
            elif isinstance(op, ir.Limit):
                tree = PhysicalNode(op="Limit", details={"count": op.count}, children=[tree], logical=op)
            elif isinstance(op, ir.Filter):
                tree = PhysicalNode(
                    op="Filter",
                    details={"condition": op.condition, "conditionText": render(op.condition)},
                    children=[tree],
                    logical=op,
                )
        return tree

    # -- helpers -------------------------------------------------------------
    def _relation_sources(self, relation: ir.IRNode) -> set[str]:
        from ..optimizer.join_utils import referenced_sources_ir

        return referenced_sources_ir(relation, self.expr)

    def _source(self, relation: ir.IRNode) -> str:
        if isinstance(relation, ir.Join):
            return f"{relation.join_type.lower()} join ({', '.join(sorted(self._relation_sources(relation)))})"
        scan = self._relation_scan(relation)
        return (scan.alias or scan.table).lower()

    def _make_candidate(
        self,
        tree: PhysicalNode,
        order: list[ir.IRNode],
        algorithm: str,
        scan_mode: str,
    ) -> PlanCandidate:
        order_sources = [self._source(r) for r in order]
        access = "index scans" if scan_mode == "index" else "sequential scans"
        if algorithm == "None":
            description = f"{access.capitalize()}"
        else:
            description = f"{algorithm} over {order_sources} using {access}"
        return PlanCandidate(
            plan_id="",
            name="",
            description=description,
            tree=tree,
            join_order=order_sources,
            join_algorithm=algorithm,
            access_paths=[access],
        )

    def _dedupe(self, candidates: list[PlanCandidate]) -> list[PlanCandidate]:
        seen: set[str] = set()
        unique: list[PlanCandidate] = []
        for candidate in candidates:
            signature = candidate.tree.to_dict().__repr__()
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(candidate)

        for index, candidate in enumerate(unique):
            letter = string.ascii_uppercase[index] if index < 26 else f"P{index}"
            candidate.name = f"Plan {letter}"
            candidate.plan_id = f"plan_{index + 1}"
        return unique
