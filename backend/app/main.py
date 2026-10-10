"""queryX — Explainable Cost-Based SQL Query Optimizer (FastAPI application)."""
from __future__ import annotations

try:  # pragma: no cover - optional convenience
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .services.examples import get_examples
from .services.pipeline import QueryPipeline

app = FastAPI(
    title="queryX",
    description=(
        "An explainable cost-based SQL query optimizer. Exposes the complete "
        "compiler pipeline: lexer, parser, AST, semantic analysis, relational IR, "
        "rule-based optimization, physical planning, cost estimation, plan "
        "selection and human-readable explanations."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "queryX",
        "description": "Explainable cost-based SQL query optimizer",
        "docs": "/docs",
        "endpoints": [
            "POST /api/compile",
            "POST /api/lex",
            "POST /api/parse",
            "POST /api/analyze",
            "POST /api/optimize",
            "POST /api/plans",
            "GET /api/schema",
            "GET /api/statistics",
            "GET /api/examples",
        ],
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/examples/seed", tags=["meta"])
def seed_example() -> dict:
    """Return the flagship demo query used in the README."""
    examples = get_examples()
    return next(e for e in examples if e["id"] == "join_pushdown")


def build_pipeline() -> QueryPipeline:
    """Factory used by scripts/tests to construct a fresh pipeline."""
    return QueryPipeline()
