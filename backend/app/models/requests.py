"""Pydantic request models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SqlRequest(BaseModel):
    sql: str = Field(..., description="The SQL query to process.", min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "sql": (
                    "SELECT s.name, d.name FROM students s "
                    "INNER JOIN departments d ON s.dept_id = d.id "
                    "WHERE s.cgpa > 8.0 AND d.name = 'CSE';"
                )
            }
        }
    }
