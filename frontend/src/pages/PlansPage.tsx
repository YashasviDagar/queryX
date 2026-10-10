import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { EmptyState } from "../components/States";
import { CostComparison } from "../features/plans/CostComparison";
import { PlanCard } from "../features/plans/PlanCard";
import { formatCost } from "../lib/format";
import { useQuery } from "../store/QueryProvider";
import type { CandidatePlan } from "../types";

export function PlansPage() {
  const { result } = useQuery();
  if (!result || !result.candidatePlans.length) {
    return (
      <EmptyState
        title="No candidate plans yet"
        description="Run a valid query to generate and cost alternative physical plans."
      />
    );
  }

  const sorted: CandidatePlan[] = [...result.candidatePlans].sort(
    (a, b) => a.estimatedCost - b.estimatedCost,
  );
  const maxCost = Math.max(...sorted.map((plan) => plan.estimatedCost));

  return (
    <div className="space-y-4">
      {result.selectedPlan && (
        <Card title="Selected plan" subtitle="Minimum estimated cost among all candidates">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-3xl font-semibold text-emerald-600 dark:text-emerald-400">
              {result.selectedPlan.name}
            </span>
            <Badge tone="green">cost {formatCost(result.selectedPlan.estimatedCost)}</Badge>
            <Badge tone="blue">{result.selectedPlan.joinAlgorithm}</Badge>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              {result.selectedPlan.description}
            </span>
          </div>
          {result.explanation?.planSelection.reason && (
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
              {result.explanation.planSelection.reason}
            </p>
          )}
        </Card>
      )}

      <Card title="Cost comparison" subtitle="All candidate plans ranked by estimated cost">
        <CostComparison rows={result.costComparison} />
      </Card>

      <div className="space-y-3">
        {sorted.map((plan, index) => (
          <PlanCard key={plan.id} plan={plan} rank={index} maxCost={maxCost} />
        ))}
      </div>
    </div>
  );
}
