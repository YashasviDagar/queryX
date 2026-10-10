"""Schema catalog.

The catalog is the semantic analyzer's view of the database: which tables
exist, which columns they contain and what types those columns have. It is
built from the same statistics file used by the cost model so that the two
stages stay consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnDef:
    name: str
    data_type: str
    nullable: bool = True
    distinct: int = 0
    is_indexed: bool = False

    @property
    def is_numeric(self) -> bool:
        return self.data_type in {"integer", "float", "bigint", "numeric"}


@dataclass
class TableDef:
    name: str
    columns: dict[str, ColumnDef] = field(default_factory=dict)
    rows: int = 0
    indexes: list[str] = field(default_factory=list)

    def column(self, name: str) -> Optional[ColumnDef]:
        return self.columns.get(name.lower())

    def column_names(self) -> list[str]:
        return list(self.columns.keys())


class Catalog:
    """In-memory schema used for semantic validation."""

    def __init__(self, tables: Optional[dict[str, TableDef]] = None) -> None:
        self.tables: dict[str, TableDef] = tables or {}

    def add_table(self, table: TableDef) -> None:
        self.tables[table.name.lower()] = table

    def get(self, name: str) -> Optional[TableDef]:
        return self.tables.get(name.lower())

    def exists(self, name: str) -> bool:
        return name.lower() in self.tables

    def table_names(self) -> list[str]:
        return sorted(self.tables.keys())

    def to_dict(self) -> dict:
        return {
            "tables": [
                {
                    "name": t.name,
                    "rows": t.rows,
                    "indexes": t.indexes,
                    "columns": [
                        {
                            "name": c.name,
                            "dataType": c.data_type,
                            "nullable": c.nullable,
                            "distinct": c.distinct,
                            "indexed": c.is_indexed,
                        }
                        for c in t.columns.values()
                    ],
                }
                for t in self.tables.values()
            ]
        }
