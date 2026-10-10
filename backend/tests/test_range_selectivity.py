"""Range selectivity from column min/max bounds."""
from __future__ import annotations

import pytest

from app.compiler.cost.cardinality import CardinalityEstimator
from app.compiler.cost.config import load_cost_config
from app.compiler.cost.statistics import load_statistics
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.parser.parser import parse
from app.compiler.semantic.analyzer import SemanticAnalyzer


def _selectivity(sql: str) -> float:
    stats = load_statistics()
    config = load_cost_config()
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(stats.to_catalog()).analyze(query)
    assert semantic.valid, [e.message for e in semantic.errors]
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    return CardinalityEstimator(stats, config, ctx).predicate_selectivity(query.where.condition)


def test_greater_than_uses_fraction_above_literal():
    # cgpa spans 0..10, so > 8 keeps 20% of rows.
    assert _selectivity("SELECT s.id FROM students s WHERE s.cgpa > 8.0") == pytest.approx(0.2)


def test_less_than_uses_fraction_below_literal():
    assert _selectivity("SELECT s.id FROM students s WHERE s.cgpa < 8.0") == pytest.approx(0.8)


def test_literal_on_left_flips_the_operator():
    # 8.0 < cgpa is the same predicate as cgpa > 8.0.
    assert _selectivity("SELECT s.id FROM students s WHERE 8.0 < s.cgpa") == pytest.approx(0.2)


def test_interpolates_within_non_zero_range():
    # age spans 17..35; > 20 keeps (35 - 20) / (35 - 17) of rows.
    assert _selectivity("SELECT s.id FROM students s WHERE s.age > 20") == pytest.approx(15 / 18)


def test_literal_above_maximum_selects_nothing():
    assert _selectivity("SELECT s.id FROM students s WHERE s.cgpa > 12.0") == pytest.approx(0.0)


def test_literal_below_minimum_selects_everything_above_it():
    assert _selectivity("SELECT s.id FROM students s WHERE s.cgpa > 0.0") == pytest.approx(1.0)


def test_column_without_bounds_falls_back_to_configured_range():
    config = load_cost_config()
    assert _selectivity("SELECT s.id FROM students s WHERE s.id > 50000") == pytest.approx(
        config.range_selectivity
    )


def test_non_numeric_literal_falls_back_to_configured_range():
    config = load_cost_config()
    assert _selectivity("SELECT s.id FROM students s WHERE s.city > 'M'") == pytest.approx(
        config.range_selectivity
    )
