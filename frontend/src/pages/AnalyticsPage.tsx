import { Card } from "../components/Card";
import { EmptyState } from "../components/States";
import { CostComparisonChart } from "../features/analytics/CostChart";
import { RowsChart } from "../features/analytics/RowsChart";
import { ImpactStats } from "../features/analytics/ImpactStats";
import { useQuery } from "../store/QueryProvider";

export function AnalyticsPage() {
  const { result } = useQuery();
  if (!result || !result.candidatePlans.length) {
    return (
      <EmptyState
        title="No analytics yet"
        description="Run a valid query to compare estimated costs and optimization impact."
      />
    );
  }

  return (
    <div className="space-y-4">
      <ImpactStats result={result} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Estimated cost by plan" subtitle="Lower is better; green is the selected plan">
          <CostComparisonChart rows={result.costComparison} />
        </Card>
        <Card title="Estimated rows by plan" subtitle="Output cardinality estimate per candidate">
          <RowsChart rows={result.costComparison} />
        </Card>
      </div>

      <Card
        title="Optimization impact"
        subtitle="Estimated rows and cost before/after each rule"
      >
        <div className="overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <th className="px-3 py-2">Rule</th>
                <th className="px-3 py-2 text-right">Rows before</th>
                <th className="px-3 py-2 text-right">Rows after</th>
                <th className="px-3 py-2 text-right">Reduction</th>
                <th className="px-3 py-2 text-right">Cost before</th>
                <th className="px-3 py-2 text-right">Cost after</th>
              </tr>
            </thead>
            <tbody>
              {result.optimizationSteps.map((step, index) => (
                <tr
                  key={index}
                  className="border-b border-slate-100 last:border-0 dark:border-slate-800/60"
                >
                  <td className="px-3 py-2 font-medium">{step.rule}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {step.estimatedImpact.estimatedRowsBefore.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {step.estimatedImpact.estimatedRowsAfter.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-emerald-600 dark:text-emerald-400">
                    {step.estimatedImpact.rowReductionPercent.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {step.estimatedImpact.estimatedCostBefore.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {step.estimatedImpact.estimatedCostAfter.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
