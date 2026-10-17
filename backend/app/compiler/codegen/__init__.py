"""Code generation back end: physical plan -> bytecode -> peephole -> VM."""
from .service import compile_plan, run_codegen

__all__ = ["compile_plan", "run_codegen"]
