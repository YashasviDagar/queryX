import { useEffect, useRef, useState } from "react";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { DiagnosticsList } from "../components/DiagnosticsList";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { ExamplePicker } from "../features/editor/ExamplePicker";
import { SqlEditor } from "../features/editor/SqlEditor";
import { useQuery } from "../store/QueryProvider";

const STAGES = [
  { id: "tokens", label: "Lexer", description: "Token stream" },
  { id: "ast", label: "Parser", description: "Abstract syntax tree" },
  { id: "ir", label: "IR", description: "Relational algebra" },
  { id: "optimization", label: "Optimizer", description: "Rule rewrites" },
  { id: "plans", label: "Planner", description: "Physical plans" },
  { id: "analytics", label: "Analytics", description: "Cost comparison" },
  { id: "bytecode", label: "Code gen", description: "Bytecode on the VM" },
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

  const stageCounts: Record<string, number> = {
    tokens: result?.tokens.length ?? 0,
    ast: result?.ast ? 1 : 0,
    ir: result?.relationalIR ? 1 : 0,
    optimization: result?.optimizationSteps.length ?? 0,
    plans: result?.candidatePlans.length ?? 0,
    analytics: result?.costComparison.length ?? 0,
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

          <Card title="Examples" subtitle="Curated queries that exercise each optimizer rule">
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

          {result?.success && result.selectedPlan && (
            <Card title="Selected plan" subtitle="Lowest estimated cost">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">
                  {result.selectedPlan.name}
                </span>
                <Badge tone="green">cost {result.selectedPlan.estimatedCost}</Badge>
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {result.selectedPlan.description}
              </p>
              <button
                type="button"
                onClick={() => onNavigate("plans")}
                className="mt-3 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
              >
                View all candidate plans →
              </button>
            </Card>
          )}
        </div>
      </div>

      {result?.success && result.explanation && (
        <Card title="Explainability summary" subtitle="Transparent reasoning for the chosen plan">
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {result.explanation.summary}
          </p>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {result.explanation.planSelection.reason}
          </p>
        </Card>
      )}
    </div>
  );
}
