# Code generation, peephole optimization and the VM

The planner's output is not the end of the pipeline. The selected physical plan is compiled
into bytecode for a stack-based virtual machine, the bytecode is optimized by a peephole
pass, and the VM executes it to produce real result rows.

```
selected physical plan
  → Code generator   → bytecode with symbolic labels      (compiler/codegen/generator.py)
  → Peephole pass    → optimized bytecode + rewrite log   (compiler/codegen/peephole.py)
  → Assembler        → labels resolved to addresses        (compiler/codegen/bytecode.py)
  → Virtual machine  → result rows + execution counters    (compiler/codegen/vm.py)
```

## Code generation: produce/consume

The generator uses the *produce/consume* model from query-compiling engines such as HyPer
and Umbra. Each operator *produces* rows by emitting a loop, and hands every row to its
parent's *consume* callback, which emits the parent's per-row code inside that loop.

For the flagship query the whole plan becomes two nested loops:

```
0000  SCAN_OPEN      r1, departments      ; sequential scan of departments d
0001  NEXT           r1, @0020            ; next row of d
0002  LOAD           r1, name             ; d.name
0003  CONST          'CSE'
0004  EQ
0005  JUMP_IF_FALSE  @0001                ; WHERE d.name = 'CSE'
0006  SCAN_OPEN      r2, students         ; sequential scan of students s
0007  NEXT           r2, @0001            ; next row of s
0008  LOAD           r2, cgpa             ; s.cgpa
0009  CONST          8.0
0010  GT
0011  JUMP_IF_FALSE  @0007                ; WHERE s.cgpa > 8.0
0012  LOAD           r2, dept_id          ; s.dept_id
0013  LOAD           r1, id               ; d.id
0014  EQ
0015  JUMP_IF_FALSE  @0007                ; ON s.dept_id = d.id
0016  LOAD           r2, name             ; s.name
0017  LOAD           r1, name             ; d.name
0018  EMIT           2                    ; append result row
0019  JUMP           @0007
0020  HALT
```

Expressions compile to postfix stack code (operands first, then the operator), and every
filter ends in a conditional jump back to the loop head.

| Operator | Generated code |
|---|---|
| Sequential scan | `SCAN_OPEN`, then a `NEXT` loop |
| Index scan | `INDEX_OPEN` over the index range, then the full predicate rechecked per row |
| Filter | condition code + `JUMP_IF_FALSE` |
| Nested-loop join | the inner input's loop generated inside the outer input's loop |
| Hash join | build loop with `HT_INSERT`, probe loop with `HT_PROBE` + `RESTORE` |
| Merge join | both inputs materialized with `BUF_APPEND` and `BUF_SORT`, then `MERGE_OPEN` |
| `LEFT` join | a match flag per outer row; unmatched rows are padded with `BIND_NULL` |
| Aggregate | `AGG_UPDATE` per input row, then a loop over finished groups |
| Sort | `BUF_APPEND` per row, `BUF_SORT`, then a loop over the sorted buffer |
| Distinct | `DISTINCT_CHECK` against a seen-set |
| Limit | `LIMIT_CHECK` jumps out of every enclosing loop once the limit is reached |
| Project | `MAKE_ROW` packs the SELECT list into a register |

Hash and merge joins need an equality key. When a join condition has none, the generator
falls back to a nested loop and records a note. A `LEFT` merge join whose condition has
non-key parts is compiled as a hash join, because the merge cannot evaluate them.

## Peephole optimization

The peephole pass slides a small window over the label-form code and rewrites local
patterns until nothing changes. Every rewrite is recorded with the code before and after.

| Rule | Pattern | Result |
|---|---|---|
| Constant folding | `CONST 2; CONST 3; ADD` | `CONST 5` |
| Constant branch | `CONST TRUE; JUMP_IF_FALSE L` | removed |
| | `CONST FALSE; JUMP_IF_FALSE L` | `JUMP L` |
| Jump threading | a jump to `L` where `L: JUMP M` | jump straight to `M` |
| Jump to next | `JUMP L; L:` | `L:` |
| Dead code elimination | code after `JUMP`/`HALT` that no jump reaches | removed |
| Store-load forwarding | `MAKE_ROW r, 2; LOAD r, 0; LOAD r, 1` with no other reader of `r` | removed |

Jump threading fires on almost every query: a failed filter jumps to a "skip" label whose
only instruction is the jump back to the loop head, so the filter can jump to the loop head
directly. On the example queries the pass cuts executed instructions by 11–19%.

One rule is deliberately missing. Rewriting `NOT; JUMP_IF_FALSE L` as `JUMP_IF_TRUE L` looks
safe but is wrong under SQL's three-valued logic: `NOT NULL` is `NULL`, so the original
jumps when the operand is `NULL` and the rewrite would not.

## The virtual machine

The VM is a stack machine with named registers. Registers hold the row each cursor is
positioned on; hash tables, sort buffers, aggregation tables, seen-sets, counters and flags
are addressed by name (`ht0`, `buf1`, `agg0`…). Comparisons and logic follow SQL
three-valued semantics, and a filter passes a row only when its condition is `TRUE`.

### Sample data

The optimizer reasons about the full-size tables in `statistics.yaml`. The VM runs on a
deterministic scaled-down copy generated from the same statistics: each table gets
`min(rows, 20 + √rows)` rows, so `students` has 336 rows and `enrollments` 727. Foreign keys
point at existing rows, numeric columns respect their recorded min and max, and the text
columns the examples filter on (`departments.name`, `students.city`) use readable values.

## Verification

Every compile also checks the back end against itself:

- **Peephole safety:** the optimized and unoptimized programs both run, and their results
  must be identical.
- **Differential testing of plans:** every candidate plan is compiled and executed. Plans
  that differ in join order, join algorithm and access path must return the same rows. A
  plan that needs more than 400,000 instructions is skipped. With `LIMIT` but no total order
  plans may legitimately return different rows, so only the row count is compared there.

The dashboard's **Bytecode & VM** page shows the bytecode before and after peephole
optimization, each rewrite, the result rows, and the verification table.

## Estimated cost versus executed instructions

The cost model charges for disk pages (`seq_page_cost`, `random_page_cost`), but the VM
runs entirely in memory. Index-scan plans therefore often execute far fewer instructions on
the VM than the plan the cost model selected. The verification table shows both numbers
side by side.
