"""Statistics store.

Loads table/column statistics and index metadata from a YAML configuration.
The store feeds both the semantic catalog and the cost model, so the two never
disagree about the shape of the database.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from ..semantic.catalog import Catalog, ColumnDef, TableDef

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "statistics.yaml"
)


@dataclass
class IndexStats:
    name: str
    columns: list[str]
    unique: bool = False
    index_type: str = "btree"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": self.columns,
            "unique": self.unique,
            "type": self.index_type,
        }


@dataclass
class ColumnStats:
    name: str
    data_type: str = "text"
    distinct: int = 0
    nullable: bool = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    indexed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dataType": self.data_type,
            "distinct": self.distinct,
            "nullable": self.nullable,
            "min": self.min_value,
            "max": self.max_value,
            "indexed": self.indexed,
        }


@dataclass
class TableStats:
    name: str
    rows: int = 0
    columns: dict[str, ColumnStats] = field(default_factory=dict)
    indexes: list[IndexStats] = field(default_factory=list)

    def column(self, name: str) -> Optional[ColumnStats]:
        return self.columns.get(name.lower())

    def to_dict(self) -> dict[str, Any]:
        indexed_columns = {
            index.columns[0].lower() for index in self.indexes if index.columns
        }
        return {
            "name": self.name,
            "rows": self.rows,
            "columns": [
                {**c.to_dict(), "indexed": c.indexed or c.name.lower() in indexed_columns}
                for c in self.columns.values()
            ],
            "indexes": [i.to_dict() for i in self.indexes],
        }


@dataclass
class StatsStore:
    tables: dict[str, TableStats] = field(default_factory=dict)

    def get(self, name: str) -> Optional[TableStats]:
        return self.tables.get(name.lower())

    def rows(self, name: str) -> int:
        table = self.get(name)
        return table.rows if table else 0

    def to_dict(self) -> dict[str, Any]:
        return {"tables": [t.to_dict() for t in self.tables.values()]}

    def to_catalog(self) -> Catalog:
        catalog = Catalog()
        for table in self.tables.values():
            indexed_columns = {
                index.columns[0].lower() for index in table.indexes if index.columns
            }
            columns = {
                name: ColumnDef(
                    name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    distinct=col.distinct,
                    is_indexed=col.indexed or name in indexed_columns,
                )
                for name, col in table.columns.items()
            }
            catalog.add_table(
                TableDef(
                    name=table.name,
                    columns=columns,
                    rows=table.rows,
                    indexes=[i.name for i in table.indexes],
                )
            )
        return catalog


def load_statistics(path: Optional[str] = None) -> StatsStore:
    config_path = path or DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    store = StatsStore()
    for table_data in data.get("tables", []):
        table = TableStats(
            name=table_data["name"],
            rows=int(table_data.get("rows", 0)),
        )
        for col_data in table_data.get("columns", []):
            table.columns[col_data["name"].lower()] = ColumnStats(
                name=col_data["name"],
                data_type=col_data.get("type", "text"),
                distinct=int(col_data.get("distinct", 0)),
                nullable=bool(col_data.get("nullable", True)),
                min_value=col_data.get("min"),
                max_value=col_data.get("max"),
                indexed=bool(col_data.get("indexed", False)),
            )
        for idx_data in table_data.get("indexes", []):
            if isinstance(idx_data, str):
                table.indexes.append(IndexStats(name=idx_data, columns=[idx_data]))
            else:
                table.indexes.append(
                    IndexStats(
                        name=idx_data["name"],
                        columns=list(idx_data.get("columns", [])),
                        unique=bool(idx_data.get("unique", False)),
                        index_type=idx_data.get("type", "btree"),
                    )
                )
        store.tables[table.name.lower()] = table
    return store
