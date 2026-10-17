"""Code generation, peephole optimization and the bytecode VM."""
from __future__ import annotations

from collections import Counter

import pytest

from app.compiler.codegen import compile_plan
from app.compiler.codegen.bytecode import Instr, Label, assemble
from app.compiler.codegen.peephole import PeepholeOptimizer
from app.compiler.codegen.vm import VirtualMachine
from app.compiler.cost.model import CostEstimator
from app.compiler.ir.builder import build_ir
from app.compiler.ir.expr import ExprContext
from app.compiler.lexer.lexer import tokenize
from app.compiler.optimizer.engine import OptimizerEngine
from app.compiler.parser.parser import parse
from app.compiler.planner.generator import PhysicalPlanGenerator
from app.compiler.planner.selector import PlanSelector
from app.compiler.semantic.analyzer import SemanticAnalyzer
from app.services.examples import get_examples


def _run(pipeline, sql: str) -> dict:
    result = pipeline.compile(sql)
    assert result["success"], result["errors"] or result["semanticErrors"]
    codegen = result["codegen"]
    assert codegen["success"], codegen.get("error")
    return codegen


def _rows(codegen: dict) -> Counter:
    assert not codegen["execution"]["truncated"]
    return Counter(tuple(row) for row in codegen["execution"]["rows"])


def _all_rows(pipeline, sql: str) -> Counter:
    """Run the selected plan on the VM without the API's 50-row display cap."""
    query = parse(tokenize(sql))
    semantic = SemanticAnalyzer(pipeline.catalog).analyze(query)
    ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)
    optimized = OptimizerEngine(pipeline.stats, pipeline.config, ctx).optimize(build_ir(query, pipeline.catalog, semantic))
    candidates = PhysicalPlanGenerator(pipeline.stats, pipeline.config, ctx).generate(optimized.root)
    selection = PlanSelector(CostEstimator(pipeline.stats, pipeline.config, ctx)).evaluate(candidates)
    _, program, _, _ = compile_plan(selection.selected.candidate.tree, ctx, pipeline.database)
    return Counter(VirtualMachine(pipeline.database).run(program).rows)


def _table(pipeline, name: str) -> list[dict]:
    return pipeline.database.rows(name)


# -- results match a direct Python evaluation of the query ---------------------
def test_join_with_filters_matches_reference(pipeline, example_sql):
    departments = {d["id"]: d for d in _table(pipeline, "departments")}
    expected = Counter(
        (s["name"], departments[s["dept_id"]]["name"])
        for s in _table(pipeline, "students")
        if s["cgpa"] > 8.0 and departments[s["dept_id"]]["name"] == "CSE"
    )
    assert _rows(_run(pipeline, example_sql)) == expected


def test_single_table_filter_matches_reference(pipeline):
    codegen = _run(pipeline, "SELECT s.name, s.age FROM students s WHERE s.age >= 30 AND s.city = 'Pune';")
    expected = Counter(
        (s["name"], s["age"]) for s in _table(pipeline, "students") if s["age"] >= 30 and s["city"] == "Pune"
    )
    assert _rows(codegen) == expected


def test_group_by_with_having_matches_reference(pipeline):
    codegen = _run(
        pipeline,
        "SELECT s.dept_id, COUNT(s.id) AS total FROM students s GROUP BY s.dept_id HAVING COUNT(s.id) > 18;",
    )
    counts = Counter(s["dept_id"] for s in _table(pipeline, "students"))
    assert _rows(codegen) == Counter((dept, n) for dept, n in counts.items() if n > 18)


def test_order_by_and_limit_return_the_top_rows_in_order(pipeline):
    codegen = _run(pipeline, "SELECT s.name, s.cgpa FROM students s ORDER BY s.cgpa DESC LIMIT 5;")
    cgpas = [row[1] for row in codegen["execution"]["rows"]]
    top = sorted((s["cgpa"] for s in _table(pipeline, "students")), reverse=True)[:5]
    assert cgpas == top


def test_distinct_removes_duplicates(pipeline):
    codegen = _run(pipeline, "SELECT DISTINCT s.city FROM students s;")
    assert _rows(codegen) == Counter((city,) for city in {s["city"] for s in _table(pipeline, "students")})


def test_global_aggregate_over_no_rows_returns_one_row(pipeline):
    codegen = _run(pipeline, "SELECT COUNT(s.id) AS total FROM students s WHERE s.cgpa > 100;")
    assert codegen["execution"]["rows"] == [[0]]


def test_left_join_pads_unmatched_rows_with_null(pipeline):
    # Only the first few student ids have a course with the same id.
    sql = "SELECT s.id, c.title FROM students s LEFT JOIN courses c ON s.id = c.id;"
    courses = {c["id"]: c["title"] for c in _table(pipeline, "courses")}
    expected = Counter((s["id"], courses.get(s["id"])) for s in _table(pipeline, "students"))
    assert _all_rows(pipeline, sql) == expected
    assert expected[(len(courses) + 1, None)] == 1


# -- every candidate plan computes the same answer -----------------------------
@pytest.mark.parametrize("example", [e for e in get_examples() if "teachers" not in e["sql"]], ids=lambda e: e["title"])
def test_all_candidate_plans_agree(pipeline, example):
    codegen = _run(pipeline, example["sql"])
    statuses = [check["status"] for check in codegen["planChecks"]]
    assert "mismatch" not in statuses and "error" not in statuses
    assert statuses.count("match") >= 1


@pytest.mark.parametrize("example", [e for e in get_examples() if "teachers" not in e["sql"]], ids=lambda e: e["title"])
def test_peephole_preserves_results_and_never_adds_work(pipeline, example):
    codegen = _run(pipeline, example["sql"])
    unoptimized = codegen["unoptimizedExecution"]
    assert unoptimized["sameResult"]
    assert codegen["execution"]["instructionsExecuted"] <= unoptimized["instructionsExecuted"]
    assert codegen["peephole"]["instructionsAfter"] <= codegen["peephole"]["instructionsBefore"]


def test_index_scan_plan_rechecks_the_full_predicate(pipeline):
    codegen = _run(pipeline, "SELECT s.name FROM students s WHERE s.cgpa > 8.0 AND s.age < 20;")
    expected = sum(1 for s in _table(pipeline, "students") if s["cgpa"] > 8.0 and s["age"] < 20)
    for check in codegen["planChecks"]:
        assert check["rowCount"] == expected


# -- peephole rules on hand-written code ---------------------------------------
def _optimize(items):
    return PeepholeOptimizer().optimize(items)


def _rules(result) -> set[str]:
    return {record.rule for record in result.records}


def test_constant_folding_and_constant_branch():
    end = Label("end")
    items = [Instr("CONST", (2,)), Instr("CONST", (3,)), Instr("LT", ()), Instr("JUMP_IF_FALSE", (end,)),
             Instr("CONST", (1,)), Instr("EMIT", (1,)), end, Instr("HALT")]
    result = _optimize(items)
    assert {"Constant Folding", "Constant Branch"} <= _rules(result)
    assert [i.op for i in result.items if isinstance(i, Instr)] == ["CONST", "EMIT", "HALT"]


def test_false_constant_branch_becomes_jump_and_dead_code_is_removed():
    end = Label("end")
    items = [Instr("CONST", (False,)), Instr("JUMP_IF_FALSE", (end,)),
             Instr("CONST", (1,)), Instr("EMIT", (1,)), end, Instr("HALT")]
    result = _optimize(items)
    assert "Dead Code Elimination" in _rules(result)
    assert [i.op for i in result.items if isinstance(i, Instr)] == ["HALT"]


def test_jump_threading_skips_intermediate_jumps():
    a, b, c = Label("a"), Label("b"), Label("c")
    items = [Instr("LOAD", ("r0", "flag")), Instr("JUMP_IF_TRUE", (a,)), Instr("HALT"),
             a, Instr("JUMP", (b,)), b, Instr("JUMP", (c,)), c, Instr("HALT")]
    result = _optimize(items)
    assert "Jump Threading" in _rules(result)
    branch = next(i for i in result.items if isinstance(i, Instr) and i.op == "JUMP_IF_TRUE")
    assert branch.args == (c,)


def test_store_load_forwarding_keeps_registers_with_other_readers():
    items = [Instr("CONST", (1,)), Instr("MAKE_ROW", ("r0", 1)), Instr("LOAD", ("r0", 0)), Instr("EMIT", (1,)),
             Instr("BUF_APPEND", ("buf0", 0, ("r0",))), Instr("HALT")]
    assert "Store-Load Forwarding" not in _rules(_optimize(items))


# -- VM semantics --------------------------------------------------------------
def _execute(pipeline, items):
    program = assemble(items + [Instr("HALT")], ["value"])
    return VirtualMachine(pipeline.database).run(program).rows


def test_comparison_with_null_is_null_and_filters_the_row(pipeline):
    skip = Label("skip")
    items = [Instr("CONST", (None,)), Instr("CONST", (1,)), Instr("EQ", ()), Instr("JUMP_IF_FALSE", (skip,)),
             Instr("CONST", ("kept",)), Instr("EMIT", (1,)), skip]
    assert _execute(pipeline, items) == []


def test_not_null_is_null_under_three_valued_logic(pipeline):
    items = [Instr("CONST", (None,)), Instr("NOT", ()), Instr("EMIT", (1,))]
    assert _execute(pipeline, items) == [(None,)]


def test_false_and_null_is_false(pipeline):
    items = [Instr("CONST", (False,)), Instr("CONST", (None,)), Instr("AND", ()), Instr("EMIT", (1,))]
    assert _execute(pipeline, items) == [(False,)]
