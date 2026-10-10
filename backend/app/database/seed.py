"""Seed the optional PostgreSQL benchmark database.

Usage (requires a running Postgres and DATABASE_ENABLED=true):

    python -m app.database.seed --students 100000 --enrollments 500000

This is entirely optional; the optimizer runs without a database.
"""
from __future__ import annotations

import argparse
import os
import random

from .connection import database_enabled, get_connection

HERE = os.path.dirname(__file__)

CITIES = ["Pune", "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"]
BUILDINGS = ["A", "B", "C", "D", "E", "F", "G", "H"]


def _apply_schema(connection) -> None:
    with open(os.path.join(HERE, "schema.sql"), "r", encoding="utf-8") as handle:
        script = handle.read()
    with connection.cursor() as cursor:
        cursor.execute(script)


def _seed(connection, students: int, enrollments: int) -> None:
    random.seed(42)
    departments = [
        ("CSE", "A", "Dr. Rao"),
        ("ECE", "B", "Dr. Iyer"),
        ("MECH", "C", "Dr. Khan"),
        ("CIVIL", "D", "Dr. Bose"),
        ("IT", "E", "Dr. Nair"),
    ]
    with connection.cursor() as cursor:
        for index, (name, building, head) in enumerate(departments, start=1):
            cursor.execute(
                "INSERT INTO departments (id, name, building, head) VALUES (%s, %s, %s, %s)",
                (index, name, building, head),
            )
        for sid in range(1, students + 1):
            cursor.execute(
                "INSERT INTO students (id, name, cgpa, dept_id, age, city) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    sid,
                    f"Student{sid}",
                    round(random.uniform(0, 10), 2),
                    random.randint(1, len(departments)),
                    random.randint(17, 25),
                    random.choice(CITIES),
                ),
            )
        for cid in range(1, 201):
            cursor.execute(
                "INSERT INTO courses (id, title, credits, dept_id) VALUES (%s, %s, %s, %s)",
                (cid, f"Course{cid}", random.choice([2, 3, 4]), random.randint(1, len(departments))),
            )
        for eid in range(1, enrollments + 1):
            cursor.execute(
                "INSERT INTO enrollments (id, student_id, course_id, grade) VALUES (%s, %s, %s, %s)",
                (eid, random.randint(1, students), random.randint(1, 200), round(random.uniform(0, 10), 2)),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the optional queryX benchmark database.")
    parser.add_argument("--students", type=int, default=100000)
    parser.add_argument("--enrollments", type=int, default=500000)
    args = parser.parse_args()

    if not database_enabled():
        print("DATABASE_ENABLED is not true; skipping database seed (this is optional).")
        return

    connection = get_connection()
    if connection is None:
        print("Could not connect to PostgreSQL; skipping seed.")
        return

    try:
        _apply_schema(connection)
        _seed(connection, args.students, args.enrollments)
        connection.commit()
        print(f"Seeded {args.students} students and {args.enrollments} enrollments.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
