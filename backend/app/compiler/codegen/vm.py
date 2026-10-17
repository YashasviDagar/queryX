"""A stack-based virtual machine that executes queryX bytecode.

State:
  * an operand stack for expression evaluation,
  * registers holding the row each cursor is positioned on,
  * cursors / iterators, hash tables, buffers, aggregation tables, seen-sets,
    counters and flags addressed by name (``r0``, ``ht0``, ``buf1``...).

Comparisons and logic follow SQL three-valued semantics: any comparison with
NULL is NULL, and a filter only passes rows whose condition is TRUE.
"""
from __future__ import annotations

import bisect
import operator
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .bytecode import Address, Program
from .sample_data import SampleDatabase


class VMError(Exception):
    pass


class StepLimitExceeded(VMError):
    pass


_COMPARE = {
    "EQ": operator.eq, "NE": operator.ne, "LT": operator.lt,
    "LE": operator.le, "GT": operator.gt, "GE": operator.ge,
}
_ARITHMETIC = {
    "ADD": operator.add, "SUB": operator.sub, "MUL": operator.mul,
    "DIV": operator.truediv, "MOD": operator.mod,
}


@dataclass
class ExecutionResult:
    columns: list[str]
    rows: list[tuple]
    steps: int
    opcode_counts: dict[str, int] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self, max_rows: int = 50) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": [list(row) for row in self.rows[:max_rows]],
            "rowCount": len(self.rows),
            "truncated": len(self.rows) > max_rows,
            "instructionsExecuted": self.steps,
            "opcodeCounts": dict(sorted(self.opcode_counts.items(), key=lambda kv: -kv[1])),
            "elapsedMs": round(self.elapsed_ms, 3),
        }


def _sql_compare(fn, a, b):
    if a is None or b is None:
        return None
    try:
        return fn(a, b)
    except TypeError:
        return None


def _sql_and(a, b):
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return bool(a) and bool(b)


def _sql_or(a, b):
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return bool(a) or bool(b)


class _Aggregation:
    def __init__(self, key_count: int, specs: tuple) -> None:
        self.key_count = key_count
        self.specs = specs
        self.groups: dict[tuple, list] = {}

    def update(self, keys: tuple, args: list) -> None:
        state = self.groups.get(keys)
        if state is None:
            state = [self._initial(name, distinct) for name, distinct in self.specs]
            self.groups[keys] = state
        for index, ((name, distinct), value) in enumerate(zip(self.specs, args)):
            if value is None:
                continue
            if distinct:
                state[index].add(value)
            elif name == "COUNT":
                state[index] += 1
            elif name in ("SUM", "AVG"):
                state[index][0] += value
                state[index][1] += 1
            elif name == "MIN":
                state[index] = value if state[index] is None else min(state[index], value)
            elif name == "MAX":
                state[index] = value if state[index] is None else max(state[index], value)

    @staticmethod
    def _initial(name: str, distinct: bool):
        if distinct:
            return set()
        if name == "COUNT":
            return 0
        if name in ("SUM", "AVG"):
            return [0, 0]
        return None

    def _final(self, name: str, distinct: bool, state):
        if distinct:
            values = state
            if name == "COUNT":
                return len(values)
            if not values:
                return None
            if name == "SUM":
                return sum(values)
            if name == "AVG":
                return sum(values) / len(values)
            return min(values) if name == "MIN" else max(values)
        if name == "SUM":
            return state[0] if state[1] else None
        if name == "AVG":
            return state[0] / state[1] if state[1] else None
        return state

    def results(self) -> Iterator[tuple]:
        groups = self.groups
        if not groups and self.key_count == 0:
            # A global aggregate over no rows still yields one row (COUNT = 0).
            groups = {(): [self._initial(name, distinct) for name, distinct in self.specs]}
        for keys, state in groups.items():
            finals = [self._final(name, distinct, s) for (name, distinct), s in zip(self.specs, state)]
            yield tuple(keys) + tuple(finals)


def _sort_key(values: tuple, directions: tuple):
    """NULLs sort last ascending and first descending, as in PostgreSQL."""
    key = []
    for value, direction in zip(values, directions):
        missing = value is None
        if direction == "DESC":
            key.append((not missing, _Reversed(value)))
        else:
            key.append((missing, value if not missing else 0))
    return tuple(key)


class _Reversed:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        if self.value is None or other.value is None:
            return False
        return other.value < self.value

    def __eq__(self, other):
        return self.value == other.value


class VirtualMachine:
    def __init__(self, database: SampleDatabase, max_steps: int = 2_000_000) -> None:
        self.database = database
        self.max_steps = max_steps
        self._indexes: dict[tuple[str, str], tuple[list, list]] = {}

    def run(self, program: Program) -> ExecutionResult:
        code = [(ins.op, tuple(a.value if isinstance(a, Address) else a for a in ins.args))
                for ins in program.instructions]
        stack: list[Any] = []
        registers: dict[str, Any] = {}
        cursors: dict[str, Iterator] = {}
        structures: dict[str, Any] = {}
        flags: dict[str, bool] = {}
        output: list[tuple] = []
        counts: dict[str, int] = {}
        push, pop = stack.append, stack.pop
        pc = steps = 0
        limit = self.max_steps
        started = time.perf_counter()

        while True:
            op, args = code[pc]
            steps += 1
            counts[op] = counts.get(op, 0) + 1
            if steps > limit:
                raise StepLimitExceeded(f"stopped after {limit:,} instructions")
            pc += 1

            if op == "LOAD":
                row = registers.get(args[0])
                push(None if row is None else row[args[1]])
            elif op == "CONST":
                push(args[0])
            elif op == "NEXT":
                row = next(cursors[args[0]], None)
                if row is None:
                    pc = args[1]
                else:
                    registers[args[0]] = row
            elif op == "JUMP":
                pc = args[0]
            elif op == "JUMP_IF_FALSE":
                if pop() is not True:
                    pc = args[0]
            elif op == "JUMP_IF_TRUE":
                if pop() is True:
                    pc = args[0]
            elif op in _COMPARE:
                b = pop()
                push(_sql_compare(_COMPARE[op], pop(), b))
            elif op == "AND":
                b = pop()
                push(_sql_and(pop(), b))
            elif op == "OR":
                b = pop()
                push(_sql_or(pop(), b))
            elif op == "NOT":
                value = pop()
                push(None if value is None else not value)
            elif op in _ARITHMETIC:
                b = pop()
                a = pop()
                if a is None or b is None or (op in ("DIV", "MOD") and b == 0):
                    push(None)
                else:
                    push(_ARITHMETIC[op](a, b))
            elif op == "RESTORE":
                snapshot = next(cursors[args[0]], None)
                if snapshot is None:
                    pc = args[1]
                else:
                    registers.update(snapshot)
            elif op == "MAKE_ROW":
                count = args[1]
                values = tuple(stack[-count:]) if count else ()
                del stack[len(stack) - count:]
                registers[args[0]] = values
            elif op == "EMIT":
                count = args[0]
                output.append(tuple(stack[-count:]) if count else ())
                del stack[len(stack) - count:]
            elif op == "SCAN_OPEN":
                cursors[args[0]] = iter(self.database.rows(args[1]))
                registers[args[0]] = None
            elif op == "INDEX_OPEN":
                cursors[args[0]] = iter(self._index_range(args[1], args[2], args[3], args[4]))
                registers[args[0]] = None
            elif op == "FLAG_SET":
                flags[args[0]] = args[1]
            elif op == "JUMP_IF_FLAG":
                if flags.get(args[0]):
                    pc = args[1]
            elif op == "BIND_NULL":
                registers[args[0]] = None
            elif op == "HT_CLEAR":
                structures[args[0]] = {}
            elif op == "HT_INSERT":
                key = self._pop_key(stack, args[1])
                if key is not None:
                    snapshot = {r: registers.get(r) for r in args[2]}
                    structures[args[0]].setdefault(key, []).append(snapshot)
            elif op == "HT_PROBE":
                key = self._pop_key(stack, args[2])
                matches = structures[args[1]].get(key, []) if key is not None else []
                cursors[args[0]] = iter(matches)
            elif op == "BUF_CLEAR":
                structures[args[0]] = []
            elif op == "BUF_APPEND":
                count = args[1]
                keys = tuple(stack[-count:]) if count else ()
                del stack[len(stack) - count:]
                structures[args[0]].append((keys, {r: registers.get(r) for r in args[2]}))
            elif op == "BUF_SORT":
                directions = args[1]
                structures[args[0]].sort(key=lambda entry: _sort_key(entry[0], directions))
            elif op == "BUF_OPEN":
                cursors[args[0]] = iter([snapshot for _, snapshot in structures[args[1]]])
            elif op == "MERGE_OPEN":
                cursors[args[0]] = iter(
                    _merge(structures[args[1]], structures[args[2]], args[3], args[4])
                )
            elif op == "AGG_CLEAR":
                structures[args[0]] = _Aggregation(args[1], args[2])
            elif op == "AGG_UPDATE":
                table = structures[args[0]]
                arg_count = len(table.specs)
                values = stack[len(stack) - arg_count:] if arg_count else []
                del stack[len(stack) - arg_count:]
                key_count = table.key_count
                keys = tuple(stack[len(stack) - key_count:]) if key_count else ()
                del stack[len(stack) - key_count:]
                table.update(keys, values)
            elif op == "AGG_OPEN":
                register = args[2]
                cursors[args[0]] = iter([{register: row} for row in structures[args[1]].results()])
            elif op == "DISTINCT_CLEAR":
                structures[args[0]] = set()
            elif op == "DISTINCT_CHECK":
                count = args[1]
                values = tuple(stack[-count:]) if count else ()
                del stack[len(stack) - count:]
                seen = structures[args[0]]
                if values in seen:
                    pc = args[2]
                else:
                    seen.add(values)
            elif op == "LIMIT_RESET":
                structures[args[0]] = 0
            elif op == "LIMIT_CHECK":
                structures[args[0]] += 1
                if structures[args[0]] > args[1]:
                    pc = args[2]
            elif op == "HALT":
                break
            else:
                raise VMError(f"unknown opcode {op} at {pc - 1}")

        elapsed = (time.perf_counter() - started) * 1000.0
        return ExecutionResult(program.output_columns, output, steps, counts, elapsed)

    @staticmethod
    def _pop_key(stack: list, count: int) -> Optional[tuple]:
        key = tuple(stack[-count:]) if count else ()
        del stack[len(stack) - count:]
        return None if any(value is None for value in key) else key

    def _index_range(self, table: str, column: str, op: str, value: Any) -> list[dict]:
        """Rows an ordered (b-tree-like) index on ``column`` returns for ``column op value``."""
        cache_key = (table.lower(), column.lower())
        if cache_key not in self._indexes:
            rows = [row for row in self.database.rows(table) if row.get(column.lower()) is not None]
            rows.sort(key=lambda row: row[column.lower()])
            self._indexes[cache_key] = ([row[column.lower()] for row in rows], rows)
        keys, rows = self._indexes[cache_key]
        try:
            if op == "=":
                return rows[bisect.bisect_left(keys, value):bisect.bisect_right(keys, value)]
            if op == ">":
                return rows[bisect.bisect_right(keys, value):]
            if op == ">=":
                return rows[bisect.bisect_left(keys, value):]
            if op == "<":
                return rows[:bisect.bisect_left(keys, value)]
            if op == "<=":
                return rows[:bisect.bisect_right(keys, value)]
        except TypeError:
            return []
        return list(rows)


def _merge(left: list, right: list, outer: bool, right_registers: tuple) -> Iterator[dict]:
    """Merge two key-sorted buffers, yielding combined row snapshots for each match."""
    i = j = 0
    null_right = {r: None for r in right_registers}
    while i < len(left):
        left_key, left_rows = left[i]
        if any(v is None for v in left_key):
            if outer:
                yield {**left_rows, **null_right}
            i += 1
            continue
        while j < len(right) and (any(v is None for v in right[j][0]) or right[j][0] < left_key):
            j += 1
        k = j
        matched = False
        while k < len(right) and right[k][0] == left_key:
            matched = True
            yield {**left_rows, **right[k][1]}
            k += 1
        if not matched and outer:
            yield {**left_rows, **null_right}
        i += 1
