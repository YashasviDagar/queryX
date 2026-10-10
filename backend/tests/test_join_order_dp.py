"""Dynamic-programming join order search (Selinger-style)."""
from __future__ import annotations

import itertools

from app.compiler.cost.config import load_cost_config
from app.compiler.cost.statistics import load_statistics
from app.compiler.ir.builder import build_ir
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.optimizer.engine import OptimizerEngine
from app.compiler.parser.parser import parse
from app.compiler.planner.generator import PhysicalPlanGenerator
from app.compiler.semantic.analyzer import SemanticAnalyzer

THREE_WAY = (
    "SELECT s.name, c.title FROM students s "
    "INNER JOIN enrollments e ON s.id = e.student_id "
    "INNER JOIN courses c ON e.course_id = c.id "
    "WHERE s.cgpa > 9.0 AND c.credits = 4"
)

FOUR_WAY = (
    "SELECT s.name, c.title FROM students s "
    "INNER JOIN enrollments e ON s.id = e.student_id "
    "INNER JOIN courses c ON e.course_id = c.id "
    "INNER JOIN departments d ON s.dept_id = d.id "
    "WHERE d.name = 'CSE'"
)


def _prepare(sql: str):
    stats = load_statistics()
    config = load_cost_config()
    catalog = stats.to_catalog()
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    root = build_ir(query, catalog, semantic)
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    optimized = OptimizerEngine(stats, config, ctx).optimize(root).root
    generator = PhysicalPlanGenerator(stats, config, ctx)
    _, core = generator._split(optimized)
    relations, predicates = generator._flatten(core)
    return generator, relations, predicates


def _order_cost(generator, order, predicates) -> float:
    tree = generator._build_join_tree(list(order), predicates, "HashJoin", "seq")
    return generator.estimator.estimate(tree).estimated_cost


def test_dp_order_is_no_costlier_than_any_three_way_permutation():
    generator, relations, predicates = _prepare(THREE_WAY)
    best = generator._dp_join_order(relations, predicates)
    assert best is not None
    best_cost = _order_cost(generator, best, predicates)
    for permutation in itertools.permutations(relations):
        assert best_cost <= _order_cost(generator, permutation, predicates) + 0.01


def test_dp_order_is_no_costlier_than_any_four_way_permutation():
    generator, relations, predicates = _prepare(FOUR_WAY)
    best = generator._dp_join_order(relations, predicates)
    assert best is not None
    best_cost = _order_cost(generator, best, predicates)
    for permutation in itertools.permutations(relations):
        assert best_cost <= _order_cost(generator, permutation, predicates) + 0.01


def test_dp_returns_every_relation_exactly_once():
    generator, relations, predicates = _prepare(FOUR_WAY)
    best = generator._dp_join_order(relations, predicates)
    assert sorted(id(r) for r in best) == sorted(id(r) for r in relations)


def test_dp_needs_at_least_three_relations():
    generator, relations, predicates = _prepare(
        "SELECT s.name FROM students s INNER JOIN departments d ON s.dept_id = d.id"
    )
    assert generator._dp_join_order(relations, predicates) is None
