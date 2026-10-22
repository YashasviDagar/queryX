"""Random query generator.

Builds a random query that is always valid for the queryX grammar and schema:
tables are chosen by walking the foreign-key join graph, filters use columns of
the chosen tables with literals drawn from the sample data, and grouping or
ordering only reference columns the query selects.
"""
from __future__ import annotations

import random
from typing import Any, Optional

from ..compiler.codegen.sample_data import SampleDatabase

ALIASES = {"students": "s", "departments": "d", "enrollments": "e", "courses": "c"}

# Foreign-key edges: (table, table, join condition).
JOIN_EDGES = [
    ("students", "departments", "s.dept_id = d.id"),
    ("students", "enrollments", "s.id = e.student_id"),
    ("enrollments", "courses", "e.course_id = c.id"),
    ("courses", "departments", "c.dept_id = d.id"),
]

NUMERIC = {
    "students": ["cgpa", "age"],
    "enrollments": ["grade"],
    "courses": ["credits"],
    "departments": [],
}
TEXT_FILTERS = {"students": ["city"], "departments": ["name"], "courses": [], "enrollments": []}
DISPLAY = {
    "students": ["name", "cgpa", "city", "age"],
    "departments": ["name", "building"],
    "enrollments": ["grade"],
    "courses": ["title", "credits"],
}
GROUP_KEYS = {
    "students": ["city", "dept_id"],
    "departments": ["name"],
    "courses": ["credits"],
    "enrollments": [],
}


def random_query(database: SampleDatabase, rng: Optional[random.Random] = None) -> dict[str, Any]:
    rng = rng or random.Random()
    tables, joins = _pick_tables(rng)
    where = _where(database, tables, rng)
    if rng.random() < 0.45 and any(GROUP_KEYS[t] for t in tables):
        sql, kind = _aggregate_query(tables, joins, where, rng)
    else:
        sql, kind = _select_query(tables, joins, where, rng)
    table_names = ", ".join(tables)
    return {
        "sql": sql,
        "description": f"Random {kind} over {table_names}.",
    }


def _pick_tables(rng: random.Random) -> tuple[list[str], list[str]]:
    start = rng.choice(["students", "students", "enrollments", "courses", "departments"])
    tables = [start]
    joins: list[str] = []
    for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
        options = [
            (a, b, cond) for a, b, cond in JOIN_EDGES if (a in tables) != (b in tables)
        ]
        if not options:
            break
        a, b, condition = rng.choice(options)
        new = b if a in tables else a
        join_type = "LEFT JOIN" if rng.random() < 0.15 else "INNER JOIN"
        joins.append(f"{join_type} {new} {ALIASES[new]} ON {condition}")
        tables.append(new)
    return tables, joins


def _where(database: SampleDatabase, tables: list[str], rng: random.Random) -> list[str]:
    candidates = []
    for table in tables:
        alias = ALIASES[table]
        for column in NUMERIC[table]:
            candidates.append(("num", table, alias, column))
        for column in TEXT_FILTERS[table]:
            candidates.append(("text", table, alias, column))
    rng.shuffle(candidates)
    predicates = []
    for kind, table, alias, column in candidates[: rng.choice([1, 1, 2, 2, 3])]:
        values = [row[column] for row in database.rows(table) if row.get(column) is not None]
        if not values:
            continue
        if kind == "num":
            low, high = min(values), max(values)
            point = rng.uniform(low, low + (high - low) * 0.8)
            literal = int(point) if isinstance(values[0], int) else round(point, 1)
            op = rng.choice([">", ">=", "<", "<="])
            if op in ("<", "<="):
                literal = int(low + (high - low) * 0.6) if isinstance(values[0], int) else round(low + (high - low) * 0.6, 1)
            predicates.append(f"{alias}.{column} {op} {literal}")
        else:
            picks = rng.sample(sorted(set(values)), k=min(2, len(set(values))))
            if len(picks) == 2 and rng.random() < 0.4:
                predicates.append(f"({alias}.{column} = '{picks[0]}' OR {alias}.{column} = '{picks[1]}')")
            else:
                predicates.append(f"{alias}.{column} = '{picks[0]}'")
    return predicates


def _from_clause(tables: list[str], joins: list[str]) -> str:
    lines = [f"FROM {tables[0]} {ALIASES[tables[0]]}"]
    lines.extend(joins)
    return "\n".join(lines)


def _where_clause(where: list[str]) -> list[str]:
    return [f"WHERE {' AND '.join(where)}"] if where else []


def _aggregate_query(tables, joins, where, rng: random.Random) -> tuple[str, str]:
    group_table = rng.choice([t for t in tables if GROUP_KEYS[t]])
    group = f"{ALIASES[group_table]}.{rng.choice(GROUP_KEYS[group_table])}"
    count_table = rng.choice(tables)
    select = [group, f"COUNT({ALIASES[count_table]}.id) AS total"]
    numeric = [(t, c) for t in tables for c in NUMERIC[t]]
    if numeric and rng.random() < 0.7:
        table, column = rng.choice(numeric)
        select.append(f"{rng.choice(['AVG', 'MAX', 'MIN'])}({ALIASES[table]}.{column}) AS {column}_stat")
    lines = [f"SELECT {', '.join(select)}", _from_clause(tables, joins), *_where_clause(where), f"GROUP BY {group}"]
    if rng.random() < 0.4:
        lines.append(f"HAVING COUNT({ALIASES[count_table]}.id) > {rng.choice([1, 2, 3, 5])}")
    lines.append(f"ORDER BY total {rng.choice(['DESC', 'ASC'])}")
    if rng.random() < 0.4:
        lines.append(f"LIMIT {rng.choice([3, 5, 10])}")
    return "\n".join(lines) + ";", "GROUP BY query"


def _select_query(tables, joins, where, rng: random.Random) -> tuple[str, str]:
    columns = [f"{ALIASES[t]}.{c}" for t in tables for c in DISPLAY[t]]
    rng.shuffle(columns)
    chosen = columns[: rng.choice([1, 2, 3, 3, 4])]
    distinct = len(chosen) == 1 and rng.random() < 0.5
    lines = [f"SELECT {'DISTINCT ' if distinct else ''}{', '.join(chosen)}", _from_clause(tables, joins), *_where_clause(where)]
    if rng.random() < 0.6:
        lines.append(f"ORDER BY {rng.choice(chosen)} {rng.choice(['ASC', 'DESC'])}")
    if rng.random() < 0.5:
        lines.append(f"LIMIT {rng.choice([5, 10, 15, 20])}")
    kind = "join query" if len(tables) > 1 else "single-table query"
    return "\n".join(lines) + ";", kind
