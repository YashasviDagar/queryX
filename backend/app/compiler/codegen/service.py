"""Back-end driver: code generation, peephole optimization and execution.

For the selected plan it reports the bytecode before and after peephole
optimization, the rewrites applied, and the result of running both versions on
the VM (which must agree). It also compiles and runs every other candidate plan
on the same data as a differential test: plans that differ in join order, join
algorithm or access path must all return the same rows.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..ir.expr import ExprContext
from ..planner.physical import PhysicalNode
from ..planner.selector import SelectionResult
from .bytecode import assemble
from .generator import CodeGenerator, CodegenError
from .peephole import PeepholeOptimizer
from .sample_data import SampleDatabase
from .vm import StepLimitExceeded, VirtualMachine, VMError

SELECTED_STEP_LIMIT = 2_000_000
CANDIDATE_STEP_LIMIT = 400_000


def compile_plan(tree: PhysicalNode, ctx: ExprContext, database: SampleDatabase):
    generator = CodeGenerator(ctx, database)
    items, columns = generator.generate(tree)
    peephole = PeepholeOptimizer().optimize(items)
    return assemble(items, columns), assemble(peephole.items, columns), peephole, generator.notes


def run_codegen(selection: SelectionResult, ctx: ExprContext, database: SampleDatabase) -> dict[str, Any]:
    if selection.selected is None:
        return {"success": False, "error": "No plan was selected."}
    selected = selection.selected.candidate
    try:
        raw, optimized, peephole, notes = compile_plan(selected.tree, ctx, database)
        vm = VirtualMachine(database, SELECTED_STEP_LIMIT)
        result = vm.run(optimized)
        unoptimized = vm.run(raw)
    except (CodegenError, VMError) as error:
        return {"success": False, "error": str(error)}

    return {
        "success": True,
        "plan": selected.name,
        "notes": notes,
        "sampleData": database.summary(),
        "bytecode": optimized.disassemble(),
        "bytecodeText": optimized.to_text(),
        "unoptimizedBytecode": raw.disassemble(),
        "unoptimizedBytecodeText": raw.to_text(),
        "peephole": peephole.to_dict(),
        "execution": result.to_dict(),
        "unoptimizedExecution": {
            "instructionsExecuted": unoptimized.steps,
            "elapsedMs": round(unoptimized.elapsed_ms, 3),
            "sameResult": _same(result.rows, unoptimized.rows),
        },
        "planChecks": _check_candidates(selection, selected.plan_id, result.rows, ctx, database),
    }


def _check_candidates(selection: SelectionResult, selected_id: str, expected: list[tuple],
                      ctx: ExprContext, database: SampleDatabase) -> list[dict[str, Any]]:
    checks = []
    for evaluation in selection.evaluations:
        candidate = evaluation.candidate
        entry: dict[str, Any] = {
            "id": candidate.plan_id,
            "name": candidate.name,
            "description": candidate.description,
            "estimatedCost": round(evaluation.estimated_cost, 2),
            "selected": candidate.plan_id == selected_id,
        }
        try:
            _, program, _, _ = compile_plan(candidate.tree, ctx, database)
            run = VirtualMachine(database, CANDIDATE_STEP_LIMIT).run(program)
        except StepLimitExceeded:
            entry.update(status="skipped", reason=f"over {CANDIDATE_STEP_LIMIT:,} instructions")
        except (CodegenError, VMError) as error:
            entry.update(status="error", reason=str(error))
        else:
            # With LIMIT and no total order, plans may legitimately pick different rows.
            if _has_limit(candidate.tree):
                matches = len(run.rows) == len(expected)
            else:
                matches = _same(run.rows, expected)
            entry.update(
                status="match" if matches else "mismatch",
                rowCount=len(run.rows),
                instructionsExecuted=run.steps,
                programLength=len(program),
            )
        checks.append(entry)
    return checks


def _same(a: list[tuple], b: list[tuple]) -> bool:
    """Compare results as multisets: ties under ORDER BY may come out in any order."""
    return Counter(map(_normalize, a)) == Counter(map(_normalize, b))


def _normalize(row: tuple) -> str:
    # Plans sum floats in different orders, so AVG/SUM can differ in the last bits.
    return repr(tuple(round(v, 9) if isinstance(v, float) else v for v in row))


def _has_limit(tree: PhysicalNode) -> bool:
    return tree.op == "Limit" or any(_has_limit(c) for c in tree.children)
