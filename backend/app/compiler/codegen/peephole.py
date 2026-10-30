"""Peephole optimization over VM bytecode.

Slides a small window over the label-form instruction list and rewrites local
patterns, repeating until nothing changes. Every rewrite is recorded with the
code before and after, in the same spirit as the logical optimizer's records.

Rules:
  * constant folding        CONST a; CONST b; ADD          -> CONST a+b
  * constant branch         CONST TRUE; JUMP_IF_FALSE L     -> (removed)
                            CONST FALSE; JUMP_IF_FALSE L    -> JUMP L
  * jump threading          any jump to L where L: JUMP M   -> jump straight to M
  * jump to next            JUMP L; L:                      -> L:
  * dead code               JUMP L; <unreachable>...        -> JUMP L
  * store-load forwarding   MAKE_ROW r, 2; LOAD r, 0; LOAD r, 1  -> (removed)
                            when nothing else reads r: the values are already
                            on the stack in that order

Deliberately absent: rewriting "NOT; JUMP_IF_FALSE L" to "JUMP_IF_TRUE L". Under
SQL's three-valued logic NOT NULL is NULL, so the original jumps when x is NULL
and the rewrite would not.
"""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any

from .bytecode import Instr, Item, Label, instruction_count

_FOLDABLE = {
    "ADD": operator.add, "SUB": operator.sub, "MUL": operator.mul,
    "EQ": operator.eq, "NE": operator.ne, "LT": operator.lt,
    "LE": operator.le, "GT": operator.gt, "GE": operator.ge,
}

RULE_DESCRIPTIONS = {
    "Constant Folding": "Operators on two constants are evaluated at compile time.",
    "Constant Branch": "A branch on a known value is removed or made unconditional.",
    "Jump Threading": "A jump that lands on another jump goes straight to the final target.",
    "Jump To Next": "A jump to the very next instruction does nothing and is removed.",
    "Dead Code Elimination": "Instructions after an unconditional jump that no jump reaches are removed.",
    "Store-Load Forwarding": "A row packed into a register and immediately unpacked, with no other reader, is never stored.",
}


@dataclass
class PeepholeRecord:
    rule: str
    before: list[str]
    after: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "before": self.before, "after": self.after}


@dataclass
class PeepholeResult:
    items: list[Item]
    records: list[PeepholeRecord] = field(default_factory=list)
    instructions_before: int = 0
    instructions_after: int = 0

    def summary(self) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.rule] = counts.get(record.rule, 0) + 1
        return [
            {"rule": rule, "applications": count, "description": RULE_DESCRIPTIONS[rule]}
            for rule, count in counts.items()
        ]

    def to_dict(self, max_examples: int = 100) -> dict[str, Any]:
        return {
            "instructionsBefore": self.instructions_before,
            "instructionsAfter": self.instructions_after,
            "rules": self.summary(),
            "examples": [r.to_dict() for r in self.records[:max_examples]],
        }


def _show(item: Item) -> str:
    if isinstance(item, Label):
        return f"{item.name}:"
    args = ", ".join(repr(a) if not isinstance(a, str) or item.op == "CONST" else a for a in item.args)
    return f"{item.op} {args}".strip()


class PeepholeOptimizer:
    def __init__(self, max_passes: int = 20) -> None:
        self.max_passes = max_passes

    def optimize(self, items: list[Item]) -> PeepholeResult:
        code = [Instr(i.op, i.args, i.comment) if isinstance(i, Instr) else i for i in items]
        result = PeepholeResult(code, instructions_before=instruction_count(code))
        for _ in range(self.max_passes):
            changed = False
            for rule in (self._fold, self._constant_branch, self._thread,
                         self._jump_to_next, self._dead_code, self._forward_stores):
                changed |= rule(code, result.records)
            if not changed:
                break
        result.items = code
        result.instructions_after = instruction_count(code)
        return result

    # -- rules ---------------------------------------------------------------
    def _fold(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        changed = False
        i = 0
        while i + 2 < len(code):
            a, b, op = code[i], code[i + 1], code[i + 2]
            if (isinstance(a, Instr) and isinstance(b, Instr) and isinstance(op, Instr)
                    and a.op == "CONST" and b.op == "CONST" and op.op in _FOLDABLE
                    and a.args[0] is not None and b.args[0] is not None):
                try:
                    value = _FOLDABLE[op.op](a.args[0], b.args[0])
                except TypeError:
                    i += 1
                    continue
                folded = Instr("CONST", (value,), "folded at compile time")
                records.append(PeepholeRecord("Constant Folding", [_show(a), _show(b), _show(op)], [_show(folded)]))
                code[i:i + 3] = [folded]
                changed = True
                continue
            i += 1
        return changed

    def _constant_branch(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        changed = False
        i = 0
        while i + 1 < len(code):
            a, b = code[i], code[i + 1]
            if isinstance(a, Instr) and isinstance(b, Instr) and a.op == "CONST" and b.op in ("JUMP_IF_FALSE", "JUMP_IF_TRUE"):
                taken = (a.args[0] is not True) if b.op == "JUMP_IF_FALSE" else (a.args[0] is True)
                replacement = [Instr("JUMP", b.args, b.comment)] if taken else []
                records.append(PeepholeRecord("Constant Branch", [_show(a), _show(b)], [_show(r) for r in replacement] or ["(removed)"]))
                code[i:i + 2] = replacement
                changed = True
                continue
            i += 1
        return changed

    def _thread(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        positions = {item: index for index, item in enumerate(code) if isinstance(item, Label)}
        changed = False
        for item in code:
            if not isinstance(item, Instr):
                continue
            for target in item.targets():
                final = self._final_target(code, positions, target)
                if final != target:
                    before = _show(item)
                    item.retarget(target, final)
                    records.append(PeepholeRecord("Jump Threading", [before, f"{target.name}: JUMP {final.name}"], [_show(item)]))
                    changed = True
        return changed

    @staticmethod
    def _final_target(code: list[Item], positions: dict[Label, int], label: Label) -> Label:
        seen = {label}
        current = label
        while True:
            index = positions[current] + 1
            while index < len(code) and isinstance(code[index], Label):
                index += 1
            if index >= len(code):
                return current
            instr = code[index]
            if instr.op != "JUMP" or instr.args[0] in seen:
                return current
            current = instr.args[0]
            seen.add(current)

    def _jump_to_next(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        changed = False
        i = 0
        while i < len(code):
            item = code[i]
            if isinstance(item, Instr) and item.op == "JUMP":
                j = i + 1
                following: set[Label] = set()
                while j < len(code) and isinstance(code[j], Label):
                    following.add(code[j])
                    j += 1
                if item.args[0] in following:
                    records.append(PeepholeRecord("Jump To Next", [_show(item), f"{item.args[0].name}:"], [f"{item.args[0].name}:"]))
                    del code[i]
                    changed = True
                    continue
            i += 1
        return changed

    def _dead_code(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        referenced = {t for item in code if isinstance(item, Instr) for t in item.targets()}
        changed = False
        i = 0
        while i < len(code):
            item = code[i]
            if isinstance(item, Instr) and item.op in ("JUMP", "HALT"):
                j = i + 1
                while j < len(code) and not (isinstance(code[j], Label) and code[j] in referenced):
                    j += 1
                dead = [x for x in code[i + 1:j] if isinstance(x, Instr)]
                if dead:
                    records.append(PeepholeRecord("Dead Code Elimination", [_show(item)] + [_show(x) for x in dead], [_show(item)]))
                    del code[i + 1:j]
                    changed = True
            i += 1
        return changed

    def _forward_stores(self, code: list[Item], records: list[PeepholeRecord]) -> bool:
        patterns: dict[str, list[int]] = {}
        for i, item in enumerate(code):
            if isinstance(item, Instr) and item.op == "MAKE_ROW" and _reloads(code, i):
                patterns.setdefault(item.args[0], []).append(i)
        changed = False
        for register, starts in patterns.items():
            covered = {i + k for i in starts for k in range(code[i].args[1] + 1)}
            other_readers = any(
                i not in covered and isinstance(item, Instr) and _mentions(item, register)
                for i, item in enumerate(code)
            )
            if other_readers:
                continue
            for i in sorted(starts, reverse=True):
                span = code[i:i + code[i].args[1] + 1]
                records.append(PeepholeRecord("Store-Load Forwarding", [_show(x) for x in span], ["(removed)"]))
                del code[i:i + len(span)]
                changed = True
        return changed


def _reloads(code: list[Item], i: int) -> bool:
    """MAKE_ROW r, n followed directly by LOAD r, 0 ... LOAD r, n-1."""
    register, count = code[i].args
    following = code[i + 1:i + 1 + count]
    return len(following) == count and all(
        isinstance(x, Instr) and x.op == "LOAD" and x.args == (register, k)
        for k, x in enumerate(following)
    )


def _mentions(item: Instr, register: str) -> bool:
    return any(a == register or (isinstance(a, tuple) and register in a) for a in item.args)
