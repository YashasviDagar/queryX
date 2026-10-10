"""Statistics, cardinality and cost-model tests."""
from __future__ import annotations

import pytest

from app.compiler.cost.cardinality import CardinalityEstimator
from app.compiler.cost.config import CostConfig
from app.compiler.cost.statistics import load_statistics
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer


def _ctx_and_cardinality(sql: str, stats, config):
    catalog = stats.to_catalog()
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(catalog).analyze(query)
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    return ctx, CardinalityEstimator(stats, config, ctx), query, semantic


def test_statistics_loaded(stats):
    students = stats.get("students")
    assert students.rows == 100000
    assert students.column("cgpa").distinct == 500
    assert any(i.name == "students_cgpa_idx" for i in students.indexes)
    assert stats.get("departments").rows == 20


def test_equality_selectivity(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT d.id FROM departments d WHERE d.name = 'CSE'", stats, cost_config
    )
    selectivity = card.predicate_selectivity(query.where.condition)
    assert selectivity == 1 / 20


def test_range_selectivity(stats, cost_config):
    # cgpa spans 0..10 uniformly, so "> 8.0" keeps 20% of rows.
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT s.id FROM students s WHERE s.cgpa > 8.0", stats, cost_config
    )
    selectivity = card.predicate_selectivity(query.where.condition)
    assert selectivity == pytest.approx(0.2)


def test_and_selectivity_multiplies(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT s.id FROM students s WHERE s.cgpa > 8.0 AND s.city = 'Pune'",
        stats,
        cost_config,
    )
    selectivity = card.predicate_selectivity(query.where.condition)
    assert selectivity == pytest.approx(0.2 * (1 / 50))


def test_join_selectivity(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT s.id FROM students s INNER JOIN departments d ON s.dept_id = d.id",
        stats,
        cost_config,
    )
    condition = query.joins[0].condition
    selectivity = card._comparison_selectivity(condition)
    assert selectivity == 1 / 20


def test_filter_row_estimate(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT s.id FROM students s WHERE s.cgpa > 8.0", stats, cost_config
    )
    rows = card.apply_filter(100000, query.where.condition)
    assert rows == pytest.approx(20000.0)


def test_cost_config_defaults():
    config = CostConfig()
    assert config.seq_page_cost == 1.0
    assert config.random_page_cost == 4.0
    assert config.rows_per_page == 100


def test_distinct_rows_estimate(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT DISTINCT s.city FROM students s", stats, cost_config
    )
    rows = card.distinct_rows(100000, query.select.columns)
    assert rows == 50


def test_distinct_rows_falls_back_for_computed_expression(stats, cost_config):
    _, card, query, _ = _ctx_and_cardinality(
        "SELECT DISTINCT COUNT(s.id) FROM students s", stats, cost_config
    )
    rows = card.distinct_rows(100000, query.select.columns)
    assert rows == 100000
