"""Shared FastAPI dependencies."""
from __future__ import annotations

import os
from functools import lru_cache

from ..services.pipeline import QueryPipeline


@lru_cache(maxsize=1)
def get_pipeline() -> QueryPipeline:
    stats_path = os.environ.get("SMART_SQL_STATS")
    return QueryPipeline(stats_path=stats_path)
