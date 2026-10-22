import { useEffect, useRef, useState } from "react";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { DiagnosticsList } from "../components/DiagnosticsList";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { ExamplePicker } from "../features/editor/ExamplePicker";
import { SqlEditor } from "../features/editor/SqlEditor";
import { formatNumber, formatPercent } from "../lib/format";
import { useQuery } from "../store/QueryProvider";

const STAGES = [
  { id: "tokens", label: "Lexer", description: "Token stream" },
  { id: "ast", label: "Parser", description: "Abstract syntax tree" },
  { id: "ir", label: "IR", description: "Relational algebra" },
  { id: "optimization", label: "Optimizer", description: "Rule rewrites" },
  { id: "plans", label: "Planner", description: "Physical plans" },
  { id: "bytecode", label: "Code gen + VM", description: "Bytecode, executed" },
];

export function EditorPage({
  onNavigate,
  autoRun,
}: {
  onNavigate: (id: string) => void;
  autoRun?: boolean;
}) {
  const { sql, setSql, result, loading, error, examples, run, clear } = useQuery();
  const [activeExample, setActiveExample] = useState<string | undefined>("join_pushdown");
  const didAutoRun = useRef(false);

  useEffect(() => {
    if (autoRun && !didAutoRun.current) {
      didAutoRun.current = true;
      void run(sql);
    }
  }, [autoRun, run, sql]);

  const handleExample = (example: { id: string; sql: string }) => {
    setActiveExample(example.id);
    setSql(example.sql);
    void run(example.sql);
  };

  const codegen = result?.codegen;
  const checks = codegen?.planChecks ?? [];
  const verified = checks.filter((check) => check.status === "match").length;
  const unoptimized = codegen?.unoptimizedExecution?.instructionsExecuted ?? 0;
  const executed = codegen?.execution?.instructionsExecuted ?? 0;
  const savedPercent = unoptimized ? ((unoptimized - executed) / unoptimized) * 100 : 0;

  const stageCounts: Record<string, number> = {
    tokens: result?.tokens.length ?? 0,
    ast: result?.ast ? 1 : 0,
    ir: result?.relationalIR ? 1 : 0,
    optimization: result?.optimizationSteps.length ?? 0,
    plans: result?.candidatePlans.length ?? 0,
    bytecode: result?.codegen?.bytecode?.length ?? 0,
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card
            title="SQL source"
            subtitle="Write a supported SQL query, then run the full compiler pipeline"
            actions={
              <>
                <button
                  type="button"
                  onClick={clear}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() => run()}
                  disabled={loading}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                >
                  {loading ? "Running…" : "Run & Optimize"}
                </button>
              </>
            }
          >
            <SqlEditor value={sql} onChange={setSql} onRun={() => run()} />
            {error && <div className="mt-3"><ErrorState message={error} /></div>}
            {result?.errors?.length ? (
              <div className="mt-3">
                <DiagnosticsList diagnostics={result.errors} title="Compilation errors" />
              </div>
            ) : null}
            {result?.semanticErrors?.length ? (
              <div className="mt-3">
                <DiagnosticsList diagnostics={result.semanticErrors} title="Semantic errors" />
              </div>
            ) : null}
          </Card>

          <Card title="Examples" subtitle="Pick a query to compile">
            <ExamplePicker examples={examples} onSelect={handleExample} activeId={activeExample} />
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Pipeline" subtitle="Compiler stages for the current query">
            {loading && <Loading label="Compiling…" />}
            {!loading && !result && (
              <EmptyState
                title="No compilation yet"
                description="Run a query to populate every stage of the pipeline."
              />
            )}
            {!loading && result && (
              <ol className="space-y-1.5">
                {STAGES.map((stage, index) => {
                  const enabled = stageCounts[stage.id] > 0;
                  return (
                    <li key={stage.id}>
                      <button
                        type="button"
                        onClick={() => onNavigate(stage.id)}
                        disabled={!enabled}
                        className="flex w-full items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-left text-sm transition-colors enabled:hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:enabled:hover:bg-slate-800/40"
                      >
                        <span className="flex items-center gap-2">
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            {index + 1}
                          </span>
                          <span>
                            <span className="font-medium">{stage.label}</span>
                            <span className="ml-2 text-xs text-slate-400">{stage.description}</span>
                          </span>
                        </span>
                        <Badge tone={enabled ? "green" : "slate"}>
                          {stageCounts[stage.id]}
                        </Badge>
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}
          </Card>

          {codegen?.success && codegen.execution && codegen.peephole && (
            <Card
              title="Compiled & executed"
              subtitle={`${codegen.plan} compiled to bytecode and run on the queryX VM`}
              className="border-blue-500/60 dark:border-blue-500/50"
            >
              <dl className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-slate-400">Bytecode</dt>
                  <dd className="text-xl font-semibold text-blue-600 dark:text-blue-400">
                    {codegen.peephole.instructionsAfter}
                  </dd>
                  <dd className="text-[11px] text-slate-400">instructions</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-slate-400">Peephole</dt>
                  <dd className="text-xl font-semibold text-blue-600 dark:text-blue-400">
                    {formatPercent(savedPercent)}
                  </dd>
                  <dd className="text-[11px] text-slate-400">fewer executed</dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wide text-slate-400">Verified</dt>
                  <dd className="text-xl font-semibold text-emerald-600 dark:text-emerald-400">
                    {verified}/{checks.length}
                  </dd>
                  <dd className="text-[11px] text-slate-400">plans agree</dd>
                </div>
              </dl>
              <button
                type="button"
                onClick={() => onNavigate("bytecode")}
                className="mt-3 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
              >
                See the bytecode and {formatNumber(codegen.execution.rowCount)} result rows →
              </button>
            </Card>
          )}
        </div>
      </div>

    </div>
  );
}
