"""Optional benchmark harness.

Runs the custom optimizer over a set of queries and, when PostgreSQL is
available, compares the custom optimizer's chosen plan with PostgreSQL's plan.
Without a database it simply reports the optimizer's own estimates.

Usage:
    python -m app.database.benchmark
"""
from __future__ import annotations

import json

from ..services.pipeline import QueryPipeline
from .connection import database_enabled, run_explain

QUERIES = [
    "SELECT s.name, d.name FROM students s INNER JOIN departments d ON s.dept_id = d.id WHERE s.cgpa > 8.0 AND d.name = 'CSE';",
    "SELECT s.name FROM students s WHERE s.cgpa > 8.0;",
    "SELECT s.dept_id, COUNT(s.id) FROM students s GROUP BY s.dept_id;",
]


def main() -> None:
    pipeline = QueryPipeline()
    for sql in QUERIES:
        result = pipeline.compile(sql)
        selected = result.get("selectedPlan") or {}
        print("=" * 80)
        print(sql)
        print(
            f"  custom optimizer -> {selected.get('name')} | "
            f"cost={selected.get('estimatedCost')} rows={selected.get('estimatedRows')}"
        )
        if database_enabled():
            explain = run_explain(sql)
            print("  postgres EXPLAIN:", json.dumps(explain)[:300] if explain else "unavailable")
        else:
            print("  postgres EXPLAIN: skipped (DATABASE_ENABLED=false)")


if __name__ == "__main__":
    main()
