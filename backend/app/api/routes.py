"""REST API routes.

Every endpoint is a thin wrapper over :class:`QueryPipeline`; all compiler
logic lives in the ``compiler`` package.
"""
from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, Depends

from ..models.requests import SqlRequest
from ..models.responses import (
    AnalyzeResponse,
    ExampleOut,
    LexResponse,
    ParseResponse,
    SchemaResponse,
    StatisticsResponse,
)
from ..services.examples import get_examples
from ..services.pipeline import QueryPipeline
from ..services.random_query import random_query
from .deps import get_pipeline

router = APIRouter()


@router.post("/lex", response_model=LexResponse, tags=["compiler"])
def lex(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> LexResponse:
    """Tokenize a SQL string and return the token stream."""
    return LexResponse(**pipeline.lex(request.sql))


@router.post("/parse", response_model=ParseResponse, tags=["compiler"])
def parse(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> ParseResponse:
    """Parse SQL into an abstract syntax tree."""
    return ParseResponse(**pipeline.parse(request.sql))


@router.post("/analyze", response_model=AnalyzeResponse, tags=["compiler"])
def analyze(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> AnalyzeResponse:
    """Run semantic analysis and return diagnostics."""
    return AnalyzeResponse(**pipeline.analyze(request.sql))


@router.post("/optimize", tags=["compiler"])
def optimize(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> dict:
    """Run the complete pipeline and return the full optimization bundle."""
    return pipeline.compile(request.sql)


@router.post("/compile", tags=["compiler"])
def compile_query(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> dict:
    """Alias of /optimize returning the complete compiler output."""
    return pipeline.compile(request.sql)


@router.post("/plans", tags=["compiler"])
def plans(request: SqlRequest, pipeline: QueryPipeline = Depends(get_pipeline)) -> dict:
    """Return only the candidate plans, cost comparison and selection."""
    result = pipeline.compile(request.sql)
    return {
        "success": result.get("success", False),
        "errors": result.get("errors", []),
        "semanticErrors": result.get("semanticErrors", []),
        "candidatePlans": result.get("candidatePlans", []),
        "selectedPlan": result.get("selectedPlan"),
        "costComparison": result.get("costComparison", []),
        "explanation": (result.get("explanation") or {}).get("planSelection"),
    }


@router.get("/schema", response_model=SchemaResponse, tags=["metadata"])
def schema(pipeline: QueryPipeline = Depends(get_pipeline)) -> SchemaResponse:
    """Return the logical schema (tables, columns, indexes)."""
    return SchemaResponse(**pipeline.schema())


@router.get("/statistics", response_model=StatisticsResponse, tags=["metadata"])
def statistics(pipeline: QueryPipeline = Depends(get_pipeline)) -> StatisticsResponse:
    """Return table/column statistics and the active cost constants."""
    return StatisticsResponse(**pipeline.statistics())


@router.get("/examples", response_model=list[ExampleOut], tags=["metadata"])
def examples() -> list[ExampleOut]:
    """Return curated example queries."""
    return [ExampleOut(**example) for example in get_examples()]


@router.get("/random", tags=["metadata"])
def random_sql(seed: Optional[int] = None, pipeline: QueryPipeline = Depends(get_pipeline)) -> dict:
    """Generate a random query that is valid for the grammar and schema."""
    return random_query(pipeline.database, random.Random(seed))
