import { EmptyState } from "../../components/States";
import type { OptimizationStep } from "../../types";
import { OptimizationCard } from "./OptimizationCard";

export function OptimizationTimeline({ steps }: { steps: OptimizationStep[] }) {
  if (!steps.length) {
    return (
      <EmptyState
        title="No optimization rewrites were necessary"
        description="The logical plan was already in a good shape for this query, or no rules matched."
      />
    );
  }
  return (
    <div className="relative space-y-4 pl-6">
      <span className="absolute left-2.5 top-2 bottom-2 w-px bg-slate-200 dark:bg-slate-800" />
      {steps.map((step, index) => (
        <div key={index} className="relative">
          <span className="absolute -left-4 top-5 h-2.5 w-2.5 rounded-full bg-blue-500 ring-4 ring-white dark:ring-slate-950" />
          <OptimizationCard step={step} index={index} />
        </div>
      ))}
    </div>
  );
}
