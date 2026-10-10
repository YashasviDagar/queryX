import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { formatCost, formatNumber, formatPercent } from "../../lib/format";
import type { Explanation } from "../../types";

export function ExplanationPanel({ explanation }: { explanation: Explanation }) {
  const selection = explanation.planSelection;
  return (
    <div className="space-y-4">
      <Card title="Pipeline summary" subtitle="What the optimizer did, in one sentence">
        <p className="text-sm text-slate-700 dark:text-slate-200">{explanation.summary}</p>
      </Card>

      <Card
        title="Why this plan was selected"
        subtitle="Cost-based decision with full comparison"
        actions={selection.selectedPlan ? <Badge tone="green">{selection.selectedPlan}</Badge> : null}
      >
        <p className="text-sm text-slate-700 dark:text-slate-200">{selection.reason}</p>
        {selection.savingsVsNextBest != null && (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Saves {formatCost(selection.savingsVsNextBest)} of estimated cost versus the next-best
            plan.
          </p>
        )}
      </Card>

      <Card
        title="Rule-by-rule explanations"
        subtitle="Each rewrite with its reason and estimated impact"
      >
        <ol className="space-y-3">
          {explanation.optimizationExplanations.map((item, index) => (
            <li
              key={index}
              className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="blue">{item.rule}</Badge>
                <Badge tone="slate">{item.target}</Badge>
                <span className="text-xs text-slate-400">
                  {formatNumber(item.estimatedRowsBefore)} → {formatNumber(item.estimatedRowsAfter)}{" "}
                  rows ({formatPercent(item.rowReductionPercent)})
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">{item.narrative}</p>
            </li>
          ))}
          {!explanation.optimizationExplanations.length && (
            <li className="text-sm text-slate-500 dark:text-slate-400">
              No optimization rules were applied for this query.
            </li>
          )}
        </ol>
      </Card>
    </div>
  );
}
