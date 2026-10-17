"""The end-to-end compiler pipeline used by the API layer.

Wires every stage together:

    SQL -> Lexer -> Parser -> AST -> Semantic Analyzer -> IR
        -> Optimizer -> Physical Planner -> Cost Estimator -> Selector -> Explain
        -> Code Generator -> Peephole Optimizer -> Virtual Machine

The pipeline is stateless with respect to a single request but holds the loaded
statistics/catalog so repeated requests are cheap.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from ..compiler.codegen import run_codegen
from ..compiler.codegen.sample_data import SampleDatabase, build_sample_database
from ..compiler.cost.config import CostConfig, load_cost_config
from ..compiler.cost.model import CostEstimator
from ..compiler.cost.statistics import StatsStore, load_statistics
from ..compiler.explain.engine import ExplainEngine
from ..compiler.ir.builder import build_ir
from ..compiler.ir.expr import ExprContext, render_tree
from ..compiler.lexer.errors import CompilerError, LexError, ParseError
from ..compiler.lexer.lexer import tokenize
from ..compiler.optimizer.engine import OptimizerEngine
from ..compiler.parser.parser import parse
from ..compiler.planner.generator import PhysicalPlanGenerator
from ..compiler.planner.selector import PlanSelector
from ..compiler.semantic.analyzer import SemanticAnalyzer
from ..compiler.semantic.catalog import Catalog


class QueryPipeline:
    def __init__(self, stats_path: Optional[str] = None) -> None:
        self.stats_path = stats_path
        self.reload()

    def reload(self) -> None:
        self.stats: StatsStore = load_statistics(self.stats_path)
        self.config: CostConfig = load_cost_config(self.stats_path)
        self.catalog: Catalog = self.stats.to_catalog()
        self.database: SampleDatabase = build_sample_database(self.stats)

    # -- individual stages ---------------------------------------------------
    def lex(self, sql: str) -> dict[str, Any]:
        try:
            tokens = tokenize(sql)
        except LexError as error:
            return {"success": False, "tokens": [], "errors": [error.diagnostic.to_dict()]}
        return {"success": True, "tokens": [t.to_dict() for t in tokens], "errors": []}

    def parse(self, sql: str) -> dict[str, Any]:
        lex_result = self.lex(sql)
        if not lex_result["success"]:
            return {"success": False, "ast": None, "tokens": [], "errors": lex_result["errors"]}
        try:
            query = parse_from_dicts(sql)
        except ParseError as error:
            return {
                "success": False,
                "ast": None,
                "tokens": lex_result["tokens"],
                "errors": [error.diagnostic.to_dict()],
            }
        return {
            "success": True,
            "ast": query.to_dict(),
            "tokens": lex_result["tokens"],
            "errors": [],
        }

    def analyze(self, sql: str) -> dict[str, Any]:
        lex_result = self.lex(sql)
        if not lex_result["success"]:
            return {"success": False, "ast": None, "semantic": None, "errors": lex_result["errors"]}
        try:
            query = parse_from_dicts(sql)
        except ParseError as error:
            return {
                "success": False,
                "ast": None,
                "semantic": None,
                "errors": [error.diagnostic.to_dict()],
            }
        analyzer = SemanticAnalyzer(self.catalog)
        semantic = analyzer.analyze(query)
        return {
            "success": semantic.valid,
            "ast": query.to_dict(),
            "semantic": semantic.to_dict(),
            "errors": [e.to_dict() for e in semantic.errors],
        }

    # -- full compile --------------------------------------------------------
    def compile(self, sql: str) -> dict[str, Any]:
        start = time.perf_counter()
        response: dict[str, Any] = {
            "success": False,
            "query": sql,
            "tokens": [],
            "ast": None,
            "semanticErrors": [],
            "relationalIR": None,
            "optimizedIR": None,
            "optimizationSteps": [],
            "candidatePlans": [],
            "selectedPlan": None,
            "costComparison": [],
            "explanation": None,
            "codegen": None,
            "statistics": self.stats.to_dict(),
            "costConfig": self.config.to_dict(),
            "metrics": {},
            "errors": [],
        }

        # 1. Lexer
        try:
            tokens = tokenize(sql)
        except LexError as error:
            response["errors"] = [error.diagnostic.to_dict()]
            response["metrics"] = {"stage": "lexer", "totalMs": _ms(start)}
            return response
        response["tokens"] = [t.to_dict() for t in tokens]

        # 2. Parser
        try:
            query = parse(tokens)
        except ParseError as error:
            response["errors"] = [error.diagnostic.to_dict()]
            response["metrics"] = {"stage": "parser", "totalMs": _ms(start)}
            return response
        response["ast"] = query.to_dict()

        # 3. Semantic analysis
        semantic = SemanticAnalyzer(self.catalog).analyze(query)
        response["semanticErrors"] = [e.to_dict() for e in semantic.errors]
        if not semantic.valid:
            response["metrics"] = {"stage": "semantic", "totalMs": _ms(start)}
            return response

        # 4. IR construction
        ir_root = build_ir(query, self.catalog, semantic)
        response["relationalIR"] = ir_root.to_dict()
        response["relationalIRText"] = render_tree(ir_root)

        ctx = ExprContext.from_semantic(semantic.resolution, semantic.scope)

        # 5. Rule-based optimization
        optimizer = OptimizerEngine(self.stats, self.config, ctx)
        optimize_result = optimizer.optimize(ir_root)
        response["optimizedIR"] = optimize_result.root.to_dict()
        response["optimizedIRText"] = render_tree(optimize_result.root)
        response["optimizationSteps"] = [r.to_dict() for r in optimize_result.records]

        # 6. Physical plan generation
        plan_start = time.perf_counter()
        generator = PhysicalPlanGenerator(self.stats, self.config, ctx)
        candidates = generator.generate(optimize_result.root)
        plan_ms = _ms(plan_start)

        # 7. Cost-based selection
        estimator = CostEstimator(self.stats, self.config, ctx)
        selection = PlanSelector(estimator).evaluate(candidates)
        response["candidatePlans"] = [e.to_dict() for e in selection.evaluations]
        response["costComparison"] = selection.cost_comparison
        if selection.selected is not None:
            response["selectedPlan"] = selection.selected.to_dict()

        # 8. Explainability
        explainer = ExplainEngine()
        response["explanation"] = explainer.explain(
            optimize_result.records, selection, optimize_result.rules_used()
        )

        # 9. Code generation, peephole optimization and execution on the VM
        codegen_start = time.perf_counter()
        response["codegen"] = run_codegen(selection, ctx, self.database)
        codegen_ms = _ms(codegen_start)

        response["success"] = True
        response["metrics"] = {
            "stage": "complete",
            "totalMs": _ms(start),
            "planGenerationMs": plan_ms,
            "codegenMs": codegen_ms,
            "candidateCount": len(selection.evaluations),
            "rulesApplied": optimize_result.rules_applied,
            "rulesUsed": optimize_result.rules_used(),
        }
        return response

    # -- metadata ------------------------------------------------------------
    def schema(self) -> dict[str, Any]:
        return self.catalog.to_dict()

    def statistics(self) -> dict[str, Any]:
        return {
            "tables": self.stats.to_dict()["tables"],
            "costConfig": self.config.to_dict(),
        }


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def parse_from_dicts(sql: str):
    """Helper used by the individual-stage endpoints."""
    return parse(tokenize(sql))
