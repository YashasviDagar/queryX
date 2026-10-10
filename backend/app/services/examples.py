"""Curated example queries used to seed the UI and integration tests."""
from __future__ import annotations

EXAMPLES: list[dict[str, str]] = [
    {
        "id": "join_pushdown",
        "title": "Join + predicate pushdown",
        "description": (
            "The flagship demo: two filtered inputs joined on dept_id. Predicate "
            "pushdown moves each filter next to its scan before the join."
        ),
        "sql": (
            "SELECT s.name, d.name\n"
            "FROM students s\n"
            "INNER JOIN departments d ON s.dept_id = d.id\n"
            "WHERE s.cgpa > 8.0 AND d.name = 'CSE';"
        ),
    },
    {
        "id": "simple_filter",
        "title": "Single-table filter",
        "description": "A single predicate over students; shows scan vs index access path selection.",
        "sql": "SELECT s.name, s.cgpa FROM students s WHERE s.cgpa > 8.0;",
    },
    {
        "id": "aggregate",
        "title": "Aggregation + GROUP BY",
        "description": "Group students by department and compute the average CGPA.",
        "sql": (
            "SELECT s.dept_id, COUNT(s.id) AS total, AVG(s.cgpa) AS avg_cgpa\n"
            "FROM students s\n"
            "GROUP BY s.dept_id\n"
            "ORDER BY avg_cgpa DESC;"
        ),
    },
    {
        "id": "constant_folding",
        "title": "Constant folding",
        "description": "The predicate '2 + 3 < 10' folds to TRUE during optimization.",
        "sql": "SELECT s.name FROM students s WHERE 2 + 3 < 10 AND s.cgpa > 7.5;",
    },
    {
        "id": "redundant",
        "title": "Redundant conditions",
        "description": "The duplicate predicate is collapsed into a single evaluation.",
        "sql": "SELECT s.name FROM students s WHERE s.cgpa > 8.0 AND s.cgpa > 8.0;",
    },
    {
        "id": "three_way_join",
        "title": "Three-way join reordering",
        "description": "Join reordering explores orders starting from the most selective relation.",
        "sql": (
            "SELECT s.name, c.title\n"
            "FROM students s\n"
            "INNER JOIN enrollments e ON s.id = e.student_id\n"
            "INNER JOIN courses c ON e.course_id = c.id\n"
            "WHERE s.cgpa > 9.0 AND c.credits = 4;"
        ),
    },
    {
        "id": "order_limit",
        "title": "ORDER BY + LIMIT",
        "description": "Sort then limit; shows how the top operator interacts with the plan.",
        "sql": (
            "SELECT s.name, s.cgpa\n"
            "FROM students s\n"
            "WHERE s.city = 'Pune'\n"
            "ORDER BY s.cgpa DESC\n"
            "LIMIT 10;"
        ),
    },
    {
        "id": "distinct",
        "title": "SELECT DISTINCT",
        "description": "Deduplication lowers the estimated output cardinality via a Distinct operator.",
        "sql": "SELECT DISTINCT s.city FROM students s WHERE s.cgpa > 8.0;",
    },
    {
        "id": "invalid_table",
        "title": "Invalid query (semantic error)",
        "description": "References a table that does not exist; demonstrates compiler-style diagnostics.",
        "sql": "SELECT x.name FROM teachers x WHERE x.salary > 1000;",
    },
]


def get_examples() -> list[dict[str, str]]:
    return EXAMPLES
