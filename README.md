# queryX — An Explainable Cost-Based SQL Query Optimizer

> An academic **Compiler Design** project that implements a complete, from-scratch SQL
> compiler pipeline: lexing, parsing, AST construction, semantic analysis, relational
> intermediate representation, rule-based optimization, physical plan generation,
> cardinality estimation, cost-based plan selection and — the primary novelty —
> **human-readable explanations for every decision**.

`queryX` is **not** a SQL editor, a database CRUD app, or a wrapper around PostgreSQL's
optimizer. The optimizer is implemented independently in Python; PostgreSQL is optional and
used only for benchmark validation.

---

## Table of contents

1. [Problem statement](#1-problem-statement)
2. [Objectives](#2-objectives)
3. [Existing approach](#3-existing-approach)
4. [Research gap](#4-research-gap)
5. [Proposed system](#5-proposed-system)
6. [Novelty](#6-novelty)
7. [Compiler design concepts used](#7-compiler-design-concepts-used)
8. [Architecture](#8-architecture)
9. [Grammar](#9-grammar)
10. [Lexer](#10-lexer)
11. [Parser](#11-parser)
12. [AST](#12-ast)
13. [Semantic analysis](#13-semantic-analysis)
14. [Intermediate representation](#14-intermediate-representation)
15. [Optimization](#15-optimization)
16. [Cost model](#16-cost-model)
17. [Physical plan generation](#17-physical-plan-generation)
18. [Evaluation metrics](#18-evaluation-metrics)
19. [Limitations](#19-limitations)
20. [Future scope](#20-future-scope)
21. [Getting started](#21-getting-started)
22. [Project structure](#22-project-structure)
23. [API reference](#23-api-reference)
24. [Testing](#24-testing)
25. [Final demo flow](#25-final-demo-flow)

---

## 1. Problem statement

Database query optimizers make critical performance decisions — join order, join algorithm,
access path — but their reasoning is largely opaque to learners and developers. Textbooks
describe *concepts* (predicate pushdown, cost models, plan enumeration) in isolation, while
real engines hide the transformation pipeline behind an `EXPLAIN` output. There is a need for
a system that (a) implements the whole compiler-style optimization pipeline from first
principles, and (b) makes every transformation and the final plan choice **explicit,
inspectable and explainable**.

## 2. Objectives

- Implement a complete SQL compiler front end: lexer → parser → AST → semantic analyzer.
- Lower the AST to a relational-algebra intermediate representation.
- Implement rule-based logical optimizations with explicit before/after records.
- Generate multiple alternative physical plans (access paths + join algorithms + join orders).
- Implement a transparent, configurable cardinality and cost model.
- Perform cost-based plan selection and retain **all** candidates for comparison.
- Explain *why* each rule fired and *why* the winning plan won.
- Visualize every stage in an interactive dashboard.

## 3. Existing approach

Production optimizers (PostgreSQL, Oracle, SQL Server) use sophisticated cost-based
optimizers with extensive statistics, histograms, and hundreds of transformation rules.
Academic tools such as Calcite, Apache Spark Catalyst, and classic textbook projects
implement subsets of this pipeline, but typically either:

- expose only the final plan (`EXPLAIN`), or
- focus on a single stage (e.g., parsing, or cost estimation), or
- are tightly coupled to a specific execution engine.

## 4. Research gap

There is a gap between **theory** (compiler/optimizer algorithms taught as abstract concepts)
and **practice** (engines that hide their reasoning). Few systems provide an end-to-end,
runnable, *explainable* optimizer that shows the token stream, AST, IR, each rewrite with its
estimated impact, multiple costed candidate plans, and a natural-language justification for
the selected plan — all in one place, with a from-scratch implementation.

## 5. Proposed system

`queryX` implements the entire pipeline independently:

```
SQL source
  → Lexer            → Token stream
  → Parser           → AST
  → Semantic Analyzer→ validated AST + diagnostics
  → IR Builder       → relational algebra (SCAN/FILTER/PROJECT/JOIN/AGGREGATE/SORT/LIMIT)
  → Rule Optimizer   → optimized IR + optimization records
  → Plan Generator   → candidate physical plans
  → Cardinality Est. → estimated rows
  → Cost Model       → estimated cost / memory / operations
  → Plan Selector    → minimum-cost plan (+ all candidates)
  → Explain Engine   → natural-language reasoning
  → Visualized plan  → interactive dashboard
```

## 6. Novelty

> **An explainable cost-based SQL optimizer that exposes the complete compiler-style
> transformation pipeline and provides transparent reasoning for optimization rules and
> physical plan selection.**

The novelty is **not** cost-based optimization itself (that is well established). The novelty
is the *educational, explainable integration*: every rule emits a structured record
(`rule`, `before`, `after`, `reason`, `estimatedImpact`), every candidate plan is costed and
shown, and the final choice is justified with numbers. The pipeline is visualized end to end.

## 7. Compiler design concepts used

| Concept | Where it appears |
|---|---|
| Lexical analysis (scanning) | `compiler/lexer` |
| Token stream & symbol tables | `Token`, `Catalog` |
| Context-free grammar | `docs/grammar.md` |
| Recursive-descent parsing | `compiler/parser` |
| Abstract syntax tree | `compiler/ast` |
| Semantic analysis / type checking | `compiler/semantic` |
| Intermediate representation | `compiler/ir` (relational algebra) |
| Peephole / rule-based optimization | `compiler/optimizer` |
| Constant folding | `ConstantFolding` rule |
| Algebraic rewriting (pushdown, pruning) | `PredicatePushdown`, `ProjectionPruning` |
| Cost model & cardinality estimation | `compiler/cost` |
| Plan enumeration & selection | `compiler/planner` |
| Diagnostics with source locations | `CompilerError` |

## 8. Architecture

```
┌──────────────────────────────── Frontend (React + TypeScript + Vite) ────────────────────────────────┐
│  Editor · Tokens · AST (React Flow) · IR · Optimization timeline · Plans · Analytics (Recharts) · Schema │
└───────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                                 │ REST /api/*
┌──────────────────────────────── Backend (FastAPI) ────────────────────────────────────────────────────┐
│ api → services.pipeline → compiler.{lexer,parser,ast,semantic,ir,optimizer,planner,cost,explain}      │
│ database (optional, PostgreSQL)                                                                       │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for details.

## 9. Grammar

A controlled SQL subset is supported (SELECT/FROM/WHERE/INNER JOIN/GROUP BY/HAVING/ORDER BY/LIMIT,
aliases, AND/OR/NOT, arithmetic, comparisons, `COUNT/SUM/AVG/MIN/MAX`). The full EBNF is in
[`docs/grammar.md`](docs/grammar.md).

## 10. Lexer

`app/compiler/lexer` converts SQL text into `Token(type, lexeme, line, column)`.

- Keywords (case-insensitive), identifiers, integers, floats (incl. exponent), strings
  (with `''` escaping), arithmetic operators, comparison operators (`= <> != < <= > >=`),
  parentheses, commas, semicolons, dots.
- Skips whitespace, `--` line comments and `/* ... */` block comments.
- Emits structured `LEX00x` errors with location and suggestion.

## 11. Parser

A recursive-descent parser (`app/compiler/parser`) with precedence:

```
OR  <  AND  <  NOT  <  comparison  <  additive  <  multiplicative  <  primary
```

It produces a typed AST and reports `PAR00x` syntax errors with positions.

## 12. AST

Typed dataclass nodes (`app/compiler/ast/nodes.py`): `Query, Select, From, Join, Where,
GroupBy, OrderBy, OrderByItem, Limit, Column, Table, Alias, BinaryExpression, Literal,
FunctionCall, Comparison, LogicalExpression`. Every node serializes to JSON with a source
position, exposed at `POST /api/parse`.

## 13. Semantic analysis

`app/compiler/semantic` validates the AST against a catalog and **collects all errors**
instead of failing fast. Checks include: unknown tables/columns, ambiguous columns, duplicate
aliases, invalid joins, unsupported outer joins (`SEM017`), aggregates in `WHERE`, non-grouped
select columns (enforced with or without a `GROUP BY` clause), `HAVING` predicates over
ungrouped columns (`SEM018`), unknown functions, and
type-compatibility of comparisons/arithmetic. Diagnostics carry a code (`SEM0xx`),
message, location and a suggested fix.

## 14. Intermediate representation

`app/compiler/ir` lowers the AST to relational algebra:

```
SCAN(table) · FILTER(condition) · PROJECT(columns) · DISTINCT(columns) · JOIN(left, right, condition)
AGGREGATE(functions, group_by) · SORT(columns) · LIMIT(n)
```

Example: `SELECT s.name FROM students s WHERE s.cgpa > 8;` becomes
`PROJECT(name) → FILTER(cgpa > 8) → SCAN(students)`.

## 15. Optimization

`app/compiler/optimizer` applies, in order:

1. **Constant Folding** — evaluate literal-only expressions.
2. **Redundant Condition Removal** — collapse duplicate predicates.
3. **Predicate Pushdown** — move filters next to scans / into join conditions.
4. **Projection Pruning** — drop columns no operator needs.
5. **Join Reordering** — order inner joins by ascending estimated cardinality.

Each transformation creates an `OptimizationRecord`:
`{ rule, before, after, reason, estimatedImpact }`, where `estimatedImpact` reports rows and
logical cost before/after (with an operator-level metric such as *rows entering the join*).
Details and extension guidance: [`docs/optimization-rules.md`](docs/optimization-rules.md).

## 16. Cost model

`app/compiler/cost` implements a transparent, configurable educational model:

- **Cardinality:** equality `1/distinct`, column-vs-column `1/max(distinct)`, configurable
  range selectivity, `AND` = product, `OR` = `s1+s2-s1·s2`, join selectivity derived from
  column cardinalities.
- **Cost:** sequential vs random I/O (`seq_page_cost`, `random_page_cost`), per-tuple CPU,
  index startup + fetch, hash build/probe, merge, sort comparisons, aggregation.
- **Outputs per plan:** `estimated_rows`, `estimated_cost`, `estimated_memory`,
  `estimated_operations`.

> **Important:** this is an educational estimate for *comparison and explanation*. It is **not**
> a prediction of real wall-clock execution time. All constants live in
> `app/compiler/config/statistics.yaml` and are shown in the UI.

Full derivation: [`docs/cost-model.md`](docs/cost-model.md).

## 17. Physical plan generation

`app/compiler/planner` enumerates candidates over:

- **Access paths:** sequential scan, index scan (when an index covers a predicate column).
- **Join algorithms:** hash join, nested-loop join, merge join.
- **Join orders:** as-written and cardinality-sorted.

All candidates are costed; the selector picks the minimum-cost valid plan and returns every
candidate plus a ranked comparison.

## 18. Evaluation metrics

- Number of optimization rules applied and distinct rules used.
- Estimated rows before/after each rule (absolute and percentage reduction).
- Estimated logical cost before/after each rule.
- Number of candidate plans generated and the cost spread.
- Selected-plan cost, rows, memory and operations, and savings vs the next-best plan.
- Plan-generation and total-compile time (milliseconds).

## 19. Limitations

- Supports a controlled SQL subset (no subqueries, `UNION`, window functions, or CTEs).
  `LEFT`/`RIGHT` joins are parsed but rejected during semantic analysis with diagnostic
  `SEM017`; only `INNER` joins are optimized.
- Selectivity uses simple uniformity/independence assumptions (no histograms). `HAVING`
  predicates use the default selectivity, since statistics do not describe aggregate values.
- Cost constants are illustrative, not calibrated to a real engine.
- Join enumeration is bounded (heuristics for larger join graphs).
- Statistics are static (no `ANALYZE`/adaptive estimation).
- Index scans model only single-column b-tree indexes.

## 20. Future scope

- Histograms and multi-dimensional statistics for better selectivity.
- Bushy join trees and dynamic-programming join enumeration (Selinger-style).
- More rules: join elimination, subquery decorrelation, common subexpression elimination,
  sort elimination, aggregate pushdown.
- Subqueries, `UNION`, outer joins, window functions.
- Parallel and memory-aware cost modeling.
- Optional real-execution validation and cost-model calibration against PostgreSQL.
- Rule-plugin API and an interactive rule editor.

---

## 21. Getting started

### Prerequisites

- **Python 3.10+** (tested on 3.12)
- **Node.js 18+** (tested on Node 24)
- PostgreSQL is **optional** (only for benchmark validation)

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API root: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The app targets `http://localhost:8000` by default; override with
`VITE_API_URL`:

```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000
```

### Optional PostgreSQL (benchmark validation only)

```bash
docker compose up -d
cd backend
# set DATABASE_ENABLED=true in .env (see .env.example)
python -m app.database.seed
python -m app.database.benchmark
```

The custom optimizer never calls PostgreSQL; this is only for comparing against a real engine.

### Full app with Docker (optional)

```bash
docker compose --profile app up --build
```

Serves the API on http://localhost:8000 and the UI on http://localhost:5173. Plain
`docker compose up -d` still starts only PostgreSQL.

---

## 22. Project structure

```
queryX/
├── frontend/                      React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── components/            Layout, Card, Badge, Tabs, DataTable, TreeGraph, …
│       ├── pages/                 Editor, Tokens, Ast, IR, Optimization, Plans, Analytics, Schema
│       ├── features/
│       │   ├── editor/            SqlEditor, ExamplePicker
│       │   ├── lexer/             TokenTable
│       │   ├── ast/               AstGraph (React Flow)
│       │   ├── optimizer/         OptimizationTimeline, OptimizationCard
│       │   ├── plans/             PlanTree, PlanCard
│       │   ├── explainability/    ExplanationPanel
│       │   └── analytics/         CostChart, RowsChart, ImpactStats
│       ├── services/api.ts        Typed API client
│       ├── store/                 Query + Theme providers
│       ├── types/                 Shared TypeScript models
│       ├── App.tsx, main.tsx
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI app + CORS
│   │   ├── api/                   REST routes + deps
│   │   ├── models/                Pydantic request/response models
│   │   ├── services/              pipeline.py, examples.py
│   │   ├── compiler/
│   │   │   ├── lexer/             tokens.py, lexer.py, errors.py
│   │   │   ├── parser/            parser.py
│   │   │   ├── ast/               nodes.py
│   │   │   ├── semantic/          catalog.py, analyzer.py
│   │   │   ├── ir/                nodes.py, builder.py, expr.py
│   │   │   ├── optimizer/         engine.py, records.py, rules/
│   │   │   ├── planner/           physical.py, generator.py, selector.py
│   │   │   ├── cost/              statistics.py, cardinality.py, model.py, config.py
│   │   │   ├── explain/           engine.py
│   │   │   └── config/            statistics.yaml
│   │   └── database/              connection.py, schema.sql, seed.py, benchmark.py
│   ├── tests/                     pytest unit + integration tests
│   └── requirements.txt
├── docs/                          architecture.md, grammar.md,
│                                  optimization-rules.md, cost-model.md
├── docker-compose.yml             optional PostgreSQL
└── README.md
```

## 23. API reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/compile` | Full pipeline output |
| POST | `/api/lex` | Token stream |
| POST | `/api/parse` | AST |
| POST | `/api/analyze` | Semantic diagnostics |
| POST | `/api/optimize` | Full bundle (see below) |
| POST | `/api/plans` | Candidate plans + selection |
| GET | `/api/schema` | Tables, columns, indexes |
| GET | `/api/statistics` | Statistics + cost constants |
| GET | `/api/examples` | Curated example queries |

Request body for POST endpoints: `{ "sql": "SELECT ..." }`.

`POST /api/optimize` returns:

```json
{
  "success": true,
  "query": "…",
  "tokens": [ … ],
  "ast": { … },
  "semanticErrors": [],
  "relationalIR": { … },
  "optimizedIR": { … },
  "optimizationSteps": [
    {
      "rule": "Predicate Pushdown",
      "before": "FILTER(s.cgpa > 8.0) above JOIN",
      "after": "FILTER(s.cgpa > 8.0) pushed into LEFT input",
      "reason": "Predicate 's.cgpa > 8.0' references only ['s']; …",
      "estimatedImpact": {
        "metricLabel": "rows entering the join",
        "estimatedRowsBefore": 100020, "estimatedRowsAfter": 12501,
        "estimatedCostBefore": 22257.45, "estimatedCostAfter": 2382.5
      }
    }
  ],
  "candidatePlans": [ … ],
  "selectedPlan": { … },
  "costComparison": [ … ],
  "explanation": {
    "summary": "…",
    "optimizationExplanations": [ … ],
    "planSelection": { "selectedPlan": "Plan C", "reason": "…" }
  },
  "metrics": { "totalMs": 3.6, "planGenerationMs": 0.5, "candidateCount": 6 }
}
```

## 24. Testing

```bash
# Backend
cd backend
pytest -q

# Frontend
cd frontend
npm test          # Vitest + Testing Library
npm run lint      # tsc --noEmit
```

Backend coverage: lexer, parser, AST serialization, semantic analyzer, IR builder, every
optimization rule, the cost/cardinality model, the planner/selector, the REST routes (via
FastAPI `TestClient`), diagnostic codes, and full end-to-end queries (valid and invalid).
123 tests, all passing. Frontend: API client, `QueryProvider`, `PlanCard` and
`OptimizationCard`. 17 tests, all passing.

CI (`.github/workflows/ci.yml`) runs the backend tests and the frontend lint, test and build
on every push and pull request.

## 25. Final demo flow

1. Enter the SQL query (pre-loaded with the flagship example).
2. **Tokens** — inspect the lexer output with positions.
3. **AST** — explore the syntax tree.
4. **Semantic** — diagnostics shown inline in the editor.
5. **Relational IR** — view the logical plan.
6. Click **Run & Optimize**.
7. **Optimization** — see each rule with before/after and estimated impact.
8. Compare estimated rows before/after each rule.
9. **Plans** — inspect multiple physical plans.
10. Compare estimated costs (chart + table).
11. See the selected plan highlighted.
12. Read the explanation of why it was selected.

### Seeded example

```sql
SELECT s.name, d.name
FROM students s
INNER JOIN departments d ON s.dept_id = d.id
WHERE s.cgpa > 8.0 AND d.name = 'CSE';
```

Original logical plan:

```
PROJECT s.name, d.name
  FILTER s.cgpa > 8.0 AND d.name = 'CSE'
    INNER JOIN ON s.dept_id = d.id
      SCAN students AS s
      SCAN departments AS d
```

After predicate pushdown:

```
PROJECT s.name, d.name
  INNER JOIN ON s.dept_id = d.id
    FILTER d.name = 'CSE' → SCAN departments AS d
    FILTER s.cgpa > 8.0   → SCAN students AS s
```

The optimizer then generates six candidate plans (hash/nested-loop/merge × sequential/index
scans × join orders), costs each, and selects the minimum-cost plan — with a full explanation.
The exact winning plan depends on the configured statistics and cost constants; adjust
`backend/app/compiler/config/statistics.yaml` and re-run to see the decision change.

---

## License

Academic project — provided for educational use.
