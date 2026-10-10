"""Pydantic response models for the stable endpoints."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ErrorOut(BaseModel):
    code: str
    message: str
    stage: str
    line: int = 0
    column: int = 0
    suggestion: Optional[str] = None
    location: Optional[dict[str, int]] = None


class TokenOut(BaseModel):
    type: str
    lexeme: str
    line: int
    column: int
    value: Any = None
    category: Optional[str] = None


class LexResponse(BaseModel):
    success: bool
    tokens: list[TokenOut] = []
    errors: list[ErrorOut] = []


class ParseResponse(BaseModel):
    success: bool
    ast: Optional[dict[str, Any]] = None
    tokens: list[TokenOut] = []
    errors: list[ErrorOut] = []


class AnalyzeResponse(BaseModel):
    success: bool
    ast: Optional[dict[str, Any]] = None
    semantic: Optional[dict[str, Any]] = None
    errors: list[ErrorOut] = []


class SchemaResponse(BaseModel):
    tables: list[dict[str, Any]] = []


class StatisticsResponse(BaseModel):
    tables: list[dict[str, Any]] = []
    costConfig: dict[str, Any] = {}


class ExampleOut(BaseModel):
    id: str
    title: str
    description: str
    sql: str
