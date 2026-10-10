"""Shared pytest fixtures."""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402

from app.compiler.cost.config import load_cost_config  # noqa: E402
from app.compiler.cost.statistics import load_statistics  # noqa: E402
from app.services.pipeline import QueryPipeline  # noqa: E402

EXAMPLE_SQL = (
    "SELECT s.name, d.name\n"
    "FROM students s\n"
    "INNER JOIN departments d ON s.dept_id = d.id\n"
    "WHERE s.cgpa > 8.0 AND d.name = 'CSE';"
)


@pytest.fixture(scope="session")
def pipeline() -> QueryPipeline:
    return QueryPipeline()


@pytest.fixture(scope="session")
def stats():
    return load_statistics()


@pytest.fixture(scope="session")
def cost_config():
    return load_cost_config()


@pytest.fixture(scope="session")
def catalog(stats):
    return stats.to_catalog()


@pytest.fixture(scope="session")
def example_sql() -> str:
    return EXAMPLE_SQL
