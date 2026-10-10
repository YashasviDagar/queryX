# Optimization rules

The optimizer applies rules in a fixed order over a **deep copy** of the logical IR, so the
original relational plan is always preserved for comparison. Every rule returns zero or more
`RuleFinding`s; the engine turns them into `OptimizationRecord`s with estimated impact.

## Pipeline order

| # | Rule | Module |
|---|---|---|
| 1 | Constant Folding | `rules/constant_folding.py` |
| 2 | Redundant Condition Removal | `rules/redundant_conditions.py` |
| 3 | Predicate Pushdown | `rules/predicate_pushdown.py` |
| 4 | Projection Pruning | `rules/projection_pruning.py` |
| 5 | Join Reordering | `rules/join_reordering.py` |

The order matters: simplification first, then movement, then narrowing, then ordering.

---

## A. Predicate Pushdown

**Goal.** Evaluate `WHERE` predicates as close to the base tables as possible.

**Mechanism.** For a `Filter` above a `Join`, split the condition into conjuncts and partition
each conjunct by the scan keys it references:

- references only the left input → push below the join into the left input;
- references only the right input → push below the join into the right input;
- references both inputs → fold into the join condition;
- otherwise → keep above.

For a `LEFT` join only the first case applies: predicates on the preserved left input move down,
and anything touching the right input or both inputs stays above the join, because moving it
would change which left rows are null-extended. Join conditions of `LEFT` joins are never
extended with `WHERE` predicates for the same reason.

It also pushes through `Project`, `Distinct` and `Sort`, and through `Aggregate` for predicates
over grouping keys only. A predicate that contains an aggregate call (for example a `HAVING
COUNT(*) > 2`) depends on the groups themselves and always stays above the `Aggregate`. It never
pushes below `Limit` (that would change semantics).

**Record example.**

```json
{
  "rule": "Predicate Pushdown",
  "before": "FILTER(s.cgpa > 8.0) above JOIN",
  "after": "FILTER(s.cgpa > 8.0) pushed into LEFT input",
  "reason": "Predicate 's.cgpa > 8.0' references only ['s']; evaluating it before the join reduces the rows entering the join.",
  "estimatedImpact": {
    "metricLabel": "rows entering the join",
    "estimatedRowsBefore": 100020,
    "estimatedRowsAfter": 12501,
    "rowReduction": 87519,
    "rowReductionPercent": 87.5,
    "estimatedCostBefore": 22257.45,
    "estimatedCostAfter": 2382.5,
    "costReduction": 19874.95
  }
}
```

---

## B. Projection Pruning

**Goal.** Read only the columns the query needs.

**Mechanism.** Collect every column referenced by filters, join conditions, aggregates and
projections, then trim each `Scan.columns` to the intersection with the table's columns. If a
`SELECT *` was expanded earlier, no pruning occurs (all columns are required).

---

## C. Constant Folding

**Goal.** Evaluate literal-only expressions at optimization time.

**Mechanism.** Recursively fold `BinaryExpression`, `Comparison` and `LogicalExpression`
nodes whose operands are constants into `Literal`s. A filter whose predicate folds to `TRUE`
is removed; one that folds to `FALSE` is retained (it yields zero rows).

Example: `WHERE 2 + 3 < 10 AND s.cgpa > 7.5` → `WHERE s.cgpa > 7.5`.

---

## D. Redundant Condition Removal

**Goal.** Evaluate each predicate once.

**Mechanism.** Split conjunctions into conjuncts, canonicalize each (whitespace/case
normalized), drop duplicates, and rebuild. Example:
`WHERE s.cgpa > 8.0 AND s.cgpa > 8.0` → `WHERE s.cgpa > 8.0`.

---

## E. Join Reordering

**Goal.** Feed joins the smallest intermediate results first.

**Mechanism.** Flatten a tree of `INNER` joins into a list of relations plus predicates,
order the relations by ascending estimated cardinality, and rebuild a left-deep tree applying
each predicate as soon as both its inputs are available.

`build_left_deep_join` (in `optimizer/join_utils.py`) guarantees correctness by only applying
a predicate when all of its referenced relations have been joined.

---

## Adding a new rule

1. Create `rules/my_rule.py`:

   ```python
   from .base import Rule
   from ..records import RuleFinding

   class MyRule(Rule):
       name = "My Rule"
       description = "…"

       def apply(self, root, ctx):
           findings: list[RuleFinding] = []
           # transform `root` in place or return a new tree
           return root, findings
   ```

2. Register it in `rules/__init__.py`'s `default_rules()` at the appropriate position.
3. Add unit tests in `tests/test_optimizer.py`.

`ctx` exposes `stats`, `config`, `expr` (the `ExprContext`), and a `cardinality` estimator.
