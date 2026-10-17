import { Card } from "../../components/Card";
import { formatCost, formatNumber, formatPercent } from "../../lib/format";
import type { CompileResult } from "../../types";

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card bodyClassName="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-800 dark:text-slate-100">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </Card>
  );
}

export function ImpactStats({ result }: { result: CompileResult }) {
  const steps = result.optimizationSteps;
  const totalCostSaved = steps.reduce(
    (sum, step) => sum + (step.estimatedImpact.costReduction ?? 0),
    0,
  );
  const bestReduction = steps.reduce(
    (max, step) => Math.max(max, step.estimatedImpact.rowReductionPercent ?? 0),
    0,
  );
  const selected = result.selectedPlan;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat
        label="Rules applied"
        value={String(result.metrics?.rulesApplied ?? steps.length)}
        hint={`${result.metrics?.rulesUsed?.length ?? 0} distinct rules`}
      />
      <Stat
        label="Candidate plans"
        value={String(result.metrics?.candidateCount ?? result.candidatePlans.length)}
        hint={selected ? `selected ${selected.name}` : undefined}
      />
      <Stat
        label="Cost saved by rules"
        value={formatCost(totalCostSaved)}
        hint={`best row reduction ${formatPercent(bestReduction)}`}
      />
      <Stat
        label="Plan generation"
        value={`${formatNumber(result.metrics?.planGenerationMs ?? 0, 2)} ms`}
        hint={`total compile ${formatNumber(result.metrics?.totalMs ?? 0, 2)} ms`}
      />
    </div>
  );
}
