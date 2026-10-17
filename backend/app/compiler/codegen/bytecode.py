"""Bytecode instruction set for the queryX virtual machine.

The code generator emits a flat list of :class:`Instr` interleaved with
:class:`Label` markers. Jumps name labels, so the peephole optimizer can move
and delete code freely; :func:`assemble` then resolves every label to an
absolute instruction address.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union


@dataclass(frozen=True)
class Label:
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Address:
    """A resolved jump target in an assembled program."""

    value: int

    def __repr__(self) -> str:
        return f"@{self.value:04d}"


@dataclass
class Instr:
    op: str
    args: tuple[Any, ...] = ()
    comment: str = ""

    def targets(self) -> list[Label]:
        return [a for a in self.args if isinstance(a, Label)]

    def retarget(self, old: Label, new: Label) -> None:
        self.args = tuple(new if a == old else a for a in self.args)


Item = Union[Instr, Label]

# Opcodes grouped by role; documented for the dashboard and the README.
OPCODES: dict[str, str] = {
    "SCAN_OPEN": "Open a sequential cursor over a table",
    "INDEX_OPEN": "Open a cursor over the rows an index range selects",
    "NEXT": "Advance a cursor and bind its row; jump when exhausted",
    "LOAD": "Push a column of a bound row",
    "CONST": "Push a constant",
    "EQ": "Pop two values, push a = b",
    "NE": "Pop two values, push a <> b",
    "LT": "Pop two values, push a < b",
    "LE": "Pop two values, push a <= b",
    "GT": "Pop two values, push a > b",
    "GE": "Pop two values, push a >= b",
    "ADD": "Pop two values, push a + b",
    "SUB": "Pop two values, push a - b",
    "MUL": "Pop two values, push a * b",
    "DIV": "Pop two values, push a / b",
    "MOD": "Pop two values, push a % b",
    "AND": "Three-valued logical AND",
    "OR": "Three-valued logical OR",
    "NOT": "Three-valued logical NOT",
    "JUMP": "Unconditional jump",
    "JUMP_IF_FALSE": "Pop a value; jump unless it is TRUE",
    "JUMP_IF_TRUE": "Pop a value; jump if it is TRUE",
    "MAKE_ROW": "Pop n values into a tuple bound to a register",
    "EMIT": "Pop n values and append them to the result",
    "FLAG_SET": "Set a boolean flag (outer-join match tracking)",
    "JUMP_IF_FLAG": "Jump if a flag is set",
    "BIND_NULL": "Bind NULL to a register (outer-join padding)",
    "HT_CLEAR": "Empty a hash table",
    "HT_INSERT": "Pop a key; store the bound rows under it",
    "HT_PROBE": "Pop a key; iterate the rows stored under it",
    "BUF_CLEAR": "Empty a materialization buffer",
    "BUF_APPEND": "Pop sort keys; store them with the bound rows",
    "BUF_SORT": "Sort a buffer by its keys",
    "BUF_OPEN": "Iterate a buffer",
    "MERGE_OPEN": "Iterate the matches of two sorted buffers",
    "RESTORE": "Advance an iterator and rebind its rows; jump when exhausted",
    "AGG_CLEAR": "Empty an aggregation table",
    "AGG_UPDATE": "Pop group keys and arguments; update accumulators",
    "AGG_OPEN": "Iterate finished groups",
    "DISTINCT_CLEAR": "Empty a seen-set",
    "DISTINCT_CHECK": "Pop n values; jump if already seen",
    "LIMIT_RESET": "Reset a row counter",
    "LIMIT_CHECK": "Count a row; jump when the limit is exceeded",
    "HALT": "Stop execution",
}

JUMP_OPS = frozenset({"JUMP", "JUMP_IF_FALSE", "JUMP_IF_TRUE"})
BINARY_OPS = frozenset({"EQ", "NE", "LT", "LE", "GT", "GE", "ADD", "SUB", "MUL", "DIV", "MOD", "AND", "OR"})


@dataclass
class Program:
    """An assembled program: label-free instructions with absolute jump targets."""

    instructions: list[Instr] = field(default_factory=list)
    output_columns: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.instructions)

    def disassemble(self) -> list[dict[str, Any]]:
        lines = []
        for address, instr in enumerate(self.instructions):
            lines.append(
                {
                    "address": address,
                    "op": instr.op,
                    "args": _format_args(instr.op, instr.args),
                    "comment": instr.comment,
                }
            )
        return lines

    def to_text(self) -> str:
        out = []
        for line in self.disassemble():
            text = f"{line['address']:04d}  {line['op']:<15}{line['args']}"
            if line["comment"]:
                text = f"{text:<52} ; {line['comment']}"
            out.append(text)
        return "\n".join(out)


def _format_args(op: str, args: tuple[Any, ...]) -> str:
    parts = []
    for arg in args:
        if isinstance(arg, str) and op != "CONST":
            parts.append(arg if arg.isidentifier() else repr(arg))
        elif isinstance(arg, tuple):
            parts.append("(" + ", ".join(str(a) for a in arg) + ")")
        else:
            parts.append(repr(arg))
    return ", ".join(parts)


def assemble(items: list[Item], output_columns: list[str]) -> Program:
    """Resolve labels to addresses and drop the label markers."""
    addresses: dict[Label, int] = {}
    count = 0
    for item in items:
        if isinstance(item, Label):
            addresses[item] = count
        else:
            count += 1
    instructions = []
    for item in items:
        if isinstance(item, Instr):
            args = tuple(Address(addresses[a]) if isinstance(a, Label) else a for a in item.args)
            instructions.append(Instr(item.op, args, item.comment))
    return Program(instructions, list(output_columns))


def instruction_count(items: list[Item]) -> int:
    return sum(1 for item in items if isinstance(item, Instr))
