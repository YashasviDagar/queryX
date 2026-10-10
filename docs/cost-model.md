# Cost model

`queryX` uses a small, fully transparent cost model inspired by classical cost-based
optimizers. Its purpose is **comparison and explanation**, not predicting real wall-clock
execution time. All constants are configurable in
`backend/app/compiler/config/statistics.yaml` under the `cost:` key and are displayed in the
Schema & Stats page.

## Statistics

Each table stores a row count; each column stores a distinct-value count, nullability,
optional min/max, and whether it is indexed; each index lists its columns.

```yaml
students:
  rows: 100000
  columns:
    cgpa: {type: float, distinct: 500, min: 0, max: 10}
    dept_id: {type: integer, distinct: 20}
  indexes:
    - {name: students_cgpa_idx, columns: [cgpa]}
```

## Cardinality estimation

| Predicate | Selectivity |
|---|---|
| `col = literal` | `1 / distinct(col)` |
| `col <> literal` | `1 - 1/distinct(col)` |
| `col1 = col2` | `1 / max(distinct(col1), distinct(col2))` |
| `col < / <= / > / >= literal` | `range_selectivity` (default `0.125`, uniform assumption) |
| `A AND B` | `s(A) · s(B)` (independence) |
| `A OR B` | `s(A) + s(B) - s(A)·s(B)` |
| `NOT A` | `1 - s(A)` |
| constant | `1` (true) or `0` (false) |

Operator outputs:

- **Filter:** `rows_in · selectivity` (min `min_rows`).
- **Join:** `left_rows · right_rows · join_selectivity`.
- **Aggregate:** `min(rows_in, Π distinct(group keys))`, or `1` without `GROUP BY`.
- **Distinct:** `min(rows_in, Π distinct(projected columns))`; if any projected expression is
  computed (no statistics), conservatively `rows_in`.
- **Limit:** `min(rows_in, n)`. **Sort / Project:** unchanged.

## Cost formulas

Notation: `rows` = input rows, `pages = ceil(rows / rows_per_page)`.

| Operator | Estimated cost |
|---|---|
| Sequential Scan | `pages · seq_page_cost + rows · cpu_tuple_cost` |
| Index Scan | `index_startup_cost + selected · index_tuple_cost + selected · cpu_tuple_cost` |
| Filter | `child_cost + rows_in · cpu_operator_cost` |
| Nested Loop Join | `left + right + left_rows · right_rows · cpu_tuple_cost` |
| Hash Join | `left + right + build_rows · hash_build_cost + probe_rows · hash_probe_cost + out_rows · cpu_tuple_cost` |
| Merge Join | `left + right + (left_rows + right_rows) · merge_cost + out_rows · cpu_tuple_cost` |
| Sort | `child + n·log2(n)·sort_comparison_cost + n·sort_cpu_cost` |
| Distinct | `child + rows_in·(hash_build_cost + cpu_tuple_cost)` |
| Aggregate | `child + rows_in · aggregate_cost` (×2 when any aggregate is `DISTINCT`) |
| Project | `child + rows_in · cpu_tuple_cost` |
| Limit | `child + out_rows · cpu_tuple_cost` |

For hash joins the **build side** is the smaller child (recorded in the plan as `buildSide`).

## Memory and operations

- **Memory** is bytes: hash build ≈ `build_rows · bytes_per_row`, sort ≈ `rows · bytes_per_row`,
  aggregate ≈ `output_rows · bytes_per_row`. Scans use `0`.
- **Operations** approximate tuple work: comparisons for nested loop
  (`left_rows · right_rows`), input tuples for hash/merge joins, comparisons for sort.

## Default constants

| Constant | Default | Meaning |
|---|---|---|
| `cpu_tuple_cost` | 0.01 | per-tuple CPU |
| `cpu_operator_cost` | 0.0025 | per-predicate CPU |
| `seq_page_cost` | 1.0 | sequential page I/O |
| `random_page_cost` | 4.0 | random page I/O |
| `rows_per_page` | 100 | rows per page |
| `index_startup_cost` | 4.0 | index descent startup |
| `index_tuple_cost` | 0.5 | per-tuple index fetch |
| `hash_build_cost` | 0.05 | per-row hash build |
| `hash_probe_cost` | 0.02 | per-row hash probe |
| `merge_cost` | 0.015 | per-row merge |
| `sort_cpu_cost` | 0.02 | per-row sort CPU |
| `sort_comparison_cost` | 0.001 | per-comparison sort |
| `aggregate_cost` | 0.02 | per-row aggregation |
| `bytes_per_row` | 120 | memory accounting |
| `range_selectivity` | 0.125 | default range selectivity |
| `default_selectivity` | 0.33 | fallback |
| `min_rows` | 1 | lower bound on any estimate |

## Worked example

Query:

```sql
SELECT s.name, d.name
FROM students s
INNER JOIN departments d ON s.dept_id = d.id
WHERE s.cgpa > 8.0 AND d.name = 'CSE';
```

Statistics: `students.rows = 100000`, `departments.rows = 20`,
`students.dept_id.distinct = departments.id.distinct = 20`.

- `s.cgpa > 8.0` → `0.125` → **12 500** rows.
- `d.name = 'CSE'` → `1/20 = 0.05` → **1** row.
- Join selectivity `1/max(20,20) = 0.05`; output ≈ `12500 · 1 · 0.05 ≈ 625` rows.
- Rows entering the join fall from `100 000 + 20 = 100 020` to `12 500 + 1 = 12 501`
  (**87.5 % reduction**).

The planner then costs all candidates and selects the minimum-cost plan. Change the statistics
or constants and re-run to see the decision (and the explanation) change.

> **Disclaimer.** These numbers are educational estimates. They are not a prediction of real
> execution time and should not be used for production tuning.
