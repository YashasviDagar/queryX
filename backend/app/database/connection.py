"""Optional PostgreSQL connection helper.

The custom optimizer is fully independent from PostgreSQL. This module only
exists to support *optional* real-execution validation and benchmarking when a
database is available. It is disabled unless ``DATABASE_ENABLED=true``.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def database_enabled() -> bool:
    return os.environ.get("DATABASE_ENABLED", "false").lower() in {"1", "true", "yes"}


def dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "queryx")
    user = os.environ.get("POSTGRES_USER", "queryx")
    password = os.environ.get("POSTGRES_PASSWORD", "queryx")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_connection():
    """Return a psycopg connection, or ``None`` when the database is disabled."""
    if not database_enabled():
        return None
    try:
        import psycopg  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return psycopg.connect(dsn())


def run_explain(sql: str) -> Optional[dict[str, Any]]:
    """Run ``EXPLAIN (FORMAT JSON)`` for optional comparison. Never required."""
    connection = get_connection()
    if connection is None:
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}")
            return {"explain": cursor.fetchone()[0]}
    finally:
        connection.close()
