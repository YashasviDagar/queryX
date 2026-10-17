"""Code generation: physical plan -> VM bytecode.

Uses the produce/consume model from query-compiling engines (HyPer, Umbra):
each operator *produces* rows by emitting a loop, and hands every row to its
parent's *consume* callback, which emits the parent's per-row code inside that
loop. Pipelines therefore compile into tight nested loops with no per-operator
iterator calls; only pipeline breakers (hash build, sort, aggregate) materialize
rows into VM data structures.

Expressions compile to stack code: operands are pushed, operators pop them and
push the result, and filters end in a conditional jump.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..ast import nodes as ast
from ..ir.expr import ExprContext, canonical, conjuncts, referenced_sources, render
from ..planner.physical import PhysicalNode
from .bytecode import Instr, Item, Label
from .sample_data import SampleDatabase

_COMPARISON_OPS = {"=": "EQ", "<>": "NE", "!=": "NE", "<": "LT", "<=": "LE", ">": "GT", ">=": "GE"}
_ARITHMETIC_OPS = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}
_FLIPPED = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "=": "=", "<>": "<>", "!=": "!="}


class CodegenError(Exception):
    """Raised for plan shapes or expressions the code generator does not support."""


@dataclass
class Env:
    """Where each visible value lives at a point in the generated code.

    Keys are ``("col", source, column)`` for base-table columns,
    ``("expr", canonical_text)`` for computed values (projections, aggregates)
    and ``("name", alias)`` for output names. Values are ``(register, field)``.
    """

    slots: dict[tuple, tuple[str, Any]] = field(default_factory=dict)
    output: Optional[list[tuple[str, Any]]] = None

    def merged(self, other: "Env") -> "Env":
        return Env({**self.slots, **other.slots}, other.output or self.output)

    def extended(self) -> "Env":
        return Env(dict(self.slots), list(self.output) if self.output else None)

    def registers(self) -> tuple[str, ...]:
        return tuple(sorted({register for register, _ in self.slots.values()}))


Consumer = Callable[[Env], None]


class CodeGenerator:
    def __init__(self, ctx: ExprContext, database: SampleDatabase) -> None:
        self.ctx = ctx
        self.database = database
        self.items: list[Item] = []
        self.notes: list[str] = []
        self._counters: dict[str, int] = {}

    # -- entry point ---------------------------------------------------------
    def generate(self, plan: PhysicalNode) -> tuple[list[Item], list[str]]:
        output_names = _output_names(plan)
        self._produce(plan, self._emit_result)
        self._emit("HALT")
        return self.items, output_names

    def _emit_result(self, env: Env) -> None:
        if not env.output:
            raise CodegenError("Plan has no projection to emit")
        for register, slot in env.output:
            self._emit("LOAD", register, slot)
        self._emit("EMIT", len(env.output), comment="append result row")

    # -- emission helpers ----------------------------------------------------
    def _emit(self, op: str, *args: Any, comment: str = "") -> None:
        self.items.append(Instr(op, tuple(args), comment))

    def _new(self, kind: str) -> str:
        number = self._counters.get(kind, 0)
        self._counters[kind] = number + 1
        return f"{kind}{number}"

    def _label(self, hint: str) -> Label:
        return Label(f"L{self._new('L')[1:]}_{hint}")

    def _place(self, label: Label) -> None:
        self.items.append(label)

    # -- operators -----------------------------------------------------------
    def _produce(self, node: PhysicalNode, consume: Consumer) -> None:
        handler = {
            "SeqScan": self._scan,
            "IndexScan": self._scan,
            "Filter": self._filter,
            "NestedLoopJoin": self._join,
            "HashJoin": self._join,
            "MergeJoin": self._join,
            "Project": self._project,
            "Distinct": self._distinct,
            "Sort": self._sort,
            "Aggregate": self._aggregate,
            "Limit": self._limit,
        }.get(node.op)
        if handler is None:
            raise CodegenError(f"No code generator for operator {node.op}")
        handler(node, consume)

    def _scan(self, node: PhysicalNode, consume: Consumer) -> None:
        details = node.details
        table = details["table"]
        alias = details.get("alias")
        source = (alias or table).lower()
        register = self._new("r")
        name = f"{table} {alias}" if alias else table
        condition = details.get("condition")

        sargable = _sargable(condition, details.get("column")) if node.op == "IndexScan" else None
        if sargable is not None:
            op, value = sargable
            self._emit("INDEX_OPEN", register, table, details["column"], op, value,
                       comment=f"index {details.get('index')} on {name}")
        else:
            self._emit("SCAN_OPEN", register, table, comment=f"sequential scan of {name}")

        loop, end = self._label("scan"), self._label("scan_end")
        self._place(loop)
        self._emit("NEXT", register, end, comment=f"next row of {source}")
        env = Env({("col", source, column): (register, column) for column in self.database.columns(table)})
        if node.op == "IndexScan" and condition is not None:
            # The index narrows the range; the full predicate is rechecked per row.
            self._filtered(env, condition, consume)
        else:
            consume(env)
        self._emit("JUMP", loop)
        self._place(end)

    def _filter(self, node: PhysicalNode, consume: Consumer) -> None:
        condition = node.details.get("condition")
        self._produce(node.children[0], lambda env: self._filtered(env, condition, consume))

    def _filtered(self, env: Env, condition: Optional[ast.Node], consume: Consumer) -> None:
        if condition is None:
            consume(env)
            return
        skip = self._label("skip")
        self._expr(condition, env)
        self._emit("JUMP_IF_FALSE", skip, comment=f"WHERE {render(condition)}")
        consume(env)
        self._place(skip)

    def _join(self, node: PhysicalNode, consume: Consumer) -> None:
        condition = node.details.get("condition")
        join_type = node.details.get("joinType", "INNER")
        left, right = node.children
        keys = _equi_keys(condition, _sources(left), _sources(right), self.ctx)
        algorithm = node.op
        if algorithm != "NestedLoopJoin" and not keys:
            self.notes.append(f"{algorithm} has no equality key; compiled as a nested loop.")
            algorithm = "NestedLoopJoin"
        if algorithm == "MergeJoin" and join_type == "LEFT" and len(conjuncts(condition)) > len(keys):
            self.notes.append("LEFT merge join with a non-key condition compiled as a hash join.")
            algorithm = "HashJoin"
        {
            "NestedLoopJoin": self._nested_loop,
            "HashJoin": self._hash_join,
            "MergeJoin": self._merge_join,
        }[algorithm](left, right, condition, join_type, keys, consume)

    def _nested_loop(self, left, right, condition, join_type, keys, consume: Consumer) -> None:
        flag = self._new("f") if join_type == "LEFT" else None

        def outer(env_left: Env) -> None:
            if flag:
                self._emit("FLAG_SET", flag, False, comment="no match yet for this left row")
            captured: list[Env] = []

            def inner(env_right: Env) -> None:
                captured.append(env_right)
                self._matched(env_left.merged(env_right), condition, flag, consume)

            self._produce(right, inner)
            if flag:
                self._pad_unmatched(env_left, captured[-1], flag, consume)

        self._produce(left, outer)

    def _hash_join(self, left, right, condition, join_type, keys, consume: Consumer) -> None:
        table = self._new("ht")
        iterator = self._new("it")
        flag = self._new("f") if join_type == "LEFT" else None
        self._emit("HT_CLEAR", table, comment="hash join: build phase")
        built: list[Env] = []

        def build(env_right: Env) -> None:
            built.append(env_right)
            for _, right_key in keys:
                self._expr(right_key, env_right)
            self._emit("HT_INSERT", table, len(keys), env_right.registers())

        self._produce(right, build)

        def probe(env_left: Env) -> None:
            env_right = built[-1]
            if flag:
                self._emit("FLAG_SET", flag, False)
            for left_key, _ in keys:
                self._expr(left_key, env_left)
            self._emit("HT_PROBE", iterator, table, len(keys), comment="hash join: probe phase")
            loop, end = self._label("probe"), self._label("probe_end")
            self._place(loop)
            self._emit("RESTORE", iterator, end)
            self._matched(env_left.merged(env_right), condition, flag, consume)
            self._emit("JUMP", loop)
            self._place(end)
            if flag:
                self._pad_unmatched(env_left, env_right, flag, consume)

        self._produce(left, probe)

    def _merge_join(self, left, right, condition, join_type, keys, consume: Consumer) -> None:
        left_buffer, right_buffer = self._new("buf"), self._new("buf")
        iterator = self._new("it")
        captured: dict[str, Env] = {}

        def materialize(side: str, buffer: str, index: int) -> Consumer:
            def body(env: Env) -> None:
                captured[side] = env
                for pair in keys:
                    self._expr(pair[index], env)
                self._emit("BUF_APPEND", buffer, len(keys), env.registers())
            return body

        directions = ("ASC",) * len(keys)
        self._emit("BUF_CLEAR", left_buffer, comment="merge join: sort left input")
        self._produce(left, materialize("left", left_buffer, 0))
        self._emit("BUF_SORT", left_buffer, directions)
        self._emit("BUF_CLEAR", right_buffer, comment="merge join: sort right input")
        self._produce(right, materialize("right", right_buffer, 1))
        self._emit("BUF_SORT", right_buffer, directions)

        outer = join_type == "LEFT"
        self._emit("MERGE_OPEN", iterator, left_buffer, right_buffer, outer, captured["right"].registers())
        loop, end = self._label("merge"), self._label("merge_end")
        self._place(loop)
        self._emit("RESTORE", iterator, end)
        env = captured["left"].merged(captured["right"])
        if outer:
            consume(env)  # the merge already applied the (key-only) join condition
        else:
            self._filtered(env, condition, consume)
        self._emit("JUMP", loop)
        self._place(end)

    def _matched(self, env: Env, condition, flag: Optional[str], consume: Consumer) -> None:
        skip = self._label("skip")
        if condition is not None:
            self._expr(condition, env)
            self._emit("JUMP_IF_FALSE", skip, comment=f"ON {render(condition)}")
        if flag:
            self._emit("FLAG_SET", flag, True)
        consume(env)
        self._place(skip)

    def _pad_unmatched(self, env_left: Env, env_right: Env, flag: str, consume: Consumer) -> None:
        done = self._label("matched")
        self._emit("JUMP_IF_FLAG", flag, done, comment="LEFT JOIN: row already matched")
        for register in env_right.registers():
            self._emit("BIND_NULL", register, comment="pad right side with NULLs")
        consume(env_left.merged(env_right))
        self._place(done)

    def _project(self, node: PhysicalNode, consume: Consumer) -> None:
        logical = node.logical
        expressions = list(getattr(logical, "expressions", []))
        names = list(getattr(logical, "names", []))
        register = self._new("r")

        def body(env: Env) -> None:
            for expression in expressions:
                self._expr(expression, env)
            self._emit("MAKE_ROW", register, len(expressions), comment="SELECT list")
            projected = env.extended()
            for index, (expression, name) in enumerate(zip(expressions, names)):
                projected.slots[("expr", canonical(expression))] = (register, index)
                projected.slots[("name", name.lower())] = (register, index)
            projected.output = [(register, index) for index in range(len(expressions))]
            consume(projected)

        self._produce(node.children[0], body)

    def _distinct(self, node: PhysicalNode, consume: Consumer) -> None:
        seen = self._new("set")
        expressions = node.details.get("expressions") or []
        self._emit("DISTINCT_CLEAR", seen)

        def body(env: Env) -> None:
            skip = self._label("dup")
            values = expressions or [None] * len(env.output or [])
            for index, expression in enumerate(values):
                if expression is None:
                    register, slot = env.output[index]
                    self._emit("LOAD", register, slot)
                else:
                    self._expr(expression, env)
            self._emit("DISTINCT_CHECK", seen, len(values), skip, comment="skip duplicate row")
            consume(env)
            self._place(skip)

        self._produce(node.children[0], body)

    def _sort(self, node: PhysicalNode, consume: Consumer) -> None:
        items = node.details.get("items") or []
        buffer, iterator = self._new("buf"), self._new("it")
        captured: list[Env] = []
        self._emit("BUF_CLEAR", buffer, comment=f"ORDER BY {node.details.get('keys', '')}")

        def body(env: Env) -> None:
            captured.append(env)
            for item in items:
                self._expr(item.column, env)
            self._emit("BUF_APPEND", buffer, len(items), env.registers())

        self._produce(node.children[0], body)
        self._emit("BUF_SORT", buffer, tuple(item.direction for item in items))
        self._emit("BUF_OPEN", iterator, buffer)
        loop, end = self._label("sorted"), self._label("sorted_end")
        self._place(loop)
        self._emit("RESTORE", iterator, end)
        consume(captured[-1])
        self._emit("JUMP", loop)
        self._place(end)

    def _aggregate(self, node: PhysicalNode, consume: Consumer) -> None:
        group_by = list(node.details.get("groupBy") or [])
        functions = list(node.details.get("functions") or [])
        specs = tuple((f.name, bool(f.distinct)) for f in functions)
        table, iterator, register = self._new("agg"), self._new("it"), self._new("r")
        self._emit("AGG_CLEAR", table, len(group_by), specs, comment=node.details.get("text", ""))

        def body(env: Env) -> None:
            for column in group_by:
                self._expr(column, env)
            for function in functions:
                if function.star or not function.args:
                    self._emit("CONST", 1, comment=f"{render(function)} counts rows")
                else:
                    self._expr(function.args[0], env)
            self._emit("AGG_UPDATE", table)

        self._produce(node.children[0], body)
        self._emit("AGG_OPEN", iterator, table, register)
        loop, end = self._label("group"), self._label("group_end")
        self._place(loop)
        self._emit("RESTORE", iterator, end, comment="next group")

        env = Env()
        for index, column in enumerate(group_by):
            env.slots[("expr", canonical(column))] = (register, index)
            if isinstance(column, ast.Column):
                source = self.ctx.source_of(column)
                env.slots[("col", source, column.name.lower())] = (register, index)
                env.slots[("name", column.name.lower())] = (register, index)
        for index, function in enumerate(functions, start=len(group_by)):
            env.slots[("expr", canonical(function))] = (register, index)
        consume(env)
        self._emit("JUMP", loop)
        self._place(end)

    def _limit(self, node: PhysicalNode, consume: Consumer) -> None:
        counter = self._new("lim")
        count = int(node.details.get("count", 0))
        done = self._label("limit_reached")
        self._emit("LIMIT_RESET", counter)

        def body(env: Env) -> None:
            self._emit("LIMIT_CHECK", counter, count, done, comment=f"LIMIT {count}")
            consume(env)

        self._produce(node.children[0], body)
        self._place(done)

    # -- expressions ---------------------------------------------------------
    def _expr(self, node: Optional[ast.Node], env: Env) -> None:
        if node is None:
            self._emit("CONST", True)
            return
        if isinstance(node, ast.Literal):
            self._emit("CONST", node.value)
        elif isinstance(node, (ast.Column, ast.FunctionCall)):
            register, slot = self._lookup(node, env)
            self._emit("LOAD", register, slot, comment=render(node))
        elif isinstance(node, ast.Comparison):
            self._expr(node.left, env)
            self._expr(node.right, env)
            self._emit(_COMPARISON_OPS[node.operator])
        elif isinstance(node, ast.LogicalExpression):
            self._expr(node.left, env)
            self._expr(node.right, env)
            self._emit(node.operator.upper())
        elif isinstance(node, ast.BinaryExpression):
            if node.operator == "NOT":
                self._expr(node.right, env)
                self._emit("NOT")
            else:
                self._expr(node.left, env)
                self._expr(node.right, env)
                self._emit(_ARITHMETIC_OPS[node.operator])
        else:
            raise CodegenError(f"Cannot compile expression {render(node)}")

    def _lookup(self, node: ast.Node, env: Env) -> tuple[str, Any]:
        found = env.slots.get(("expr", canonical(node)))
        if found is not None:
            return found
        if isinstance(node, ast.Column):
            source = self.ctx.source_of(node)
            name = node.name.lower()
            for key in (("col", source, name), ("name", name)):
                if key in env.slots:
                    return env.slots[key]
            if node.table is None:
                matches = [v for k, v in env.slots.items() if k[0] == "col" and k[2] == name]
                if len(matches) == 1:
                    return matches[0]
        raise CodegenError(f"{render(node)} is not available at this point in the plan")


# -- helpers -----------------------------------------------------------------
def _output_names(plan: PhysicalNode) -> list[str]:
    node: Optional[PhysicalNode] = plan
    while node is not None:
        if node.op == "Project" and node.logical is not None:
            return list(getattr(node.logical, "names", []))
        node = node.children[0] if node.children else None
    return []


def _sources(node: PhysicalNode) -> set[str]:
    if node.op in ("SeqScan", "IndexScan"):
        return {(node.details.get("alias") or node.details["table"]).lower()}
    found: set[str] = set()
    for child in node.children:
        found |= _sources(child)
    return found


def _equi_keys(condition, left: set[str], right: set[str], ctx: ExprContext) -> list[tuple[ast.Node, ast.Node]]:
    """Equality conjuncts of the form left_expr = right_expr usable as join keys."""
    keys = []
    for predicate in conjuncts(condition):
        if not (isinstance(predicate, ast.Comparison) and predicate.operator == "="):
            continue
        a, b = referenced_sources(predicate.left, ctx), referenced_sources(predicate.right, ctx)
        if a and b and a <= left and b <= right:
            keys.append((predicate.left, predicate.right))
        elif a and b and a <= right and b <= left:
            keys.append((predicate.right, predicate.left))
    return keys


def _sargable(condition, column: Optional[str]) -> Optional[tuple[str, Any]]:
    """The first ``column <op> literal`` conjunct an index on ``column`` can answer."""
    if column is None:
        return None
    for predicate in conjuncts(condition):
        if not isinstance(predicate, ast.Comparison) or predicate.operator in ("<>", "!="):
            continue
        left, right, op = predicate.left, predicate.right, predicate.operator
        if isinstance(left, ast.Literal) and isinstance(right, ast.Column):
            left, right, op = right, left, _FLIPPED[op]
        if isinstance(left, ast.Column) and isinstance(right, ast.Literal) and left.name.lower() == column.lower():
            return op, right.value
    return None
