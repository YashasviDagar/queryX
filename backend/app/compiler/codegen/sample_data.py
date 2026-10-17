"""Deterministic in-memory sample database for the bytecode VM.

The optimizer reasons about the full-size tables described in
``statistics.yaml``; the VM executes against a scaled-down copy generated from
the same statistics, so every query in the demo actually returns rows. Sizes
grow with the square root of the real row count, which keeps nested-loop plans
fast enough to run interactively while preserving which tables are big.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from ..cost.statistics import StatsStore, TableStats

_SEED = 7

# Readable values for text columns that the example queries filter on.
_TEXT_DOMAINS: dict[tuple[str, str], list[str]] = {
    ("departments", "name"): [
        "CSE", "ECE", "MECH", "CIVIL", "IT", "EEE", "CHEM", "BIO", "AERO", "AUTO",
        "MATH", "PHY", "MBA", "ARCH", "TEXT", "MINING", "META", "PROD", "INST", "ENV",
    ],
    ("students", "city"): ["Pune", "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
    ("departments", "building"): ["A", "B", "C", "D", "E", "F", "G", "H"],
}


def sample_size(rows: int) -> int:
    """Rows to generate for a table that really has ``rows`` rows."""
    return min(rows, 20 + math.isqrt(rows))


@dataclass
class SampleDatabase:
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    real_rows: dict[str, int] = field(default_factory=dict)

    def rows(self, table: str) -> list[dict[str, Any]]:
        return self.tables.get(table.lower(), [])

    def columns(self, table: str) -> list[str]:
        rows = self.rows(table)
        return list(rows[0].keys()) if rows else []

    def summary(self) -> list[dict[str, Any]]:
        return [
            {"table": name, "sampleRows": len(rows), "realRows": self.real_rows.get(name, 0)}
            for name, rows in self.tables.items()
        ]


def build_sample_database(stats: StatsStore) -> SampleDatabase:
    rng = random.Random(_SEED)
    sizes = {name: sample_size(table.rows) for name, table in stats.tables.items()}
    database = SampleDatabase()
    for name, table in stats.tables.items():
        database.tables[name] = _generate_table(table, sizes, rng)
        database.real_rows[name] = table.rows
    return database


def _referenced_table(column: str, sizes: dict[str, int]) -> str | None:
    """``dept_id`` -> ``departments``: a foreign key names the table it points at."""
    if not column.endswith("_id"):
        return None
    prefix = column[: -len("_id")]
    for table in sizes:
        if table.startswith(prefix):
            return table
    return None


def _generate_table(table: TableStats, sizes: dict[str, int], rng: random.Random) -> list[dict[str, Any]]:
    count = sizes[table.name.lower()]
    rows: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        row: dict[str, Any] = {}
        for key, column in table.columns.items():
            row[key] = _value(table.name.lower(), key, column, index, count, sizes, rng)
        rows.append(row)
    return rows


def _value(table: str, key: str, column, index: int, count: int, sizes: dict[str, int], rng: random.Random) -> Any:
    if key == "id":
        return index
    domain = _TEXT_DOMAINS.get((table, key))
    if domain is not None:
        # Unique columns (one value per row) walk the domain; others sample it.
        return domain[(index - 1) % len(domain)] if column.distinct >= count else rng.choice(domain)
    referenced = _referenced_table(key, sizes)
    if referenced is not None:
        return rng.randint(1, sizes[referenced])
    if column.data_type == "float":
        low, high = column.min_value or 0.0, column.max_value if column.max_value is not None else 10.0
        return round(rng.uniform(low, high), 2)
    if column.data_type == "integer":
        if column.min_value is not None and column.max_value is not None:
            return rng.randint(int(column.min_value), int(column.max_value))
        return rng.randint(1, max(1, min(column.distinct or count, count)))
    # Generic text: unique columns get one value per row, others repeat.
    # A table's name/title column is labelled after the table ("Student 12").
    label = table.rstrip("s").title() if key in ("name", "title") else key.replace("_", " ").title()
    distinct = column.distinct or count
    number = index if distinct >= count else rng.randint(1, distinct)
    return f"{label} {number}"
