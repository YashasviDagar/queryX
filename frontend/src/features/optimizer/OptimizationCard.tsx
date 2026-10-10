import { Badge } from "../../components/Badge";
import { CodeBlock } from "../../components/CodeBlock";
import { formatCost, formatNumber, formatPercent } from "../../lib/format";
import type { OptimizationStep } from "../../types";

export function OptimizationCard({ step, index }: { step: OptimizationStep; index: number }) {
  const impact = step.estimatedImpact;
  const reduced = impact.rowReduction > 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
            {index + 1}
          </span>
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {step.rule}
          </span>
          <Badge tone="slate">{step.target}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={reduced ? "green" : "amber"}>
            {formatPercent(impact.rowReductionPercent)} row reduction
          </Badge>
          <Badge tone="blue">{formatCost(impact.costReduction)} cost saved</Badge>
        </div>
      </div>

      <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{step.reason}</p>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Before
          </div>
          <CodeBlock code={step.before} maxHeight="max-h-40" />
        </div>
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            After
          </div>
          <CodeBlock code={step.after} maxHeight="max-h-40" />
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-xs dark:border-slate-800 sm:grid-cols-4">
        <div>
          <dt className="text-slate-400">{impact.metricLabel ?? "Rows before"}</dt>
          <dd className="font-mono text-slate-700 dark:text-slate-200">
            {formatNumber(impact.estimatedRowsBefore)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Rows after</dt>
          <dd className="font-mono text-slate-700 dark:text-slate-200">
            {formatNumber(impact.estimatedRowsAfter)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Cost before</dt>
          <dd className="font-mono text-slate-700 dark:text-slate-200">
            {formatCost(impact.estimatedCostBefore)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Cost after</dt>
          <dd className="font-mono text-slate-700 dark:text-slate-200">
            {formatCost(impact.estimatedCostAfter)}
          </dd>
        </div>
      </dl>
    </div>
  );
}
