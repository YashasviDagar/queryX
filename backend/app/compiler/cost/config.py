"""Configurable constants for the educational cost model.

Every constant is transparent and adjustable so the optimizer's behaviour can
be explained and experimented with. These are *not* calibrated against a real
database engine.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Any

import yaml

DEFAULT_STATS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "statistics.yaml"
)


@dataclass
class CostConfig:
    cpu_tuple_cost: float = 0.01
    cpu_operator_cost: float = 0.0025
    seq_page_cost: float = 1.0
    random_page_cost: float = 4.0
    rows_per_page: int = 100
    index_startup_cost: float = 4.0
    index_tuple_cost: float = 0.5
    hash_build_cost: float = 0.05
    hash_probe_cost: float = 0.02
    merge_cost: float = 0.015
    sort_cpu_cost: float = 0.02
    sort_comparison_cost: float = 0.001
    aggregate_cost: float = 0.02
    bytes_per_row: int = 120
    equality_selectivity: float = 0.0
    range_selectivity: float = 0.125
    inequality_selectivity: float = 0.9
    default_selectivity: float = 0.33
    min_rows: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CostConfig":
        if not data:
            return cls()
        allowed = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in allowed}
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def load_cost_config(path: str | None = None) -> CostConfig:
    """Load the ``cost:`` section from the statistics YAML file."""
    config_path = path or DEFAULT_STATS_PATH
    if not os.path.exists(config_path):
        return CostConfig()
    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return CostConfig.from_dict(data.get("cost"))
