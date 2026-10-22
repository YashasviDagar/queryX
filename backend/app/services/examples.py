"""Curated example queries used to seed the UI and integration tests."""
from __future__ import annotations

EXAMPLES: list[dict[str, str]] = [
    {
        "id": "department_report",
        "title": "Department report (4-table join)",
        "description": (
            "Joins all four tables, filters three of them, groups by department, keeps "
            "groups with HAVING, then sorts and limits. Exercises every compiler stage."
        ),
        "sql": (
            "SELECT d.name, COUNT(e.id) AS enrolments, AVG(e.grade) AS avg_grade\n"
            "FROM students s\n"
            "INNER JOIN departments d ON s.dept_id = d.id\n"
            "INNER JOIN enrollments e ON e.student_id = s.id\n"
            "INNER JOIN courses c ON e.course_id = c.id\n"
            "WHERE s.cgpa > 6.0 AND c.credits >= 3 AND s.age < 30\n"
            "GROUP BY d.name\n"
            "HAVING COUNT(e.id) > 5\n"
            "ORDER BY avg_grade DESC\n"
            "LIMIT 10;"
        ),
    },
    {
        "id": "top_grades",
        "title": "Top grades in two cities",
        "description": "Three-table join with an OR filter, sorted by grade and limited to 15 rows.",
        "sql": (
            "SELECT s.name, s.city, c.title, e.grade\n"
            "FROM students s\n"
            "INNER JOIN enrollments e ON s.id = e.student_id\n"
            "INNER JOIN courses c ON e.course_id = c.id\n"
            "WHERE s.cgpa >= 7.5 AND e.grade > 8.0 AND (s.city = 'Pune' OR s.city = 'Mumbai')\n"
            "ORDER BY e.grade DESC\n"
            "LIMIT 15;"
        ),
    },
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
        "id": "having_filter",
        "title": "HAVING on an aggregate",
        "description": (
            "Keeps only departments with more than two students. The HAVING predicate "
            "references COUNT(*), so it stays above the aggregate instead of being pushed "
            "into the scan."
        ),
        "sql": (
            "SELECT s.dept_id, COUNT(s.id) AS total\n"
            "FROM students s\n"
            "GROUP BY s.dept_id\n"
            "HAVING COUNT(s.id) > 2\n"
            "ORDER BY total DESC;"
        ),
    },
    {
        "id": "left_join",
        "title": "LEFT JOIN pushdown boundary",
        "description": (
            "Students with no matching department are kept. The cgpa filter moves into the "
            "preserved students input, while the filter on departments stays above the join."
        ),
        "sql": (
            "SELECT s.name, d.name\n"
            "FROM students s\n"
            "LEFT JOIN departments d ON s.dept_id = d.id\n"
            "WHERE s.cgpa > 8.0 AND d.name = 'CSE';"
        ),
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
        "id": "invalid_table",
        "title": "Invalid query (semantic error)",
        "description": "References a table that does not exist; demonstrates compiler-style diagnostics.",
        "sql": "SELECT x.name FROM teachers x WHERE x.salary > 1000;",
    },
]


def get_examples() -> list[dict[str, str]]:
    return EXAMPLES
