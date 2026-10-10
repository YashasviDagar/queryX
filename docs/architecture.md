# Architecture

`queryX` is split into a stateless FastAPI backend that owns the compiler pipeline and a React
frontend that visualizes every stage. PostgreSQL is optional and never used by the optimizer.

## High-level view

```
┌──────────────────────────── Frontend ────────────────────────────┐
│  React + TypeScript + Vite + Tailwind                             │
│  React Flow (AST / IR / plan graphs) · Recharts (cost analytics)  │
│                                                                    │
│  store/QueryProvider ──> services/api.ts ──> POST /api/optimize    │
└───────────────────────────────┬────────────────────────────────────┘
                                 │ JSON
┌───────────────────────────────▼────────────────────────────────────┐
│  FastAPI (app/main.py)                                             │
│  api/routes.py ──> services/pipeline.py (QueryPipeline)            │
│                                                                    │
│  compiler/                                                         │
│    lexer      → tokens.py, lexer.py, errors.py                     │
│    parser     → parser.py                                          │
│    ast        → nodes.py                                           │
│    semantic   → catalog.py, analyzer.py                            │
│    ir         → nodes.py, builder.py, expr.py                      │
│    optimizer  → engine.py, records.py, rules/*                     │
│    planner    → physical.py, generator.py, selector.py             │
│    cost       → statistics.py, cardinality.py, model.py, config.py │
│    explain    → engine.py                                          │
│                                                                    │
│  database/    → optional PostgreSQL (disabled by default)          │
└────────────────────────────────────────────────────────────────────┘
```

## Request lifecycle (`QueryPipeline.compile`)

1. **Lex** — `tokenize(sql)` returns `Token[]`. A `LexError` short-circuits with a diagnostic.
2. **Parse** — `parse(tokens)` returns an `ast.Query`. A `ParseError` short-circuits.
3. **Analyze** — `SemanticAnalyzer(catalog).analyze(query)` returns a `SemanticResult`.
   If invalid, the response includes all diagnostics and stops.
4. **Build IR** — `build_ir(query, catalog, semantic)` returns the logical plan.
5. **Optimize** — `OptimizerEngine(stats, config, expr_ctx).optimize(ir)` applies the rule
   pipeline on a deep copy and returns optimized IR + records.
6. **Plan** — `PhysicalPlanGenerator(stats, config, expr_ctx).generate(optimized_ir)` returns
   candidate physical plans.
7. **Cost** — `CostEstimator` annotates each candidate with rows/cost/memory/operations.
8. **Select** — `PlanSelector` marks the minimum-cost plan and ranks all candidates.
9. **Explain** — `ExplainEngine` produces narratives and the selection reason.

## Design principles

- **Separation of concerns.** Each compiler stage is a package with a single public entry
  point; the API layer only orchestrates.
- **Structured diagnostics.** One `CompilerError` type carries `code`, `message`, `stage`,
  `line`, `column`, `suggestion`.
- **Immutable source of truth.** `statistics.yaml` defines schema, statistics, indexes and
  cost constants; both the semantic catalog and the cost model derive from it.
- **Extensibility.** Optimizer rules implement a tiny `Rule` interface and are registered in
  `optimizer/rules/__init__.py`; adding a rule requires no engine changes.
- **Explainability first.** Rules must return `RuleFinding`s (reason + before/after) — a rule
  that changes the plan silently is not allowed.

## Frontend state flow

`QueryProvider` holds the current SQL, the last `CompileResult`, loading/error state and the
example list. The **Run & Optimize** button calls `api.optimize(sql)` and stores the result;
every page then derives its view from that single result. Theme (dark/light) is managed by
`ThemeProvider` and persisted to `localStorage`.
